import json,mimetypes,re
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.accounts.models import ApiToken,DeviceSession,DeviceToken,EmailOTP,User,UserBlock
from apps.accounts.utils import client_ip,send_otp
from apps.audit.services import audit_actor
from .models import Attachment,ChatFolder,ChatFolderConversation,Conversation,ConversationMember,Message,MessageHiddenFor,MessageReceipt,Reaction,Sticker,StickerPack,UserNotification,Poll,PollOption,PollVote,ScheduledPost
from .services import (
    broadcast,conversation_cards,create_message,delete_chat_for_user,delete_message_for_user,get_or_create_direct,get_saved_conversation,
    mark_read,may_admin,may_write,message_payload,pair_is_blocked,visible_messages_for,server_timestamp_parts,
)


def _touch_api_presence(request, client_id=""):
    """Refresh durable presence for real native message/upload activity.

    Polling endpoints deliberately do not call this helper; only an explicit
    user action may move the last-seen clock forward.
    """
    try:
        from apps.accounts.presence import normalize_client_id, set_active
        token=getattr(request, "api_device_token", None)
        device_id=getattr(token, "device_id", None) if token else None
        raw=(request.headers.get("X-R-Mes-Presence-Client") or client_id
             or (f"device:{device_id}" if device_id else "api"))
        set_active(request.api_user, normalize_client_id(raw), True)
    except Exception:
        # Presence must never turn a successful message into a 5xx response.
        return

def api_user(request):
    auth=request.META.get("HTTP_AUTHORIZATION","")
    if auth.lower().startswith("bearer "):
        raw=auth.split(" ",1)[1].strip()
        dt=DeviceToken.authenticate_access(raw)
        if dt and dt.user.is_active and dt.user.can_login and not dt.user.is_suspended:
            request.api_device_token=dt
            return dt.user
        t=ApiToken.authenticate(raw)
        if t and t.user.is_active and t.user.can_login and not t.user.is_suspended:
            return t.user
    if request.user.is_authenticated:return request.user
    return None

def _device_credentials(request,user,data):
    device_id=str(data.get("device_id") or "")[:80]
    device_name=str(data.get("device_name") or data.get("name") or "R-Mes device")[:120]
    platform=str(data.get("platform") or "native")[:40]
    push_token=str(data.get("push_token") or "")[:512]
    device=None
    if device_id:
        device=DeviceSession.objects.filter(user=user,device_id=device_id,revoked_at__isnull=True).first()
    if device and device.trust_status==DeviceSession.Trust.BLOCKED:
        raise PermissionError("This device is blocked by R-Mes security policy.")
    if device:
        device.device_name=device_name;device.platform=platform;device.browser="native"
        device.ip_address=client_ip(request);device.user_agent=request.META.get("HTTP_USER_AGENT","")[:1000]
        if push_token:device.push_token=push_token
        device.last_seen_at=timezone.now()
        device.save(update_fields=["device_name","platform","browser","ip_address","user_agent","push_token","last_seen_at"])
        DeviceToken.objects.filter(device=device,revoked_at__isnull=True).update(revoked_at=timezone.now())
    else:
        device=DeviceSession.objects.create(
            user=user,device_id=device_id,device_name=device_name,platform=platform,browser="native",
            ip_address=client_ip(request),user_agent=request.META.get("HTTP_USER_AGENT","")[:1000],
            push_token=push_token,last_seen_at=timezone.now(),
        )
    tok,access,refresh=DeviceToken.issue(user,device,settings.ACCESS_TOKEN_MINUTES,settings.REFRESH_TOKEN_DAYS)
    return {"token":access,"access_token":access,"refresh_token":refresh,"token_type":"Bearer","expires_in":settings.ACCESS_TOKEN_MINUTES*60,"device_id":device.pk,"prefix":tok.access_prefix}

def require_user(view):
    @wraps(view)
    def wrapped(request,*a,**kw):
        u=api_user(request)
        if not u:return JsonResponse({"detail":"Authentication required"},status=401)
        request.api_user=u
        return view(request,*a,**kw)
    return wrapped

def body_json(request):
    try:return json.loads(request.body or "{}")
    except json.JSONDecodeError:return None

