from asgiref.sync import async_to_sync
from django.conf import settings
from channels.layers import get_channel_layer
from datetime import timedelta
import mimetypes
import os
import re
from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.db.models import Q,Max
from django.http import FileResponse,Http404,HttpResponse,JsonResponse,StreamingHttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_http_methods,require_POST

from apps.accounts.models import User,UserBlock,UserPreference
from apps.accounts.presence import (presence_label as _server_presence_label, set_active as _set_presence_active,
    touch_last_seen as _touch_last_seen, normalize_client_id as _normalize_presence_client, can_view_presence as _can_view_presence,
    presence_visibility as _presence_visibility)
from apps.audit.services import audit
from .forms import DirectChatForm,GroupForm
from .models import (
    Attachment,ChatFolder,ChatFolderConversation,Conversation,ConversationMember,Message,MessageHiddenFor,
    MessagePin,MessageReceipt,MessageRevision,Reaction,Sticker,StickerPack,UserNotification,Poll,PollOption,PollVote,ScheduledPost,CallSignalEvent,CallRecord,
)
from .services import (
    broadcast,conversation_cards,create_message,delete_chat_for_user,delete_message_for_user,
    get_or_create_direct,get_saved_conversation,mark_all_delivered,mark_read,may_admin,may_write,message_payload,
    pair_is_blocked,visible_messages_for,create_call_signal_event,server_timestamp_parts,
)

def _conv_for_user(user,cid):
    return get_object_or_404(
        Conversation.objects.prefetch_related("members__user"),
        pk=cid,members__user=user,
    )

def _message_for_user(user,message_id,allow_deleted=False):
    msg=Message.objects.select_related("conversation","sender","reply_to__sender","forwarded_from__sender").prefetch_related(
        "attachments","reactions__user"
    ).filter(pk=message_id,conversation__members__user=user).first()
    if not msg:raise Http404
    member=ConversationMember.objects.filter(conversation=msg.conversation,user=user).first()
    if not member:raise Http404
    if MessageHiddenFor.objects.filter(message=msg,user=user).exists():raise Http404
    if member.hidden_before_message_id and msg.pk<=member.hidden_before_message_id:
        raise Http404
    if msg.is_deleted and not allow_deleted:raise Http404
    return msg


def _attachment_for_user(user,attachment_id):
    attachment=(Attachment.objects.select_related("message__conversation","message__sender")
                .filter(pk=attachment_id,message__conversation__members__user=user).first())
    if not attachment:raise Http404
    member=ConversationMember.objects.filter(conversation=attachment.message.conversation,user=user).first()
    if not member or MessageHiddenFor.objects.filter(message=attachment.message,user=user).exists():raise Http404
    if member.hidden_before_message_id and attachment.message_id<=member.hidden_before_message_id:
        raise Http404
    return attachment


def _normalized_content_type(upload):
    claimed=str(getattr(upload,"content_type","") or "").split(";",1)[0].strip().lower()
    guessed=(mimetypes.guess_type(getattr(upload,"name","") or "")[0] or "").lower()
    if not claimed or claimed in {"application/octet-stream","binary/octet-stream"}:
        claimed=guessed
    return claimed[:120] if re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+",claimed or "") else "application/octet-stream"


def _range_chunks(file_obj,remaining,chunk_size=64*1024):
    try:
        while remaining>0:
            chunk=file_obj.read(min(chunk_size,remaining))
            if not chunk:break
            remaining-=len(chunk)
            yield chunk
    finally:
        file_obj.close()

def _presence_label(viewer,peer):
    return _server_presence_label(viewer, peer)


def _touch_request_presence(request):
    """Record activity for a real authenticated page/API request.

    This is a safety net for clients whose websocket or JavaScript heartbeat is
    unavailable. It updates the durable last-seen value without trusting a
    browser-supplied timestamp.
    """
    try:
        # Only a real client that supplies its per-window id may create a
        # presence lease.  A normal HTML/history request has no matching
        # pagehide event; creating a fallback ``web`` lease here used to keep
        # users online for up to 45 seconds after they had left.
        raw_client=request.headers.get("X-R-Mes-Presence-Client")
        if raw_client:
            _set_presence_active(request.user, _normalize_presence_client(raw_client), True)
        else:
            _touch_last_seen(request.user)
    except Exception:
        return

def _folder_rows(user):
    return ChatFolder.objects.filter(user=user).order_by("position","id")[:12]

def _notification_context(user):
    qs=UserNotification.objects.filter(user=user).select_related("actor","message__conversation")
    return {"notification_rows":qs[:30],"notification_unread":qs.filter(read_at__isnull=True).count()}

@login_required
def home(request):
    _touch_request_presence(request)
    mark_all_delivered(request.user)
    folder=request.GET.get("folder","all")
    cards=conversation_cards(request.user,folder=folder)
    ctx={"cards":cards,"conversation":None,"folder":folder,"custom_folders":_folder_rows(request.user)}
    ctx.update(_notification_context(request.user))
    response=render(request,"chat/shell.html",ctx)
    response["Cache-Control"]="no-store, private"
    return response

@login_required
def conversation(request,conversation_id):
    _touch_request_presence(request)
    mark_all_delivered(request.user)
    conv=_conv_for_user(request.user,conversation_id)
    member=ConversationMember.objects.get(conversation=conv,user=request.user)
    member.is_hidden=False
    member.save(update_fields=["is_hidden"])

    folder=request.GET.get("folder","all")
    q=request.GET.get("mq","").strip()
    jump=request.GET.get("jump","").strip()

    qs=visible_messages_for(request.user,conv).select_related(
        "sender","reply_to__sender","forwarded_from__sender"
    ).prefetch_related("attachments","reactions__user","receipts","poll__options__votes").order_by("-id")

    if q:
        qs=qs.filter(Q(body__icontains=q)|Q(sender__display_name__icontains=q)|Q(sender__email__icontains=q))
    elif jump.isdigit():
        center=int(jump)
        qs=qs.filter(id__gte=max(1,center-80),id__lte=center+80)

    rows=list(reversed(list(qs[:140])))
    if rows:mark_read(request.user,conv,rows[-1])

    cards=conversation_cards(request.user,folder=folder)
    visible_qs=visible_messages_for(request.user,conv).filter(is_deleted=False)
    shared_images=Attachment.objects.filter(
        message__in=visible_qs,content_type__startswith="image/"
    ).order_by("-created_at")[:9]
    shared_files_count=Attachment.objects.filter(message__in=visible_qs).exclude(content_type__startswith="image/").count()
    shared_media_count=Attachment.objects.filter(message__in=visible_qs,content_type__startswith="image/").count()
    peer=conv.peer_for(request.user)
    blocked_by_me=bool(peer and UserBlock.objects.filter(blocker=request.user,blocked=peer).exists())
    blocked_me=bool(peer and UserBlock.objects.filter(blocker=peer,blocked=request.user).exists())
    audit(request,"chat.open","Conversation",str(conv.pk),{"title":conv.display_title_for(request.user)})

    ctx={
        "cards":cards,"conversation":conv,"chat_title":conv.display_title_for(request.user),
        "message_rows":rows,"member":member,"may_write":may_write(request.user,conv),
        "may_admin":may_admin(request.user,conv),"peer":peer,
        "peer_presence":"недоступен" if (blocked_by_me or blocked_me) else _presence_label(request.user,peer),
        "blocked_by_me":blocked_by_me,"blocked_me":blocked_me,
        "message_search":q,"folder":folder,"jump_message_id":jump if jump.isdigit() else "",
        "shared_images":shared_images,"shared_media_count":shared_media_count,
        "shared_files_count":shared_files_count,"custom_folders":_folder_rows(request.user),
        "pinned_rows":conv.pins.select_related("message__sender").order_by("-created_at")[:20],
        "sticker_packs":StickerPack.objects.filter(active=True).prefetch_related("stickers")[:12],
    }
    ctx.update(_notification_context(request.user))
    response=render(request,"chat/shell.html",ctx)
    response["Cache-Control"]="no-store, private"
    return response