def visible_message(user,message_id,allow_deleted=False):
    msg=Message.objects.select_related("conversation").filter(pk=message_id,conversation__members__user=user).first()
    if not msg:return None
    member=msg.conversation.members.filter(user=user).first()
    if not member:return None
    if MessageHiddenFor.objects.filter(message=msg,user=user).exists():return None
    if member.hidden_before_message_id and msg.pk<=member.hidden_before_message_id:
        return None
    if msg.is_deleted and not allow_deleted:return None
    return msg

@csrf_exempt
def token_login(request):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    d=body_json(request)
    if d is None:return JsonResponse({"detail":"Invalid JSON"},status=400)
    email=(d.get("email") or "").lower().strip()
    u=authenticate(request,username=email,password=d.get("password") or "")
    if not u or u.is_suspended or not u.can_login or not u.email_verified:
        return JsonResponse({"detail":"Invalid credentials"},status=401)

    if settings.LOGIN_EMAIL_2FA:
        try:
            otp=send_otp(u.email,EmailOTP.Purpose.LOGIN,request)
            return JsonResponse({
                "two_factor_required":True,
                "challenge_id":otp.pk,
                "email":u.email,
            })
        except Exception as exc:
            return JsonResponse({"detail":f"Unable to send verification code: {exc}"},status=503)

    try:creds=_device_credentials(request,u,d)
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    return JsonResponse({**creds,"user":{"id":u.pk,"email":u.email,"name":u.display_name,"handle":u.handle,"avatar":u.avatar_url}})

@csrf_exempt
def token_verify(request):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    d=body_json(request)
    if d is None:return JsonResponse({"detail":"Invalid JSON"},status=400)
    email=(d.get("email") or "").lower().strip()
    otp=EmailOTP.objects.filter(
        pk=d.get("challenge_id"),email=email,purpose=EmailOTP.Purpose.LOGIN
    ).first()
    u=User.objects.filter(email=email,is_active=True,is_suspended=False,can_login=True,email_verified=True).first()
    if not otp or not u or not otp.verify_code(str(d.get("code") or "").strip(),settings.OTP_MAX_ATTEMPTS):
        return JsonResponse({"detail":"Invalid or expired code"},status=401)
    try:creds=_device_credentials(request,u,d)
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    return JsonResponse({**creds,"user":{"id":u.pk,"email":u.email,"name":u.display_name,"handle":u.handle,"avatar":u.avatar_url}})

@csrf_exempt
def refresh_token(request):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    d=body_json(request) or {}
    old,new_access,new_refresh=DeviceToken.refresh(d.get("refresh_token") or "")
    if not old:return JsonResponse({"detail":"Invalid or expired refresh token"},status=401)
    new=DeviceToken.objects.get(access_hash=__import__("hashlib").sha256(new_access.encode()).hexdigest())
    return JsonResponse({"access_token":new_access,"token":new_access,"refresh_token":new_refresh,"token_type":"Bearer","expires_in":settings.ACCESS_TOKEN_MINUTES*60,"prefix":new.access_prefix})

@require_user
def devices_api(request):
    rows=[]
    for d in request.api_user.device_sessions.filter(revoked_at__isnull=True).order_by("-last_seen_at")[:100]:
        rows.append({"id":d.pk,"device_id":d.device_id,"device_name":d.device_name,"platform":d.platform,"browser":d.browser,"ip":d.ip_address,"last_seen_at":d.last_seen_at.isoformat(),"trust_status":d.trust_status,"trust_reason":d.trust_reason,"current":getattr(request,"api_device_token",None) and getattr(request.api_device_token,"device_id",None)==d.pk})
    return JsonResponse({"results":rows})

@csrf_exempt
@require_user
def device_update_api(request,device_id):
    d=DeviceSession.objects.filter(pk=device_id,user=request.api_user,revoked_at__isnull=True).first()
    if not d:return JsonResponse({"detail":"Not found"},status=404)
    if request.method=="PATCH" or request.method=="POST":
        data=body_json(request) or {};d.push_token=str(data.get("push_token",d.push_token))[:512];d.device_name=str(data.get("device_name",d.device_name))[:120];d.last_seen_at=timezone.now();d.save(update_fields=["push_token","device_name","last_seen_at"]);return JsonResponse({"ok":True})
    if request.method=="DELETE":
        now=timezone.now();d.revoked_at=now;d.save(update_fields=["revoked_at"]);DeviceToken.objects.filter(device=d,revoked_at__isnull=True).update(revoked_at=now);return JsonResponse({"ok":True})
    return JsonResponse({"detail":"Method not allowed"},status=405)

@csrf_exempt
@require_user
def revoke_token(request):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    auth=request.META.get("HTTP_AUTHORIZATION","")
    if auth.lower().startswith("bearer "):
        raw=auth.split(" ",1)[1].strip();now=timezone.now()
        dt=DeviceToken.authenticate_access(raw)
        if dt:dt.revoked_at=now;dt.save(update_fields=["revoked_at"])
        else:
            t=ApiToken.authenticate(raw)
            if t:t.revoked_at=now;t.save(update_fields=["revoked_at"])
    return JsonResponse({"ok":True})

@require_user
def me(request):
    u=request.api_user
    return JsonResponse({
        "id":u.pk,"email":u.email,"display_name":u.display_name,"handle":u.handle,
        "bio":u.bio,"avatar":u.avatar_url,"role":u.role,
        "last_seen_at":u.last_seen_at.isoformat() if u.last_seen_at else None,
    })

@require_user
def users_search(request):
    q=request.GET.get("q","").strip();uq=q.lstrip("@");rows=[]
    if len(uq)>=1:
        qs=User.objects.filter(is_active=True,is_suspended=False).exclude(pk=request.api_user.pk).filter(
            Q(display_name__icontains=uq)|Q(email__icontains=uq)|Q(handle__icontains=uq)
        )[:30]
        from apps.accounts.presence import presence_label, presence_visibility
        for u in qs.select_related("preferences"):
            blocked=pair_is_blocked(request.api_user,u)
            visibility="hidden" if blocked else presence_visibility(request.api_user,u)
            exact=visibility=="exact"
            visible_online=bool(u.is_online) if exact else False
            rows.append({
                "id":u.pk,"email":u.email,"display_name":u.display_name,"handle":u.handle,
                "avatar":u.avatar_url,"online":visible_online,
                "developer":bool(u.is_developer),"hidden":visibility=="hidden","visibility":visibility,
                "last_seen_at":u.last_seen_at.isoformat() if (exact and u.last_seen_at) else None,
                "label":"недоступен" if blocked else presence_label(request.api_user,u,online=visible_online),
                "blocked":blocked,
            })
    return JsonResponse({"results":rows})

@csrf_exempt
@require_user
def direct_create(request):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    d=body_json(request) or {}
    identity=str(d.get("email") or d.get("username") or "").lower().strip()
    handle=identity.lstrip("@") if identity.startswith("@") else ""
    other=User.objects.filter(
        Q(email=identity)|Q(handle=handle)|
        Q(pk=d.get("user_id") if str(d.get("user_id","")).isdigit() else -1),
        is_active=True,is_suspended=False
    ).first()
    if not other:return JsonResponse({"detail":"User not found"},status=404)
    if pair_is_blocked(request.api_user,other):return JsonResponse({"detail":"Conversation blocked"},status=403)
    conv,_=get_or_create_direct(request.api_user,other)
    return JsonResponse({"id":str(conv.pk),"title":conv.display_title_for(request.api_user)})

@require_user
def conversations_api(request):
    return JsonResponse({"results":[{
        "id":str(c["conversation"].pk),"kind":c["conversation"].kind,"title":c["title"],
        "unread":c["unread"],"pinned":c["membership"].is_pinned,
        "archived":c["membership"].is_archived,"muted":c["membership"].muted,
        "updated_at":c["conversation"].updated_at.isoformat(),
        "peer":{
            "id":c["peer"].pk,"name":c["peer"].display_name,"handle":c["peer"].handle,
            "avatar":c["peer"].avatar_url,
        } if c.get("peer") else None,
    } for c in conversation_cards(request.api_user)[:300]]})