@login_required
@require_http_methods(["GET","POST"])
def new_direct(request):
    if not request.user.can_start_direct_chats:
        return JsonResponse({"detail":"Личные чаты запрещены политикой."},status=403)
    form=DirectChatForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        other=User.objects.get(email=form.cleaned_data["email"])
        if other==request.user:
            form.add_error("email","Нельзя написать самому себе.")
        elif pair_is_blocked(request.user,other):
            form.add_error("email","Диалог недоступен из-за блокировки.")
        else:
            conv,created=get_or_create_direct(request.user,other)
            audit(request,"chat.direct_create" if created else "chat.direct_open","Conversation",str(conv.pk),{"peer":other.email})
            return redirect("chat:conversation",conversation_id=conv.pk)
    return render(request,"chat/new_direct.html",{"form":form})

@login_required
def open_user(request,user_id):
    if not request.user.can_start_direct_chats:
        messages.error(request,"Личные чаты запрещены политикой.")
        return redirect("chat:home")
    other=get_object_or_404(User,pk=user_id,is_active=True,is_suspended=False)
    if other.pk==request.user.pk:
        return redirect("accounts:profile")
    if pair_is_blocked(request.user,other):
        messages.error(request,"Диалог недоступен из-за блокировки.")
        return redirect("chat:home")
    conv,created=get_or_create_direct(request.user,other)
    audit(request,"chat.direct_create" if created else "chat.direct_open","Conversation",str(conv.pk),{"peer":other.email})
    return redirect("chat:conversation",conversation_id=conv.pk)

@login_required
@require_http_methods(["GET","POST"])
def new_group(request):
    if not request.user.can_create_groups:
        return JsonResponse({"detail":"Создание групп запрещено политикой."},status=403)
    form=GroupForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data
        conv=Conversation.objects.create(kind=d["kind"],title=d["title"],description=d["description"],created_by=request.user)
        ConversationMember.objects.create(conversation=conv,user=request.user,role=ConversationMember.Role.OWNER)
        emails=[x.strip().lower() for x in d["members"].replace("\n",",").split(",") if x.strip()]
        for u in User.objects.filter(email__in=emails,is_active=True,is_suspended=False):
            ConversationMember.objects.get_or_create(conversation=conv,user=u)
        audit(request,"chat.group_create","Conversation",str(conv.pk),{"kind":conv.kind,"members":emails})
        return redirect("chat:conversation",conversation_id=conv.pk)
    return render(request,"chat/new_group.html",{"form":form})

@login_required
def people_search(request):
    q=request.GET.get("q","").strip()
    uq=q.lstrip("@")
    rows=[]
    if len(uq)>=1:
        qs=User.objects.filter(is_active=True,is_suspended=False).exclude(pk=request.user.pk).filter(
            Q(email__icontains=uq)|Q(display_name__icontains=uq)|Q(handle__icontains=uq)
        )[:50]
        rows=list(qs)
        for row in rows:
            # Keep the contacts screen consistent with chat headers/sidebar:
            # the label is generated from the authoritative server clock and
            # applies the developer privacy rule for this viewer.
            row.presence_status=_presence_label(request.user,row)
    return render(request,"chat/people_search.html",{"rows":rows,"q":q})

@login_required
def search_suggest(request):
    q=(request.GET.get("q") or "").strip()
    if not q:return JsonResponse({"people":[],"chats":[],"messages":[]})
    uq=q.lstrip("@")
    cache_key=f"search-suggest:v4:{request.user.pk}:{uq.lower()[:80]}"
    cached=cache.get(cache_key)
    if cached is not None:return JsonResponse(cached)
    ql=uq.lower()

    people=[]
    user_qs=User.objects.filter(is_active=True,is_suspended=False).exclude(pk=request.user.pk).filter(
        Q(display_name__icontains=uq)|Q(email__icontains=uq)|Q(handle__icontains=uq)
    )[:30]
    ranked=sorted(
        user_qs,
        key=lambda u:(
            not (u.display_name or "").lower().startswith(ql),
            not (u.handle or "").lower().startswith(ql),
            not u.email.lower().startswith(ql),
            (u.display_name or u.email).lower(),
        )
    )[:8]
    for u in ranked:
        blocked=UserBlock.objects.filter(Q(blocker=request.user,blocked=u)|Q(blocker=u,blocked=request.user)).exists()
        people.append({
            "id":u.pk,"name":u.display_name,"email":u.email,"handle":u.handle or "",
            "avatar":u.avatar_url,"initials":u.initials,"blocked":blocked,
            "status":"недоступен" if blocked else _presence_label(request.user,u),
            "url":f"/u/{u.pk}/open/",
        })

    cards=conversation_cards(request.user,query=q)
    chats=[{
        "id":str(c["conversation"].pk),"title":c["title"],"kind":c["conversation"].kind,
        "unread":c["unread"],"avatar":c["peer"].avatar_url if c.get("peer") else "",
        "initials":(c["title"][:1] or "?").upper(),
        "url":f"/c/{c['conversation'].pk}/",
    } for c in cards[:8]]

    memberships={m.conversation_id:m for m in ConversationMember.objects.filter(user=request.user)}
    message_qs=Message.objects.filter(
        conversation__members__user=request.user,body__icontains=q,is_deleted=False
    ).select_related("conversation","sender").prefetch_related("hidden_for").order_by("-created_at").distinct()[:40]
    msg_results=[]
    for m in message_qs:
        mm=memberships.get(m.conversation_id)
        if not mm:continue
        if any(h.user_id==request.user.id for h in m.hidden_for.all()):continue
        if mm.hidden_before_message_id and m.pk<=mm.hidden_before_message_id:continue
        if mm.is_hidden:continue
        msg_results.append({
            "id":m.pk,"chat":m.conversation.display_title_for(request.user),
            "sender":m.sender.display_name if m.sender else "Удалённый пользователь",
            "text":"Сообщение удалено" if m.is_deleted else m.body[:140],
            "time":timezone.localtime(m.created_at).strftime("%d.%m %H:%M"),
            "url":f"/c/{m.conversation_id}/?jump={m.pk}#msg-{m.pk}",
        })
        if len(msg_results)>=8:break

    payload={"people":people,"chats":chats,"messages":msg_results}
    cache.set(cache_key,payload,12)
    return JsonResponse(payload)