@csrf_exempt
@require_user
def messages_api(request,conversation_id):
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    if request.method=="GET":
        before=request.GET.get("before")
        qs=visible_messages_for(request.api_user,conv).select_related(
            "sender","reply_to__sender","forwarded_from__sender"
        ).prefetch_related("attachments","reactions__user","poll__options__votes").order_by("-id")
        if before and before.isdigit():qs=qs.filter(id__lt=int(before))
        objs=list(qs[:100]);rows=list(reversed([message_payload(x) for x in objs]))
        if objs:mark_read(request.api_user,conv,objs[0])
        return JsonResponse({"results":rows})
    if request.method=="POST":
        d=body_json(request)
        if d is None:return JsonResponse({"detail":"Invalid JSON"},status=400)
        _touch_api_presence(request,d.get("client_id") or d.get("client_message_id") or "")
        try:
            reply=visible_message(request.api_user,d.get("reply_to")) if d.get("reply_to") else None
            if reply and reply.conversation_id!=conv.id:reply=None
            msg=create_message(request.api_user,conv,d.get("body",""),reply_to=reply,client_message_id=d.get("client_id") or d.get("client_message_id") or "")
            return JsonResponse(message_payload(msg),status=201)
        except (ValueError,PermissionError) as exc:
            return JsonResponse({"detail":str(exc)},status=400)
    return JsonResponse({"detail":"Method not allowed"},status=405)

@csrf_exempt
@require_user
def delete_message_api(request,message_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    msg=visible_message(request.api_user,message_id)
    if not msg:return JsonResponse({"detail":"Not found"},status=404)
    d=body_json(request) or {};scope=d.get("scope","self")
    if scope=="self":
        result=delete_message_for_user(request.api_user,msg,scope="self")
        broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
        audit_actor(request.api_user,"chat.message_hide_self","Message",msg.pk,{"conversation":str(msg.conversation_id),"source":"api"})
        return JsonResponse({"ok":True,"scope":"self"})
    if scope=="peer":
        try:result=delete_message_for_user(request.api_user,msg,scope="peer")
        except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
        broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
        audit_actor(request.api_user,"chat.message_hide_peer","Message",msg.pk,{"conversation":str(msg.conversation_id),"source":"api","affected_user_ids":result["hidden_for_user_ids"]})
        return JsonResponse({"ok":True,"scope":"peer"})
    if msg.sender_id!=request.api_user.id and not (request.api_user.is_developer and msg.conversation.kind==Conversation.Kind.DIRECT):
        return JsonResponse({"detail":"Only sender can delete for everyone via API"},status=403)
    result=delete_message_for_user(request.api_user,msg,scope="everyone",reason="api")
    broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
    audit_actor(request.api_user,"chat.message_soft_delete","Message",msg.pk,{"conversation":str(msg.conversation_id),"source":"api","affected_user_ids":result["hidden_for_user_ids"],"protected_developer_ids":result["protected_developer_ids"]})
    return JsonResponse({"ok":True,"scope":"everyone"})

@csrf_exempt
@require_user
def delete_conversation_api(request,conversation_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    d=body_json(request) or {}
    try:event=delete_chat_for_user(request.api_user,conv,scope=d.get("scope","self"))
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    broadcast(conv.pk,"conversation_deleted",{"affected_user_ids":event.affected_user_ids})
    audit_actor(request.api_user,"chat.delete","Conversation",conv.pk,{"scope":event.scope,"source":"api","affected_user_ids":event.affected_user_ids,"protected_developer_ids":event.protected_developer_ids})
    return JsonResponse({"ok":True,"scope":event.scope})


@csrf_exempt
@require_user
def clear_conversation_api(request,conversation_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    d=body_json(request) or {}
    try:event=delete_chat_for_user(request.api_user,conv,scope=d.get("scope","self"),clear_history=True)
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    broadcast(conv.pk,"history_cleared",{"affected_user_ids":event.affected_user_ids,"through_message_id":event.through_message_id})
    audit_actor(request.api_user,"chat.clear_history","Conversation",conv.pk,{"scope":event.scope,"source":"api","affected_user_ids":event.affected_user_ids,"protected_developer_ids":event.protected_developer_ids})
    return JsonResponse({"ok":True,"scope":event.scope,"through_message_id":event.through_message_id,"applied":request.api_user.pk in event.affected_user_ids})

@csrf_exempt
@require_user
def block_api(request,user_id):
    target=User.objects.filter(pk=user_id,is_active=True).first()
    if not target:return JsonResponse({"detail":"Not found"},status=404)
    if request.method=="POST":
        if target.pk==request.api_user.pk:return JsonResponse({"detail":"Cannot block self"},status=400)
        UserBlock.objects.get_or_create(blocker=request.api_user,blocked=target)
        return JsonResponse({"ok":True,"blocked":True})
    if request.method=="DELETE":
        UserBlock.objects.filter(blocker=request.api_user,blocked=target).delete()
        return JsonResponse({"ok":True,"blocked":False})
    return JsonResponse({"detail":"Method not allowed"},status=405)

@csrf_exempt
@require_user
def react_api(request,message_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    msg=visible_message(request.api_user,message_id)
    if not msg:return JsonResponse({"detail":"Not found"},status=404)
    d=body_json(request) or {};emoji=(d.get("emoji") or "")[:16]
    if not emoji:return JsonResponse({"detail":"Emoji required"},status=400)
    obj=Reaction.objects.filter(message=msg,user=request.api_user,emoji=emoji).first()
    if obj:
        obj.delete()
    else:
        Reaction.objects.create(message=msg,user=request.api_user,emoji=emoji)
        if msg.sender_id and msg.sender_id!=request.api_user.pk:
            UserNotification.objects.create(
                user=msg.sender,kind=UserNotification.Kind.REACTION,message=msg,actor=request.api_user,
                title=f"{request.api_user.display_name} поставил(а) реакцию {emoji}",
                body=(msg.body or "Сообщение")[:300],
            )
    payload=message_payload(msg);broadcast(msg.conversation_id,"reaction",payload)
    return JsonResponse(payload)

@require_user
def saved_api(request):
    conv=get_saved_conversation(request.api_user)
    return JsonResponse({"id":str(conv.pk),"title":"Сохранённые сообщения","kind":conv.kind})

@csrf_exempt
@require_user
def notifications_api(request):
    if request.method=="GET":
        before=request.GET.get("before")
        qs=UserNotification.objects.filter(user=request.api_user).select_related("actor","message","message__conversation").order_by("-id")
        if before and str(before).isdigit():qs=qs.filter(id__lt=int(before))
        rows=[]
        for n in qs[:100]:
            timestamp=server_timestamp_parts(n.created_at)
            rows.append({
                "id":n.pk,"kind":n.kind,"title":n.title,"body":n.body,
                "read":bool(n.read_at),**timestamp,
                "time":timestamp["time_dhm"],
                "actor":{"id":n.actor_id,"name":n.actor.display_name,"handle":n.actor.handle,"avatar":n.actor.avatar_url} if n.actor else None,
                "message_id":n.message_id,
                "conversation_id":str(n.message.conversation_id) if n.message_id else None,
            })
        now=timezone.now()
        response=JsonResponse({"results":rows,"unread":UserNotification.objects.filter(user=request.api_user,read_at__isnull=True).count(),
                               "server_time":now.isoformat(),"server_time_ms":int(now.timestamp()*1000)})
        response["Cache-Control"]="no-store, private"
        return response
    if request.method=="POST":
        UserNotification.objects.filter(user=request.api_user,read_at__isnull=True).update(read_at=timezone.now())
        return JsonResponse({"ok":True})
    return JsonResponse({"detail":"Method not allowed"},status=405)

@csrf_exempt
@require_user
def folders_api(request):
    if request.method=="GET":
        rows=[]
        for folder in ChatFolder.objects.filter(user=request.api_user).prefetch_related("chat_links"):
            rows.append({
                "id":folder.pk,"name":folder.name,"smart_type":folder.smart_type,
                "position":folder.position,"include_muted":folder.include_muted,
                "conversation_ids":[str(x.conversation_id) for x in folder.chat_links.all()],
            })
        return JsonResponse({"results":rows})
    if request.method=="POST":
        d=body_json(request) or {}
        name=str(d.get("name") or "").strip()[:40]
        smart=str(d.get("smart_type") or ChatFolder.SmartType.CUSTOM)
        if not name:return JsonResponse({"detail":"Name required"},status=400)
        if smart not in dict(ChatFolder.SmartType.choices):smart=ChatFolder.SmartType.CUSTOM
        folder=ChatFolder.objects.create(
            user=request.api_user,name=name,smart_type=smart,
            position=max(0,min(int(d.get("position") or 0),999)),
            include_muted=bool(d.get("include_muted",True)),
        )
        ids=[x for x in d.get("conversation_ids",[]) if x]
        if smart==ChatFolder.SmartType.CUSTOM and ids:
            allowed=Conversation.objects.filter(pk__in=ids,members__user=request.api_user)
            ChatFolderConversation.objects.bulk_create([ChatFolderConversation(folder=folder,conversation=c) for c in allowed],ignore_conflicts=True)
        return JsonResponse({"id":folder.pk,"name":folder.name},status=201)
    return JsonResponse({"detail":"Method not allowed"},status=405)

@csrf_exempt
@require_user
def folder_detail_api(request,folder_id):
    folder=ChatFolder.objects.filter(pk=folder_id,user=request.api_user).first()
    if not folder:return JsonResponse({"detail":"Not found"},status=404)
    if request.method=="DELETE":
        folder.delete();return JsonResponse({"ok":True})
    if request.method in {"PATCH","POST"}:
        d=body_json(request) or {}
        if "name" in d:folder.name=str(d["name"]).strip()[:40] or folder.name
        if "position" in d:folder.position=max(0,min(int(d["position"] or 0),999))
        if "include_muted" in d:folder.include_muted=bool(d["include_muted"])
        folder.save(update_fields=["name","position","include_muted"])
        if "conversation_ids" in d and folder.smart_type==ChatFolder.SmartType.CUSTOM:
            folder.chat_links.all().delete()
            allowed=Conversation.objects.filter(pk__in=d.get("conversation_ids") or [],members__user=request.api_user)
            ChatFolderConversation.objects.bulk_create([ChatFolderConversation(folder=folder,conversation=c) for c in allowed],ignore_conflicts=True)
        return JsonResponse({"ok":True})
    return JsonResponse({"detail":"Method not allowed"},status=405)

@require_user
def stickers_api(request):
    packs=[]
    for pack in StickerPack.objects.filter(active=True).prefetch_related("stickers"):
        stickers=[]
        for item in pack.stickers.filter(active=True):
            stickers.append({
                "id":item.pk,"emoji":item.emoji,"title":item.title,
                "custom_emoji":item.is_custom_emoji,"url":item.image.url,
            })
        packs.append({"id":pack.pk,"name":pack.name,"slug":pack.slug,"stickers":stickers})
    return JsonResponse({"results":packs})

@csrf_exempt
@require_user
def send_sticker_api(request,conversation_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    d=body_json(request) or {}
    sticker=Sticker.objects.filter(pk=d.get("sticker_id"),active=True,pack__active=True).first()
    if not sticker:return JsonResponse({"detail":"Sticker not found"},status=404)
    try:
        msg=create_message(request.api_user,conv,"",kind=Message.Kind.STICKER,sticker=sticker,client_message_id=d.get("client_id") or "")
    except (ValueError,PermissionError) as exc:
        return JsonResponse({"detail":str(exc)},status=400)
    payload=message_payload(msg);broadcast(conv.pk,"message",payload)
    return JsonResponse(payload,status=201)

@csrf_exempt
@require_user
def upload_api(request,conversation_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    if not request.api_user.can_upload_files:return JsonResponse({"detail":"Upload forbidden"},status=403)
    file=request.FILES.get("file")
    if not file:return JsonResponse({"detail":"File required"},status=400)
    _touch_api_presence(request,request.POST.get("client_id") or "")
    if file.size>settings.MAX_UPLOAD_MB*1024*1024:return JsonResponse({"detail":f"Maximum {settings.MAX_UPLOAD_MB} MB"},status=413)
    kind=Message.Kind.VOICE if (getattr(file,"content_type","") or "").startswith("audio/") and request.POST.get("voice")=="1" else Message.Kind.FILE
    client_id=(request.POST.get("client_id") or "")[:64]
    if client_id:
        existing=(Message.objects.filter(sender=request.api_user,conversation=conv,client_message_id=client_id)
                  .prefetch_related("attachments","reactions__user","receipts","poll__options__votes").select_related("sender").first())
        if existing and existing.attachments.exists():
            return JsonResponse({"message":message_payload(existing),"duplicate":True},status=200)
    try:
        msg=create_message(
            request.api_user,conv,request.POST.get("body","").strip(),
            kind=kind,client_message_id=client_id,broadcast_realtime=False,
        )
    except (ValueError,PermissionError) as exc:
        return JsonResponse({"detail":str(exc)},status=400)
    claimed=str(getattr(file,"content_type","") or "").split(";",1)[0].strip().lower()
    guessed=(mimetypes.guess_type(file.name or "")[0] or "").lower()
    if not claimed or claimed in {"application/octet-stream","binary/octet-stream"}:claimed=guessed
    content_type=claimed[:120] if re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+",claimed or "") else "application/octet-stream"
    attachment=Attachment.objects.create(
        message=msg,file=file,original_name=file.name,
        content_type=content_type,size=file.size,
    )
    attachment.calculate_hash();attachment.save(update_fields=["sha256"])
    audit_actor(request.api_user,"chat.file_upload","Attachment",attachment.pk,{"conversation":str(conv.pk),"name":file.name,"size":file.size,"sha256":attachment.sha256,"source":"api"})
    try:
        from apps.securitycenter.services import queue_attachment_security_scan
        queue_attachment_security_scan(attachment)
    except Exception:pass
    if kind!=Message.Kind.VOICE:
        try:
            from apps.moderation.services import queue_attachment_scan
            queue_attachment_scan(attachment)
        except Exception:pass
    msg=Message.objects.select_related("sender").prefetch_related("attachments","reactions__user","receipts","poll__options__votes").get(pk=msg.pk)
    payload=message_payload(msg)
    from .services import broadcast_message_to_user_clients
    broadcast_message_to_user_clients(msg)
    broadcast(conv.pk,"message",payload)
    return JsonResponse({"message":payload,"scan_status":attachment.scan_status},status=201)

@require_user
def receipts_api(request,message_id):
    msg=visible_message(request.api_user,message_id)
    if not msg:return JsonResponse({"detail":"Not found"},status=404)
    if msg.sender_id!=request.api_user.pk and not request.api_user.is_control_admin:
        return JsonResponse({"detail":"Forbidden"},status=403)
    qs=MessageReceipt.objects.filter(message=msg).select_related("user").order_by("user__display_name")
    if not request.api_user.is_developer:
        qs=qs.exclude(user__role=User.Role.DEVELOPER)
    return JsonResponse({"results":[{
        "user":{"id":r.user_id,"name":r.user.display_name,"handle":r.user.handle,"avatar":r.user.avatar_url},
        "delivered_at":r.delivered_at.isoformat() if r.delivered_at else None,
        "read_at":r.read_at.isoformat() if r.read_at else None,
    } for r in qs]})

@csrf_exempt
@require_user
def polls_api(request,conversation_id):
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    if request.method=="GET":
        rows=[]
        for p in Poll.objects.filter(conversation=conv).prefetch_related("options__votes").order_by("-created_at")[:100]:
            rows.append({"id":p.pk,"question":p.question,"anonymous":p.anonymous,"multiple_choice":p.multiple_choice,"closed":p.is_closed,"closes_at":p.closes_at.isoformat() if p.closes_at else None,"options":[{"id":o.pk,"text":o.text,"votes":o.votes.count()} for o in p.options.all()]})
        return JsonResponse({"results":rows})
    if request.method!="POST":return JsonResponse({"detail":"Method not allowed"},status=405)
    if not may_write(request.api_user,conv):return JsonResponse({"detail":"Write forbidden"},status=403)
    if conv.kind==Conversation.Kind.CHANNEL and not may_admin(request.api_user,conv):return JsonResponse({"detail":"Channel admin required"},status=403)
    d=body_json(request) or {};question=str(d.get("question") or "").strip()[:300];options=[str(x).strip()[:200] for x in (d.get("options") or []) if str(x).strip()][:10]
    if not question or len(options)<2:return JsonResponse({"detail":"Question and at least 2 options required"},status=400)
    closes_at=None
    if d.get("closes_at"):
        from django.utils.dateparse import parse_datetime
        closes_at=parse_datetime(str(d["closes_at"]))
        if closes_at and timezone.is_naive(closes_at):closes_at=timezone.make_aware(closes_at)
    poll=Poll.objects.create(conversation=conv,created_by=request.api_user,question=question,anonymous=bool(d.get("anonymous")),multiple_choice=bool(d.get("multiple_choice")),closes_at=closes_at)
    PollOption.objects.bulk_create([PollOption(poll=poll,text=text,position=i) for i,text in enumerate(options)])
    msg=create_message(request.api_user,conv,question,kind=Message.Kind.POLL,poll=poll,client_message_id=str(d.get("client_id") or ""))
    payload=message_payload(Message.objects.select_related("sender","poll").prefetch_related("poll__options__votes","attachments","reactions__user","receipts").get(pk=msg.pk));broadcast(conv.pk,"message",payload)
    return JsonResponse(payload,status=201)

@csrf_exempt
@require_user
def poll_vote_api(request,poll_id):
    if request.method!="POST":return JsonResponse({"detail":"POST required"},status=405)
    poll=Poll.objects.filter(pk=poll_id,conversation__members__user=request.api_user).first()
    if not poll:return JsonResponse({"detail":"Not found"},status=404)
    if poll.is_closed:return JsonResponse({"detail":"Poll closed"},status=409)
    d=body_json(request) or {};option=PollOption.objects.filter(pk=d.get("option_id"),poll=poll).first()
    if not option:return JsonResponse({"detail":"Option not found"},status=404)
    existing=PollVote.objects.filter(poll=poll,user=request.api_user)
    if not poll.multiple_choice:existing.delete()
    vote=PollVote.objects.filter(option=option,user=request.api_user).first()
    if vote:vote.delete();selected=False
    else:PollVote.objects.create(poll=poll,option=option,user=request.api_user);selected=True
    msg=getattr(poll,"message",None);payload=message_payload(msg) if msg else {"poll":{"id":poll.pk}}
    broadcast(poll.conversation_id,"poll_updated",payload)
    return JsonResponse({"selected":selected,"poll":payload.get("poll")})

@csrf_exempt
@require_user
def scheduled_posts_api(request,conversation_id):
    conv=Conversation.objects.filter(pk=conversation_id,members__user=request.api_user).first()
    if not conv:return JsonResponse({"detail":"Not found"},status=404)
    if conv.kind!=Conversation.Kind.CHANNEL or not may_admin(request.api_user,conv):return JsonResponse({"detail":"Channel admin required"},status=403)
    if request.method=="GET":
        return JsonResponse({"results":[{"id":x.pk,"body":x.body,"silent":x.silent,"scheduled_for":x.scheduled_for.isoformat(),"status":x.status,"sent_message_id":x.sent_message_id,"last_error":x.last_error} for x in ScheduledPost.objects.filter(conversation=conv)[:200]]})
    if request.method!="POST":return JsonResponse({"detail":"Method not allowed"},status=405)
    d=body_json(request) or {}
    if d.get("action")=="cancel":
        row=ScheduledPost.objects.filter(pk=d.get("post_id"),conversation=conv,status=ScheduledPost.Status.SCHEDULED).first()
        if not row:return JsonResponse({"detail":"Not found"},status=404)
        row.status=ScheduledPost.Status.CANCELLED;row.save(update_fields=["status","updated_at"]);return JsonResponse({"ok":True})
    from django.utils.dateparse import parse_datetime
    when=parse_datetime(str(d.get("scheduled_for") or ""));body=str(d.get("body") or "").strip()
    if when and timezone.is_naive(when):when=timezone.make_aware(when)
    if not body or not when or when<=timezone.now():return JsonResponse({"detail":"Future scheduled_for and body required"},status=400)
    row=ScheduledPost.objects.create(conversation=conv,created_by=request.api_user,body=body,silent=bool(d.get("silent")),scheduled_for=when)
    return JsonResponse({"id":row.pk,"status":row.status,"scheduled_for":row.scheduled_for.isoformat()},status=201)