@login_required
def history_api(request,conversation_id):
    _touch_request_presence(request)
    conv=_conv_for_user(request.user,conversation_id)
    before=(request.GET.get("before") or "").strip()
    after=(request.GET.get("after") or "").strip()
    try:limit=int(request.GET.get("limit","60") or 60)
    except (TypeError,ValueError):limit=60
    limit=min(max(limit,20),100)
    base=visible_messages_for(request.user,conv).select_related(
        "sender","reply_to__sender","forwarded_from__sender"
    ).prefetch_related("attachments","reactions__user","poll__options__votes")
    if after.isdigit():
        objs=list(base.filter(id__gt=int(after)).order_by("id")[:limit+1])
        has_more=len(objs)>limit;objs=objs[:limit]
        return JsonResponse({
            "results":[message_payload(x) for x in objs],
            "has_more":has_more,
            "next_after":objs[-1].pk if objs else int(after),
        })
    qs=base.order_by("-id")
    if before.isdigit():qs=qs.filter(id__lt=int(before))
    objs=list(qs[:limit+1]);has_more=len(objs)>limit;objs=objs[:limit]
    return JsonResponse({
        "results":[message_payload(x) for x in reversed(objs)],
        "has_more":has_more,
        "next_before":objs[-1].pk if objs else None,
    })

@login_required
def message_search_api(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    q=(request.GET.get("q") or "").strip()
    if not q:return JsonResponse({"results":[]})
    uq=q.lstrip("@")
    qs=visible_messages_for(request.user,conv).filter(is_deleted=False).filter(
        Q(body__icontains=q)|Q(sender__display_name__icontains=uq)|Q(sender__email__icontains=uq)|Q(sender__handle__icontains=uq)
    ).select_related("sender").order_by("-created_at")[:50]
    return JsonResponse({"results":[{
        "id":m.pk,"sender":m.sender.display_name if m.sender else "—",
        "text":"Сообщение удалено" if m.is_deleted else m.body[:180],
        "time":timezone.localtime(m.created_at).strftime("%d.%m.%Y %H:%M"),
        "url":f"/c/{conv.pk}/?jump={m.pk}#msg-{m.pk}",
    } for m in qs]})

@login_required
@require_POST
def upload_attachment(request,conversation_id):
    _touch_request_presence(request)
    conv=_conv_for_user(request.user,conversation_id)
    if not request.user.can_upload_files or not may_write(request.user,conv):
        return JsonResponse({"detail":"Загрузка запрещена."},status=403)
    f=request.FILES.get("file")
    if not f:return JsonResponse({"detail":"Файл не выбран."},status=400)
    if f.size>settings.MAX_UPLOAD_MB*1024*1024:
        return JsonResponse({"detail":f"Максимум {settings.MAX_UPLOAD_MB} MB."},status=413)
    kind=Message.Kind.VOICE if (getattr(f,"content_type","") or "").startswith("audio/") and request.POST.get("voice")=="1" else Message.Kind.FILE
    client_id=(request.POST.get("client_id") or "")[:64]
    # Idempotent retry: if the server accepted this upload but the client lost the response,
    # return the already-created message instead of creating a duplicate attachment.
    if client_id:
        existing=(Message.objects.filter(sender=request.user,conversation=conv,client_message_id=client_id)
                  .prefetch_related("attachments","reactions__user","poll__options__votes").select_related("sender").first())
        if existing and existing.attachments.exists():
            return JsonResponse({"ok":True,"message":message_payload(existing),"duplicate":True})
    # Keep attachment bubbles clean like Telegram: filename belongs to the attachment card,
    # not to message text. A real caption is preserved when the client sends one.
    msg=create_message(
        request.user,conv,request.POST.get("body","").strip(),kind=kind,
        client_message_id=client_id,broadcast_realtime=False,
    )
    a=Attachment(message=msg,file=f,original_name=f.name,content_type=_normalized_content_type(f),size=f.size)
    a.save();a.calculate_hash();a.save(update_fields=["sha256"])
    try:
        from apps.securitycenter.services import queue_attachment_security_scan
        queue_attachment_security_scan(a)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to queue security scan for attachment %s",a.pk)
    try:
        from apps.moderation.services import queue_attachment_scan
        queue_attachment_scan(a)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to queue moderation scan for attachment %s",a.pk)
    audit(request,"chat.file_upload","Attachment",str(a.pk),{"conversation":str(conv.pk),"name":f.name,"size":f.size,"sha256":a.sha256})
    msg=Message.objects.prefetch_related("attachments","reactions__user","poll__options__votes").select_related("sender").get(pk=msg.pk)
    payload=message_payload(msg)
    from .services import broadcast_message_to_user_clients
    broadcast_message_to_user_clients(msg)
    broadcast(conv.pk,"message",payload)
    if request.headers.get("X-Requested-With")=="XMLHttpRequest":
        return JsonResponse({"ok":True,"message":payload})
    return redirect("chat:conversation",conversation_id=conv.pk)

@login_required
@require_POST
def edit_message(request,message_id):
    msg=_message_for_user(request.user,message_id)
    if msg.sender_id!=request.user.id:return JsonResponse({"detail":"Forbidden"},status=403)
    body=(request.POST.get("body") or "").strip()
    if not body or len(body)>10000:return JsonResponse({"detail":"Некорректный текст."},status=400)
    MessageRevision.objects.create(message=msg,editor=request.user,old_body=msg.body,new_body=body)
    msg.body=body;msg.edited_at=timezone.now();msg.save(update_fields=["body","edited_at"])
    try:
        from apps.moderation.services import moderate_text_message
        moderate_text_message(msg)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Text moderation hook failed after edit for message %s",msg.pk)
    audit(request,"chat.message_edit","Message",str(msg.pk),{"conversation":str(msg.conversation_id)})
    broadcast(msg.conversation_id,"message_updated",message_payload(msg))
    return JsonResponse({"ok":True,"message":message_payload(msg)})

@login_required
@require_POST
def delete_message(request,message_id):
    msg=_message_for_user(request.user,message_id)
    m=ConversationMember.objects.filter(conversation=msg.conversation,user=request.user).first()
    if not m:raise Http404
    scope=request.POST.get("scope","everyone")
    if scope=="self":
        result=delete_message_for_user(request.user,msg,scope="self")
        audit(request,"chat.message_hide_self","Message",str(msg.pk),{"conversation":str(msg.conversation_id)})
        broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
        return JsonResponse({"ok":True,"scope":"self","id":msg.pk})
    if scope=="peer":
        try:result=delete_message_for_user(request.user,msg,scope="peer")
        except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
        audit(request,"chat.message_hide_peer","Message",str(msg.pk),{"conversation":str(msg.conversation_id),"affected_user_ids":result["hidden_for_user_ids"]})
        broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
        return JsonResponse({"ok":True,"scope":"peer","id":msg.pk})
    if msg.sender_id!=request.user.id and not (request.user.is_developer and msg.conversation.kind==Conversation.Kind.DIRECT):
        if msg.conversation.kind==Conversation.Kind.DIRECT or m.role not in {ConversationMember.Role.OWNER,ConversationMember.Role.ADMIN}:
            return JsonResponse({"detail":"Удалить у всех можно только своё сообщение."},status=403)
    result=delete_message_for_user(request.user,msg,scope="everyone",reason=request.POST.get("reason","user request"))
    audit(request,"chat.message_soft_delete","Message",str(msg.pk),{
        "conversation":str(msg.conversation_id),"forensic_body_retained":True,
        "affected_user_ids":result["hidden_for_user_ids"],"protected_developer_ids":result["protected_developer_ids"],
    })
    broadcast(msg.conversation_id,"message_deleted",{"id":msg.pk,"hidden_for_user_ids":result["hidden_for_user_ids"]})
    return JsonResponse({"ok":True,"scope":"everyone","id":msg.pk})

@login_required
@require_POST
def react_message(request,message_id):
    msg=_message_for_user(request.user,message_id)
    emoji=(request.POST.get("emoji") or "").strip()[:16]
    if not emoji:return JsonResponse({"detail":"Emoji required"},status=400)
    obj=Reaction.objects.filter(message=msg,user=request.user,emoji=emoji).first()
    if obj:obj.delete();active=False
    else:
        Reaction.objects.create(message=msg,user=request.user,emoji=emoji);active=True
        if msg.sender_id and msg.sender_id!=request.user.id:
            UserNotification.objects.create(user=msg.sender,kind=UserNotification.Kind.REACTION,message=msg,actor=request.user,title=f"{request.user.display_name} отреагировал(а) {emoji}",body=msg.body[:500])
    payload=message_payload(Message.objects.select_related("sender","reply_to__sender","forwarded_from__sender").prefetch_related("attachments","reactions__user","poll__options__votes").get(pk=msg.pk))
    broadcast(msg.conversation_id,"reaction",payload)
    return JsonResponse({"ok":True,"active":active,"message":payload})

@login_required
@require_POST
def pin_message(request,message_id):
    msg=_message_for_user(request.user,message_id)
    conv=msg.conversation
    m=ConversationMember.objects.filter(conversation=conv,user=request.user).first()
    if not m:raise Http404
    if conv.only_admins_can_pin and m.role not in {ConversationMember.Role.OWNER,ConversationMember.Role.ADMIN}:
        return JsonResponse({"detail":"Только администраторы могут закреплять."},status=403)
    existing=MessagePin.objects.filter(conversation=conv,message=msg).first()
    if existing:existing.delete();active=False
    else:MessagePin.objects.create(conversation=conv,message=msg,pinned_by=request.user);active=True
    latest=conv.pins.select_related("message").order_by("-created_at").first();conv.pinned_message=latest.message if latest else None;conv.save(update_fields=["pinned_message"])
    audit(request,"chat.message_pin","Message",str(msg.pk),{"conversation":str(conv.pk),"active":active})
    broadcast(conv.pk,"pinned",{"message_id":conv.pinned_message_id,"count":conv.pins.count()})
    return JsonResponse({"ok":True,"message_id":conv.pinned_message_id,"active":active,"count":conv.pins.count()})

@login_required
@require_POST
def forward_message(request,message_id):
    src=_message_for_user(request.user,message_id)
    target=_conv_for_user(request.user,request.POST.get("conversation_id"))
    msg=create_message(request.user,target,src.body,forwarded_from=src)
    broadcast(target.pk,"message",message_payload(msg))
    audit(request,"chat.message_forward","Message",str(src.pk),{"target":str(target.pk)})
    return JsonResponse({"ok":True,"target":str(target.pk)})

@login_required
@require_POST
def toggle_chat_pin(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    m=ConversationMember.objects.get(conversation=conv,user=request.user)
    m.is_pinned=not m.is_pinned;m.save(update_fields=["is_pinned"])
    return JsonResponse({"ok":True,"pinned":m.is_pinned})

@login_required
@require_POST
def toggle_archive(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    m=ConversationMember.objects.get(conversation=conv,user=request.user)
    m.is_archived=not m.is_archived;m.save(update_fields=["is_archived"])
    audit(request,"chat.archive_toggle","Conversation",str(conv.pk),{"archived":m.is_archived})
    return JsonResponse({"ok":True,"archived":m.is_archived})

@login_required
@require_POST
def toggle_mute(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    m=ConversationMember.objects.get(conversation=conv,user=request.user)
    m.notifications_enabled=not m.notifications_enabled
    m.muted=not m.notifications_enabled
    m.save(update_fields=["notifications_enabled","muted"])
    return JsonResponse({"ok":True,"muted":m.muted})

@login_required
@require_POST
def delete_conversation(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    scope=request.POST.get("scope","self")
    try:event=delete_chat_for_user(request.user,conv,scope=scope)
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    audit(request,"chat.delete","Conversation",str(conv.pk),{
        "scope":event.scope,"affected_user_ids":event.affected_user_ids,
        "protected_developer_ids":event.protected_developer_ids,
        "forensic_copy_retained":True,
    })
    broadcast(conv.pk,"conversation_deleted",{"affected_user_ids":event.affected_user_ids})
    return JsonResponse({
        "ok":True,"scope":event.scope,"redirect":"/",
    })


@login_required
@require_POST
def clear_conversation_history(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    scope=request.POST.get("scope","self")
    try:event=delete_chat_for_user(request.user,conv,scope=scope,clear_history=True)
    except PermissionError as exc:return JsonResponse({"detail":str(exc)},status=403)
    audit(request,"chat.clear_history","Conversation",str(conv.pk),{
        "scope":event.scope,"through_message_id":event.through_message_id,
        "affected_user_ids":event.affected_user_ids,"protected_developer_ids":event.protected_developer_ids,
        "forensic_copy_retained":True,
    })
    broadcast(conv.pk,"history_cleared",{"affected_user_ids":event.affected_user_ids,"through_message_id":event.through_message_id})
    return JsonResponse({"ok":True,"scope":event.scope,"through_message_id":event.through_message_id,"applied":request.user.pk in event.affected_user_ids})

@login_required
@require_POST
def block_user(request,user_id):
    target=get_object_or_404(User,pk=user_id,is_active=True)
    if target.pk==request.user.pk:return JsonResponse({"detail":"Нельзя заблокировать себя."},status=400)
    obj,created=UserBlock.objects.get_or_create(blocker=request.user,blocked=target)
    audit(request,"privacy.block_user","User",str(target.pk),{"email":target.email})
    return JsonResponse({"ok":True,"blocked":True,"created":created})

@login_required
@require_POST
def unblock_user(request,user_id):
    target=get_object_or_404(User,pk=user_id)
    count,_=UserBlock.objects.filter(blocker=request.user,blocked=target).delete()
    audit(request,"privacy.unblock_user","User",str(target.pk),{"email":target.email})
    return JsonResponse({"ok":True,"blocked":False,"removed":bool(count)})

@login_required
@require_http_methods(["GET","POST"])
def conversation_info(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    m=ConversationMember.objects.get(conversation=conv,user=request.user)
    admin=m.role in {ConversationMember.Role.OWNER,ConversationMember.Role.ADMIN}
    peer=conv.peer_for(request.user)
    blocked_by_me=bool(peer and UserBlock.objects.filter(blocker=request.user,blocked=peer).exists())
    blocked_me=bool(peer and UserBlock.objects.filter(blocker=peer,blocked=request.user).exists())
    if request.method=="POST":
        action=request.POST.get("action")
        if action=="add_member":
            if conv.only_admins_can_invite and not admin:return JsonResponse({"detail":"Forbidden"},status=403)
            identity=(request.POST.get("email") or "").lower().strip()
            if identity.startswith("@"):
                u=User.objects.filter(handle=identity.lstrip("@"),is_active=True,is_suspended=False).first()
            else:
                u=User.objects.filter(email=identity,is_active=True,is_suspended=False).first()
            email=u.email if u else identity
            if not u:messages.error(request,"Пользователь не найден.")
            else:
                ConversationMember.objects.get_or_create(conversation=conv,user=u)
                audit(request,"chat.member_add","Conversation",str(conv.pk),{"email":email})
                messages.success(request,"Участник добавлен.")
        elif action=="settings" and admin:
            conv.title=(request.POST.get("title") or conv.title)[:180]
            conv.description=(request.POST.get("description") or "")[:4000]
            conv.only_admins_can_invite=request.POST.get("only_admins_can_invite")=="on"
            conv.only_admins_can_pin=request.POST.get("only_admins_can_pin")=="on"
            conv.save()
            audit(request,"chat.settings_update","Conversation",str(conv.pk),{})
        elif action=="personal_settings":
            theme=request.POST.get("chat_theme")
            bg=request.POST.get("background_style")
            if theme in dict(ConversationMember.ChatTheme.choices):
                m.chat_theme=theme
            if bg in dict(ConversationMember.BackgroundStyle.choices):
                m.background_style=bg
            m.media_previews=request.POST.get("media_previews")=="on"
            m.notifications_enabled=request.POST.get("notifications_enabled")=="on"
            m.muted=not m.notifications_enabled
            m.save(update_fields=["chat_theme","background_style","media_previews","notifications_enabled","muted"])
            audit(request,"chat.personal_settings","ConversationMember",str(m.pk),{
                "conversation":str(conv.pk),"chat_theme":m.chat_theme,"background_style":m.background_style,
                "media_previews":m.media_previews,"notifications_enabled":m.notifications_enabled,
            })
            messages.success(request,"Личные настройки чата сохранены.")
        elif action=="member_role" and admin:
            member=ConversationMember.objects.filter(pk=request.POST.get("member_id"),conversation=conv).first()
            role=request.POST.get("role")
            if member and member.user_id!=request.user.id and role in dict(ConversationMember.Role.choices):
                member.role=role;member.save(update_fields=["role"])
                audit(request,"chat.member_role","ConversationMember",str(member.pk),{"role":role})
        elif action=="remove_member" and admin:
            member=ConversationMember.objects.filter(pk=request.POST.get("member_id"),conversation=conv).first()
            if member and member.role!=ConversationMember.Role.OWNER:
                email=member.user.email;member.delete()
                audit(request,"chat.member_remove","Conversation",str(conv.pk),{"email":email})
        return redirect("chat:conversation_info",conversation_id=conv.pk)
    return render(request,"chat/conversation_info.html",{
        "conversation":conv,"member":m,"admin":admin,
        "members":conv.members.select_related("user").all(),
        "peer":peer,"blocked_by_me":blocked_by_me,"blocked_me":blocked_me,
        "peer_presence":"недоступен" if (blocked_by_me or blocked_me) else _presence_label(request.user,peer),
    })

@login_required
def saved_messages(request):
    conv=get_saved_conversation(request.user)
    return redirect("chat:conversation",conversation_id=conv.pk)


@login_required
@require_http_methods(["GET","HEAD"])
def attachment_content(request,attachment_id):
    """Stream private media on the authenticated R-Mes origin."""
    attachment=_attachment_for_user(request.user,attachment_id)
    if attachment.scan_status=="infected":raise Http404
    name=os.path.basename(attachment.original_name or f"attachment-{attachment.pk}")[:255]
    content_type=(attachment.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream").split(";",1)[0]
    safe_inline=(content_type.startswith("audio/") or content_type.startswith("video/") or
                 (content_type.startswith("image/") and content_type!="image/svg+xml") or
                 content_type=="application/pdf")
    as_attachment=request.GET.get("download")=="1" or not safe_inline
    try:size=int(attachment.size or attachment.file.size or 0)
    except Exception:size=0
    base_headers={
        "Content-Type":content_type,"Accept-Ranges":"bytes","Cache-Control":"private, max-age=60",
        "Content-Disposition":content_disposition_header(as_attachment,name),"X-Content-Type-Options":"nosniff",
    }
    if request.method=="HEAD":
        response=HttpResponse(status=200,headers=base_headers)
        if size:response["Content-Length"]=str(size)
        return response
    range_header=(request.headers.get("Range") or "").strip()
    if range_header and size:
        match=re.fullmatch(r"bytes=(\d*)-(\d*)",range_header)
        if not match:
            response=HttpResponse(status=416);response["Content-Range"]=f"bytes */{size}";return response
        first,last=match.groups()
        if first:
            start=int(first);end=min(int(last) if last else size-1,size-1)
        elif last:
            length=min(int(last),size);start=size-length;end=size-1
        else:start=0;end=size-1
        if start<0 or start>=size or end<start:
            response=HttpResponse(status=416);response["Content-Range"]=f"bytes */{size}";return response
        file_obj=attachment.file.open("rb");file_obj.seek(start)
        response=StreamingHttpResponse(_range_chunks(file_obj,end-start+1),status=206,headers=base_headers)
        response["Content-Range"]=f"bytes {start}-{end}/{size}";response["Content-Length"]=str(end-start+1)
        return response
    file_obj=attachment.file.open("rb")
    response=FileResponse(file_obj,as_attachment=as_attachment,filename=name,content_type=content_type)
    for key,value in base_headers.items():response[key]=value
    if size:response["Content-Length"]=str(size)
    return response


@login_required
def attachment_status_api(request,attachment_id):
    a=_attachment_for_user(request.user,attachment_id)
    a.message=Message.objects.select_related("sender","conversation").prefetch_related("attachments","reactions__user","receipts","poll__options__votes").get(pk=a.message_id)
    job=getattr(a,"security_job",None)
    return JsonResponse({
        "ok":True,"attachment_id":a.pk,"scan_status":a.scan_status,
        "scan_engine":a.scan_engine,"job_status":getattr(job,"status",None),
        "message":message_payload(a.message),
    })

@login_required
@require_POST
def attachment_retry_scan(request,attachment_id):
    a=Attachment.objects.filter(pk=attachment_id,message__conversation__members__user=request.user).first()
    if not a:raise Http404
    try:
        from apps.securitycenter.services import queue_attachment_security_scan
        a.scan_status="pending";a.scan_signature="";a.save(update_fields=["scan_status","scan_signature"])
        queue_attachment_security_scan(a,force=True)
        return JsonResponse({"ok":True,"scan_status":"pending"})
    except Exception as exc:
        return JsonResponse({"detail":f"Не удалось повторить проверку: {exc}"},status=503)

@login_required
def sidebar_state_api(request):
    folder=(request.GET.get("folder") or "all").strip() or "all"
    rows=[]
    for card in conversation_cards(request.user,folder=folder):
        conv=card["conversation"];peer=card["peer"];last=card["last"];member=card["membership"]
        body=""
        if last:
            body="Сообщение удалено" if last.is_deleted else (last.body or "")
            if not body:
                att=last.attachments.first()
                if att:
                    ct=(att.content_type or "").lower()
                    body="Фото" if ct.startswith("image/") else "Видео" if ct.startswith("video/") else "Голосовое сообщение" if ct.startswith("audio/") else f"Файл: {att.original_name}"
        timestamp=server_timestamp_parts(last.created_at if last else None)
        peer_visibility=_presence_visibility(request.user,peer) if peer else "hidden"
        peer_exact=peer_visibility=="exact"
        rows.append({
            "id":str(conv.pk),"title":card["title"],"kind":conv.kind,"unread":int(card["unread"] or 0),
            "pinned":bool(member.is_pinned),"muted":bool(member.muted),
            "last":{"body":body,"mine":bool(last and last.sender_id==request.user.id),
                    **timestamp},
            "peer":None if not peer else {"id":peer.pk,"avatar":peer.avatar_url,
                    "online":peer.is_online if peer_exact else False,
                    "developer":peer.is_developer,"hidden":peer_visibility=="hidden","visibility":peer_visibility,
                    "status":_server_presence_label(request.user,peer,online=peer.is_online if peer_exact else False)},
            "url":f"/c/{conv.pk}/?folder={folder}",
        })
    now=timezone.now()
    response=JsonResponse({"results":rows,"folder":folder,"server_time":now.isoformat(),"server_time_ms":int(now.timestamp()*1000)})
    response["Cache-Control"]="no-store, private"
    return response

@login_required
@require_POST
def call_signal_api(request):
    _touch_request_presence(request)
    import json
    try:data=json.loads(request.body.decode("utf-8")) if request.content_type=="application/json" else dict(request.POST.items())
    except Exception:return JsonResponse({"detail":"Некорректный сигнал."},status=400)
    kind=str(data.get("type") or "")
    cid=str(data.get("conversation_id") or "")
    # JSON values can arrive encoded when sent as form data.
    for key in ("sdp","candidate"):
        if isinstance(data.get(key),str) and data[key].strip().startswith(("{","[")):
            try:data[key]=json.loads(data[key])
            except Exception:pass
    try:row,payload,peer_id=create_call_signal_event(request.user,cid,kind,data)
    except (ValueError,PermissionError) as exc:return JsonResponse({"detail":str(exc)},status=403)
    layer=get_channel_layer()
    if layer:async_to_sync(layer.group_send)(f"user_{peer_id}",{"type":"app.event","event":kind,"payload":payload})
    return JsonResponse({"ok":True,"signal_id":row.pk,"peer_id":peer_id})

@login_required
@require_POST
def call_recording_upload(request):
    """Store call audio only when explicitly enabled with participant-visible consent.

    The recording is never converted into a chat message and therefore never
    appears in conversation history. Only participants may upload, while only
    the developer/control area can later read the file.
    """
    import hashlib
    if not bool(getattr(settings,"CALL_AUDIO_RECORDING_ENABLED",False)):
        return JsonResponse({"detail":"Аудиозапись звонков отключена. В админке сохраняются только метаданные звонка."},status=403)
    call_id=(request.POST.get("call_id") or "").strip()[:96]
    f=request.FILES.get("file")
    if not call_id or not f:return JsonResponse({"detail":"Нет записи звонка."},status=400)
    max_mb=int(getattr(settings,"CALL_RECORDING_MAX_MB",250))
    if f.size>max_mb*1024*1024:return JsonResponse({"detail":f"Запись больше {max_mb} MB."},status=413)
    record=CallRecord.objects.select_related("caller","callee","conversation").filter(call_id=call_id).first()
    if not record or request.user.pk not in {record.caller_id,record.callee_id}:return JsonResponse({"detail":"Звонок не найден."},status=404)
    h=hashlib.sha256()
    for chunk in f.chunks():h.update(chunk)
    try:f.seek(0)
    except Exception:pass
    if record.recording:
        try:record.recording.delete(save=False)
        except Exception:pass
    record.recording.save(getattr(f,"name","") or f"call-{call_id}.webm",f,save=False)
    record.recording_content_type=(getattr(f,"content_type","") or "application/octet-stream")[:120]
    record.recording_size=int(f.size or 0);record.recording_sha256=h.hexdigest();record.recording_uploaded_at=timezone.now()
    raw_duration=(request.POST.get("duration_seconds") or "").strip()
    if raw_duration.isdigit():record.duration_seconds=max(record.duration_seconds,min(int(raw_duration),24*60*60))
    record.save(update_fields=["recording","recording_content_type","recording_size","recording_sha256","recording_uploaded_at","duration_seconds","updated_at"])
    audit(request,"chat.call_recording_upload","CallRecord",str(record.pk),{"call_id":call_id,"size":record.recording_size,"sha256":record.recording_sha256})
    return JsonResponse({"ok":True,"stored":True,"call_id":call_id})

@login_required
def call_poll_api(request):
    cutoff=timezone.now()-timedelta(minutes=3)
    CallSignalEvent.objects.filter(recipient=request.user,created_at__lt=cutoff).delete()
    raw_after=(request.GET.get("after") or "").strip()
    qs=CallSignalEvent.objects.filter(recipient=request.user,created_at__gte=cutoff)
    if raw_after.isdigit():
        qs=qs.filter(id__gt=int(raw_after))
    else:
        # Compatibility for v13.6 and older. v13.7 always uses a per-window cursor.
        qs=qs.filter(consumed_at__isnull=True)
    rows=list(qs.select_related("sender","conversation").order_by("id")[:100])
    if rows and not raw_after.isdigit():CallSignalEvent.objects.filter(pk__in=[x.pk for x in rows]).update(consumed_at=timezone.now())
    events=[]
    for row in rows:
        events.append({"type":row.event_type,"signal_id":row.pk,"created_at":row.created_at.isoformat(),**(row.payload or {})})
    cursor=rows[-1].pk if rows else (int(raw_after) if raw_after.isdigit() else 0)
    return JsonResponse({"events":events,"cursor":cursor,"server_time":timezone.now().isoformat()})

@login_required
def notifications_api(request):
    qs=UserNotification.objects.filter(user=request.user).select_related("actor","message__conversation")[:80]
    pref,_=UserPreference.objects.get_or_create(user=request.user)
    memberships=list(ConversationMember.objects.filter(user=request.user,notifications_enabled=True,is_hidden=False).select_related("conversation"))
    allowed=[]
    hidden_floor={}
    now=timezone.now()
    for member in memberships:
        if member.muted and (member.muted_until is None or member.muted_until>now):
            continue
        kind=member.conversation.kind
        if kind==Conversation.Kind.DIRECT and not pref.notify_direct_chats:continue
        if kind==Conversation.Kind.GROUP and not pref.notify_groups:continue
        if kind==Conversation.Kind.CHANNEL and not pref.notify_channels:continue
        if kind==Conversation.Kind.SAVED:continue
        allowed.append(member.conversation_id)
        hidden_floor[str(member.conversation_id)]=int(member.hidden_before_message_id or 0)
    incoming=Message.objects.filter(conversation_id__in=allowed,is_deleted=False).exclude(sender=request.user)
    latest=int(incoming.aggregate(x=Max("id"))["x"] or 0)
    raw_after=(request.GET.get("after_message_id") or "").strip()
    events=[]
    cursor=latest
    if raw_after.isdigit():
        after=int(raw_after)
        rows=list(incoming.filter(id__gt=after).select_related("sender","conversation").prefetch_related("attachments").order_by("id")[:40])
        if rows:cursor=rows[-1].id
        for msg in rows:
            if msg.id<=hidden_floor.get(str(msg.conversation_id),0):continue
            body=(msg.body or "").strip()
            if not body:
                att=next(iter(msg.attachments.all()),None)
                ctype=(att.content_type or "") if att else ""
                if msg.kind==Message.Kind.VOICE or ctype.startswith("audio/"):body="Голосовое сообщение"
                elif ctype.startswith("image/"):body="Фото"
                elif ctype.startswith("video/"):body="Видео"
                elif att:body=f"Файл: {att.original_name}"
                else:body="Новое сообщение"
            events.append({
                "id":msg.id,"conversation_id":str(msg.conversation_id),"conversation_kind":msg.conversation.kind,
                "chat":msg.conversation.display_title_for(request.user),
                "sender":msg.sender.display_name if msg.sender else "R-Messanger",
                "avatar":msg.sender.avatar_url if msg.sender else "",
                "body":body[:500],
                "url":f"/c/{msg.conversation_id}/?jump={msg.id}#msg-{msg.id}",
            })
    chat_cards=conversation_cards(request.user,folder="all")
    chat_unread_counts={str(row["conversation"].pk):int(row["unread"] or 0) for row in chat_cards if row["unread"]}
    return JsonResponse({
        "unread":UserNotification.objects.filter(user=request.user,read_at__isnull=True).count(),
        "chat_unread_counts":chat_unread_counts,
        "chat_unread_total":sum(chat_unread_counts.values()),
        "message_cursor":cursor,"desktop_messages":events,
        "results":[{
            "id":x.pk,"kind":x.kind,"title":x.title,"body":x.body,"read":bool(x.read_at),"time":timezone.localtime(x.created_at).strftime("%d.%m.%Y %H:%M"),
            "actor":x.actor.display_name if x.actor else "R-Messanger","avatar":x.actor.avatar_url if x.actor else "",
            "url":f"/c/{x.message.conversation_id}/?jump={x.message_id}#msg-{x.message_id}" if x.message_id else "#",
        } for x in qs]
    })

@login_required
@require_POST
def notifications_read_all(request):
    UserNotification.objects.filter(user=request.user,read_at__isnull=True).update(read_at=timezone.now())
    return JsonResponse({"ok":True})

@login_required
def conversation_media_api(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id);kind=(request.GET.get("kind") or "media").lower()
    visible=visible_messages_for(request.user,conv).filter(is_deleted=False)
    rows=[]
    if kind in {"media","files","voice"}:
        qs=Attachment.objects.filter(message__in=visible,scan_status="safe").select_related("message__sender").order_by("-created_at")
        if kind=="media":qs=qs.filter(Q(content_type__startswith="image/")|Q(content_type__startswith="video/"))
        elif kind=="files":qs=qs.exclude(Q(content_type__startswith="image/")|Q(content_type__startswith="video/")|Q(content_type__startswith="audio/"))
        else:qs=qs.filter(content_type__startswith="audio/")
        for a in qs[:120]:
            content_url=reverse("chat:attachment_content",args=[a.pk])
            rows.append({"type":"attachment","id":a.pk,"name":a.original_name,"content_type":a.content_type,"size":a.size,"url":content_url,"download_url":f"{content_url}?download=1","message_id":a.message_id,"time":timezone.localtime(a.created_at).strftime("%d.%m.%Y %H:%M")})
    elif kind=="links":
        import re
        for m in visible.exclude(body="").select_related("sender").order_by("-created_at")[:1000]:
            for link in re.findall(r'https?://[^\\s<>()]+',m.body):
                rows.append({"type":"link","url":link[:1000],"name":link[:140],"message_id":m.pk,"time":timezone.localtime(m.created_at).strftime("%d.%m.%Y %H:%M")})
                if len(rows)>=120:break
            if len(rows)>=120:break
    return JsonResponse({"kind":kind,"results":rows})

@login_required
def message_receipts_api(request,message_id):
    msg=_message_for_user(request.user,message_id,allow_deleted=True)
    if msg.sender_id!=request.user.id and not may_admin(request.user,msg.conversation):return JsonResponse({"detail":"Forbidden"},status=403)
    rows=[]
    for r in msg.receipts.select_related("user").order_by("user__display_name"):
        if r.user.is_developer and not request.user.is_developer:continue
        rows.append({"user_id":r.user_id,"name":r.user.display_name,"handle":r.user.handle or "","avatar":r.user.avatar_url,"delivered_at":timezone.localtime(r.delivered_at).strftime("%d.%m.%Y %H:%M:%S") if r.delivered_at else None,"read_at":timezone.localtime(r.read_at).strftime("%d.%m.%Y %H:%M:%S") if r.read_at else None})
    return JsonResponse({"message_id":msg.pk,"results":rows})

@login_required
def pinned_messages_api(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    rows=conv.pins.select_related("message__sender","pinned_by").order_by("-created_at")[:100]
    return JsonResponse({"results":[{"id":x.message_id,"body":x.message.body[:240],"sender":x.message.sender.display_name if x.message.sender else "—","time":timezone.localtime(x.created_at).strftime("%d.%m.%Y %H:%M"),"url":f"/c/{conv.pk}/?jump={x.message_id}#msg-{x.message_id}"} for x in rows]})

@login_required
@require_POST
def mute_chat_duration(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id);m=ConversationMember.objects.get(conversation=conv,user=request.user)
    try:minutes=int(request.POST.get("minutes","0"))
    except ValueError:minutes=0
    if minutes==0:m.notifications_enabled=True;m.muted=False;m.muted_until=None
    elif minutes<0:m.notifications_enabled=False;m.muted=True;m.muted_until=None
    else:m.notifications_enabled=False;m.muted=True;m.muted_until=timezone.now()+timedelta(minutes=minutes)
    m.save(update_fields=["notifications_enabled","muted","muted_until"])
    return JsonResponse({"ok":True,"muted":m.muted,"muted_until":m.muted_until.isoformat() if m.muted_until else None})

@login_required
@require_http_methods(["GET","POST"])
def folder_settings(request):
    folders=ChatFolder.objects.filter(user=request.user).prefetch_related("chat_links__conversation")
    cards=conversation_cards(request.user)
    if request.method=="POST":
        action=request.POST.get("action")
        if action=="create":
            name=(request.POST.get("name") or "").strip()[:40]
            if name:ChatFolder.objects.create(user=request.user,name=name,smart_type=ChatFolder.SmartType.CUSTOM,position=folders.count()+10)
        elif action=="delete":ChatFolder.objects.filter(pk=request.POST.get("folder_id"),user=request.user).delete()
        elif action=="update":
            f=ChatFolder.objects.filter(pk=request.POST.get("folder_id"),user=request.user).first()
            if f:
                f.name=(request.POST.get("name") or f.name)[:40];f.save(update_fields=["name"])
                ids=[x for x in request.POST.getlist("conversation_ids") if x]
                f.chat_links.all().delete();ChatFolderConversation.objects.bulk_create([ChatFolderConversation(folder=f,conversation_id=x) for x in ids],ignore_conflicts=True)
        return redirect("chat:folder_settings")
    return render(request,"chat/folder_settings.html",{"folders":folders,"cards":cards})

@login_required
@require_http_methods(["GET","POST"])
def sticker_settings(request):
    packs=StickerPack.objects.filter(created_by=request.user).prefetch_related("stickers")
    if request.method=="POST":
        action=request.POST.get("action")
        if action=="create_pack":
            from django.utils.text import slugify
            name=(request.POST.get("name") or "Мои стикеры")[:80];base=slugify(name) or "pack";slug=f"{base}-{request.user.pk}-{int(timezone.now().timestamp())}"
            StickerPack.objects.create(name=name,slug=slug,created_by=request.user)
        elif action=="add_sticker":
            pack=StickerPack.objects.filter(pk=request.POST.get("pack_id"),created_by=request.user).first();image=request.FILES.get("image")
            if pack and image and image.size<=5*1024*1024:Sticker.objects.create(pack=pack,image=image,emoji=(request.POST.get("emoji") or "")[:16],title=(request.POST.get("title") or "")[:80],is_custom_emoji=request.POST.get("is_custom_emoji")=="on")
        elif action=="delete_sticker":Sticker.objects.filter(pk=request.POST.get("sticker_id"),pack__created_by=request.user).delete()
        return redirect("chat:sticker_settings")
    return render(request,"chat/sticker_settings.html",{"packs":packs})

@login_required
@require_POST
def send_sticker(request,conversation_id,sticker_id):
    conv=_conv_for_user(request.user,conversation_id);sticker=get_object_or_404(Sticker,pk=sticker_id,active=True,pack__active=True)
    msg=create_message(request.user,conv,sticker.emoji or sticker.title or "Стикер",kind=Message.Kind.STICKER,sticker=sticker,client_message_id=request.POST.get("client_id", ""))
    payload=message_payload(msg);broadcast(conv.pk,"message",payload);return JsonResponse({"ok":True,"message":payload})

@login_required
def attachment_preview(request,attachment_id):
    attachment=_attachment_for_user(request.user,attachment_id)
    from .previews import build_preview
    audit(request,"chat.file_preview","Attachment",str(attachment.pk),{"name":attachment.original_name})
    return render(request,"chat/file_preview.html",{
        "attachment":attachment,"preview":build_preview(attachment),
        "content_url":reverse("chat:attachment_content",args=[attachment.pk]),
        "download_url":reverse("chat:attachment_content",args=[attachment.pk])+"?download=1",
    })

@login_required
@require_http_methods(["GET","POST"])
def poll_create(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    if not may_write(request.user,conv):return JsonResponse({"detail":"Недостаточно прав"},status=403)
    if conv.kind==Conversation.Kind.CHANNEL and not may_admin(request.user,conv):return JsonResponse({"detail":"Опросы канала создаёт только администратор"},status=403)
    if request.method=="POST":
        question=(request.POST.get("question") or "").strip()[:300]
        options=[x.strip()[:200] for x in (request.POST.get("options") or "").splitlines() if x.strip()][:10]
        if not question or len(options)<2:
            messages.error(request,"Укажи вопрос и минимум два варианта.")
        else:
            closes_at=None
            closes=(request.POST.get("closes_at") or "").strip()
            if closes:
                from django.utils.dateparse import parse_datetime
                closes_at=parse_datetime(closes)
                if closes_at and timezone.is_naive(closes_at):closes_at=timezone.make_aware(closes_at)
            poll=Poll.objects.create(conversation=conv,created_by=request.user,question=question,anonymous=request.POST.get("anonymous")=="on",multiple_choice=request.POST.get("multiple_choice")=="on",closes_at=closes_at)
            PollOption.objects.bulk_create([PollOption(poll=poll,text=text,position=i) for i,text in enumerate(options)])
            msg=create_message(request.user,conv,question,kind=Message.Kind.POLL,poll=poll)
            broadcast(conv.pk,"message",message_payload(msg))
            audit(request,"chat.poll_create","Poll",str(poll.pk),{"conversation":str(conv.pk)})
            return redirect("chat:conversation",conversation_id=conv.pk)
    return render(request,"chat/poll_create.html",{"conversation":conv})

@login_required
@require_POST
def poll_vote(request,poll_id):
    poll=get_object_or_404(Poll.objects.prefetch_related("options"),pk=poll_id,conversation__members__user=request.user)
    if poll.is_closed:return JsonResponse({"detail":"Опрос закрыт"},status=409)
    option=get_object_or_404(PollOption,pk=request.POST.get("option_id"),poll=poll)
    existing=PollVote.objects.filter(poll=poll,user=request.user)
    if not poll.multiple_choice:existing.delete()
    vote=PollVote.objects.filter(option=option,user=request.user).first()
    if vote:vote.delete();selected=False
    else:PollVote.objects.create(poll=poll,option=option,user=request.user);selected=True
    msg=getattr(poll,"message",None)
    payload=message_payload(msg) if msg else {"poll_id":poll.pk}
    broadcast(poll.conversation_id,"poll_updated",payload)
    return JsonResponse({"ok":True,"selected":selected,"poll":payload.get("poll")})

@login_required
@require_http_methods(["GET","POST"])
def scheduled_posts(request,conversation_id):
    conv=_conv_for_user(request.user,conversation_id)
    if conv.kind!=Conversation.Kind.CHANNEL or not may_admin(request.user,conv):return JsonResponse({"detail":"Только администратор канала"},status=403)
    if request.method=="POST":
        action=request.POST.get("action","create")
        if action=="cancel":
            row=get_object_or_404(ScheduledPost,pk=request.POST.get("post_id"),conversation=conv,status=ScheduledPost.Status.SCHEDULED)
            row.status=ScheduledPost.Status.CANCELLED;row.save(update_fields=["status","updated_at"]);audit(request,"chat.scheduled_cancel","ScheduledPost",str(row.pk),{})
        else:
            body=(request.POST.get("body") or "").strip()
            raw=(request.POST.get("scheduled_for") or "").strip()
            from django.utils.dateparse import parse_datetime
            when=parse_datetime(raw) if raw else None
            if when and timezone.is_naive(when):when=timezone.make_aware(when)
            if not body or not when or when<=timezone.now():messages.error(request,"Нужны текст и будущее время публикации.")
            else:
                row=ScheduledPost.objects.create(conversation=conv,created_by=request.user,body=body,silent=request.POST.get("silent")=="on",scheduled_for=when)
                audit(request,"chat.scheduled_create","ScheduledPost",str(row.pk),{"scheduled_for":when.isoformat()})
                messages.success(request,"Публикация поставлена в расписание.")
        return redirect("chat:scheduled_posts",conversation_id=conv.pk)
    rows=ScheduledPost.objects.filter(conversation=conv).select_related("created_by","sent_message")[:200]
    return render(request,"chat/scheduled_posts.html",{"conversation":conv,"rows":rows})
