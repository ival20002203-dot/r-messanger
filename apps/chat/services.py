from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.db.models import Q
import re
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import UserBlock
from .models import ChatDeletionEvent,ChatFolder,ChatFolderConversation,Conversation,ConversationMember,Message,MessageHiddenFor,MessageMention,UserNotification,MessageReceipt,MessagePin,Poll,PollOption,PollVote,ScheduledPost,CallSignalEvent,CallRecord

def membership(user,conversation):
    return ConversationMember.objects.filter(user=user,conversation=conversation).first()

def pair_is_blocked(a,b):
    return UserBlock.objects.filter(
        Q(blocker=a,blocked=b)|Q(blocker=b,blocked=a)
    ).exists()

def may_write(user,conversation):
    if user.is_suspended or not user.can_send_messages:return False
    m=membership(user,conversation)
    if not m or not m.can_write:return False
    if conversation.kind==Conversation.Kind.DIRECT:
        peer=conversation.peer_for(user)
        if peer and pair_is_blocked(user,peer):return False
    if conversation.kind==Conversation.Kind.CHANNEL:
        return m.role in {ConversationMember.Role.OWNER,ConversationMember.Role.ADMIN}
    return True

def may_admin(user,conversation):
    m=membership(user,conversation)
    return bool(m and m.role in {ConversationMember.Role.OWNER,ConversationMember.Role.ADMIN})

def visible_messages_for(user,conversation):
    qs=conversation.messages.exclude(hidden_for__user=user)
    m=membership(user,conversation)
    if m and m.hidden_before_message_id:
        qs=qs.filter(id__gt=m.hidden_before_message_id)
    return qs

def revive_members_for_new_message(conversation):
    ConversationMember.objects.filter(conversation=conversation,is_hidden=True).update(is_hidden=False)

def get_or_create_direct(a,b):
    for conv in Conversation.objects.filter(kind=Conversation.Kind.DIRECT,members__user=a).filter(members__user=b).distinct():
        if conv.members.count()==2:
            ConversationMember.objects.filter(conversation=conv,user=a).update(is_hidden=False,is_archived=False)
            return conv,False
    with transaction.atomic():
        conv=Conversation.objects.create(kind=Conversation.Kind.DIRECT,created_by=a)
        ConversationMember.objects.bulk_create([
            ConversationMember(conversation=conv,user=a,role=ConversationMember.Role.OWNER),
            ConversationMember(conversation=conv,user=b,role=ConversationMember.Role.MEMBER),
        ])
    return conv,True

def get_saved_conversation(user):
    conv=Conversation.objects.filter(kind=Conversation.Kind.SAVED,members__user=user).first()
    if conv:
        if conv.title!="Избранное":
            Conversation.objects.filter(pk=conv.pk).update(title="Избранное")
            conv.title="Избранное"
        return conv
    with transaction.atomic():
        conv=Conversation.objects.create(kind=Conversation.Kind.SAVED,title="Избранное",created_by=user)
        ConversationMember.objects.create(conversation=conv,user=user,role=ConversationMember.Role.OWNER)
    return conv

def _create_receipts_and_notifications(msg):
    recipients=list(msg.conversation.members.exclude(user=msg.sender).select_related("user"))
    MessageReceipt.objects.bulk_create([MessageReceipt(message=msg,user=m.user) for m in recipients],ignore_conflicts=True)
    body=msg.body or ""
    handles=set(re.findall(r"(?<![\w@])@([a-z0-9_]{4,32})",body.lower()))
    all_mention="all" in handles or "everyone" in handles
    if all_mention:
        handles.discard("all");handles.discard("everyone")
    users={m.user.handle:m.user for m in recipients if m.user.handle}
    mentioned=[]
    for handle in handles:
        u=users.get(handle)
        if u:
            MessageMention.objects.get_or_create(message=msg,user=u,defaults={"is_all":False});mentioned.append(u)
    if all_mention:
        for m in recipients:
            MessageMention.objects.get_or_create(message=msg,user=m.user,defaults={"is_all":True});mentioned.append(m.user)
    seen=set()
    for u in mentioned:
        if u.pk in seen:continue
        seen.add(u.pk)
        UserNotification.objects.create(user=u,kind=UserNotification.Kind.MENTION,message=msg,actor=msg.sender,title=f"{msg.sender.display_name if msg.sender else 'R-Messanger'} упомянул(а) вас",body=body[:500])
    if msg.reply_to and msg.reply_to.sender_id and msg.reply_to.sender_id!=msg.sender_id:
        UserNotification.objects.create(user=msg.reply_to.sender,kind=UserNotification.Kind.REPLY,message=msg,actor=msg.sender,title="Ответ на ваше сообщение",body=body[:500])

def mark_delivered(user,conversation):
    now=timezone.now()
    MessageReceipt.objects.filter(user=user,message__conversation=conversation,delivered_at__isnull=True).update(delivered_at=now)

def mark_all_delivered(user):
    MessageReceipt.objects.filter(user=user,delivered_at__isnull=True).update(delivered_at=timezone.now())

def receipt_summary(message):
    qs=message.receipts.all()
    return {"total":qs.count(),"delivered":qs.filter(delivered_at__isnull=False).count(),"read":qs.filter(read_at__isnull=False).count()}


def server_timestamp_parts(value):
    """Return one unambiguous server timestamp for every client surface.

    The database stores aware UTC values when ``USE_TZ`` is enabled.  Older
    imported rows can still be naive, so interpret those in the configured
    server timezone before serialising them.  ``time_hm`` is intentionally
    included: the browser must not recalculate chat clocks from its own
    timezone or a user's incorrect workstation clock.
    """
    if value is None:
        return {
            "created_at": None,
            "created_at_ms": None,
            "time_hm": "",
            "time_dhm": "",
            "created_at_local": None,
        }
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())
    local = timezone.localtime(value)
    return {
        "created_at": value.isoformat(),
        "created_at_ms": int(value.timestamp() * 1000),
        "time_hm": local.strftime("%H:%M"),
        "time_dhm": local.strftime("%d.%m.%Y %H:%M"),
        "created_at_local": local.isoformat(),
    }

def _member_notification_allowed(member,now=None):
    now=now or timezone.now()
    if member.conversation.kind==Conversation.Kind.SAVED or member.is_hidden:
        return False
    if not member.notifications_enabled:
        return False
    if member.muted and (member.muted_until is None or member.muted_until>now):
        return False
    return True


def _broadcast_message_to_user_clients(message_id):
    """Push a new message to every member's global app websocket."""
    try:
        msg=(Message.objects.select_related("sender","conversation","reply_to__sender","forwarded_from__sender")
             .prefetch_related("attachments","reactions__user","receipts","poll__options__votes").get(pk=message_id))
        layer=get_channel_layer()
        if not layer:return
        send=async_to_sync(layer.group_send)
        base=message_payload(msg)
        now=timezone.now()
        members=list(msg.conversation.members.select_related("user","conversation"))
        for member in members:
            payload=dict(base)
            payload.update({
                "conversation_kind":msg.conversation.kind,
                "chat":msg.conversation.display_title_for(member.user),
                "url":f"/c/{msg.conversation_id}/?jump={msg.pk}#msg-{msg.pk}",
                "notify_allowed":bool(member.user_id!=msg.sender_id and _member_notification_allowed(member,now)),
                "recipient_id":member.user_id,
            })
            send(f"user_{member.user_id}",{"type":"app.event","event":"message","payload":payload})
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to broadcast global message event %s",message_id)


def broadcast_message_to_user_clients(msg):
    # Works correctly both in normal requests and inside transaction.atomic().
    transaction.on_commit(lambda mid=msg.pk:_broadcast_message_to_user_clients(mid))
    try:
        from apps.accounts.push import send_message_push_async
        transaction.on_commit(lambda m=msg:send_message_push_async(m))
    except Exception:
        pass


def _broadcast_message_update_to_user_clients(message_id):
    """Push a silent message refresh (scan/preview/reaction state) to all app windows."""
    try:
        msg=(Message.objects.select_related("sender","conversation","reply_to__sender","forwarded_from__sender")
             .prefetch_related("attachments","reactions__user","receipts","poll__options__votes").get(pk=message_id))
        layer=get_channel_layer()
        if not layer:return
        send=async_to_sync(layer.group_send)
        base=message_payload(msg)
        for member in msg.conversation.members.select_related("user"):
            payload=dict(base)
            payload.update({
                "conversation_kind":msg.conversation.kind,
                "chat":msg.conversation.display_title_for(member.user),
                "url":f"/c/{msg.conversation_id}/?jump={msg.pk}#msg-{msg.pk}",
                "notify_allowed":False,
                "recipient_id":member.user_id,
            })
            send(f"user_{member.user_id}",{"type":"app.event","event":"message_updated","payload":payload})
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to broadcast global message update %s",message_id)

def broadcast_message_update_to_user_clients(msg):
    transaction.on_commit(lambda mid=msg.pk:_broadcast_message_update_to_user_clients(mid))

def _update_call_record_from_signal(sender,peer,conversation,call_id,event_type,data):
    now=timezone.now();reason=str((data or {}).get("reason") or "")[:80]
    record=CallRecord.objects.filter(call_id=call_id).first()
    if event_type==CallSignalEvent.EventType.OFFER:
        if record is None:
            record=CallRecord.objects.create(call_id=call_id,conversation=conversation,caller=sender,callee=peer,status=CallRecord.Status.RINGING,started_at=now)
        else:
            changed=[]
            if record.conversation_id!=conversation.pk:record.conversation=conversation;changed.append("conversation")
            if record.caller_id is None:record.caller=sender;changed.append("caller")
            if record.callee_id is None:record.callee=peer;changed.append("callee")
            if changed:record.save(update_fields=changed+["updated_at"])
        return record
    if record is None:
        # Signals can be delivered after a process restart. Preserve an admin trace
        # even if the original OFFER row was already pruned.
        record=CallRecord.objects.create(call_id=call_id,conversation=conversation,caller=peer if event_type==CallSignalEvent.EventType.ANSWER else sender,callee=sender if event_type==CallSignalEvent.EventType.ANSWER else peer,started_at=now)
    fields=[]
    if event_type==CallSignalEvent.EventType.ANSWER:
        if not record.connected_at:record.connected_at=now;fields.append("connected_at")
        record.status=CallRecord.Status.CONNECTED;fields.append("status")
    elif event_type in {CallSignalEvent.EventType.END,CallSignalEvent.EventType.REJECT,CallSignalEvent.EventType.BUSY}:
        if not record.ended_at:record.ended_at=now;fields.append("ended_at")
        record.end_reason=reason;fields.append("end_reason")
        if event_type==CallSignalEvent.EventType.REJECT:record.status=CallRecord.Status.REJECTED
        elif event_type==CallSignalEvent.EventType.BUSY:record.status=CallRecord.Status.BUSY
        elif record.connected_at:record.status=CallRecord.Status.ENDED
        elif reason in {"timeout","no_answer","missed"}:record.status=CallRecord.Status.MISSED
        elif reason in {"media_error","failed","network"}:record.status=CallRecord.Status.FAILED
        else:record.status=CallRecord.Status.MISSED
        fields.append("status")
        if record.connected_at and record.ended_at:
            record.duration_seconds=max(0,int((record.ended_at-record.connected_at).total_seconds()));fields.append("duration_seconds")
    if fields:record.save(update_fields=list(dict.fromkeys(fields+["updated_at"])))
    return record

def create_call_signal_event(sender,conversation_id,event_type,data):
    """Validate, persist and return a call signal for WS + HTTP fallback delivery."""
    allowed={x for x,_ in CallSignalEvent.EventType.choices}
    if event_type not in allowed:
        raise ValueError("Некорректный тип сигнала звонка.")
    conversation=Conversation.objects.filter(pk=conversation_id,kind=Conversation.Kind.DIRECT).first()
    if not conversation or not getattr(sender,"can_make_calls",False):
        raise PermissionError("Звонок недоступен.")
    if not ConversationMember.objects.filter(conversation=conversation,user=sender).exists():
        raise PermissionError("Звонок недоступен.")
    peer=conversation.peer_for(sender)
    if not peer or not getattr(peer,"can_make_calls",False) or pair_is_blocked(sender,peer):
        raise PermissionError("Звонок недоступен.")
    call_id=str((data or {}).get("call_id") or "").strip()[:96]
    if not call_id:raise ValueError("Некорректный идентификатор звонка.")
    payload={
        "conversation_id":str(conversation.pk),"call_id":call_id,
        "from_user":sender.pk,"from_name":sender.display_name,
        "from_avatar":getattr(sender,"avatar_url","") or "",
    }
    for key in ("sdp","candidate","reason"):
        if key in (data or {}):payload[key]=(data or {})[key]
    # Video calls are intentionally not part of R-Mes. Never trust an old
    # client to turn a call into a camera session via the signaling payload.
    payload["media"]="audio"
    cutoff=timezone.now()-timedelta(minutes=10)
    CallSignalEvent.objects.filter(created_at__lt=cutoff).delete()
    if event_type==CallSignalEvent.EventType.ICE:
        # WebSocket and HTTP fallback may deliver the same ICE candidate. Keep one
        # durable row so polling clients receive it exactly once.
        row=CallSignalEvent.objects.filter(
            recipient=peer,sender=sender,conversation=conversation,call_id=call_id,
            event_type=event_type,payload=payload,
        ).order_by("-id").first()
        created=row is None
        if row is None:
            row=CallSignalEvent.objects.create(recipient=peer,sender=sender,conversation=conversation,call_id=call_id,event_type=event_type,payload=payload)
    else:
        row,created=CallSignalEvent.objects.get_or_create(
            recipient=peer,sender=sender,call_id=call_id,event_type=event_type,
            defaults={"conversation":conversation,"payload":payload},
        )
        if not created and row.payload!=payload:
            row.payload=payload;row.conversation=conversation;row.save(update_fields=["payload","conversation"])
    # Keep an admin-only lifecycle row for every call. This does not create a chat message.
    try:
        _update_call_record_from_signal(sender,peer,conversation,call_id,event_type,data)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to update CallRecord %s",call_id)
    payload={**payload,"signal_id":row.pk,"created_at":row.created_at.isoformat()}
    try:
        from apps.audit.services import audit_actor
        if event_type!=CallSignalEvent.EventType.ICE and created:
            audit_actor(sender,f"chat.{event_type}","Conversation",str(conversation.pk),{"call_id":call_id,"peer_id":peer.pk,"media":"audio"})
    except Exception:
        pass
    return row,payload,peer.pk


def create_message(user,conversation,body,reply_to=None,forwarded_from=None,kind=Message.Kind.TEXT,client_message_id="",sticker=None,poll=None,notify=True,broadcast_realtime=True):
    body=(body or "").strip()
    if not body and not forwarded_from and not sticker and not poll and kind not in {Message.Kind.FILE,Message.Kind.VOICE}:raise ValueError("Пустое сообщение.")
    client_message_id=(client_message_id or "")[:64]
    if client_message_id:
        existing=Message.objects.filter(sender=user,client_message_id=client_message_id).first()
        if existing:return existing
    if len(body)>10000:raise ValueError("Максимум 10 000 символов.")
    if not may_write(user,conversation):raise PermissionError("Отправка сообщений недоступна.")
    if reply_to and reply_to.conversation_id!=conversation.id:reply_to=None
    if kind==Message.Kind.TEXT and body:
        try:
            from apps.operations.services import enforce_message_policy
            enforce_message_policy(user,conversation,body)
        except PermissionError:
            raise
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Anti-spam policy hook failed")
    msg=Message.objects.create(conversation=conversation,sender=user,body=body,reply_to=reply_to,forwarded_from=forwarded_from,kind=kind,client_message_id=client_message_id,sticker=sticker,poll=poll)
    if notify:_create_receipts_and_notifications(msg)
    else:
        recipients=list(msg.conversation.members.exclude(user=msg.sender).select_related("user"))
        MessageReceipt.objects.bulk_create([MessageReceipt(message=msg,user=m.user) for m in recipients],ignore_conflicts=True)
    revive_members_for_new_message(conversation)
    Conversation.objects.filter(pk=conversation.pk).update(updated_at=msg.created_at)
    # Push the message to app clients before non-blocking policy bookkeeping. This keeps
    # receive latency Telegram-like even when security/audit tables are busy.
    if broadcast_realtime:broadcast_message_to_user_clients(msg)
    try:
        from apps.securitycenter.services import scan_message_dlp
        scan_message_dlp(msg)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("DLP hook failed for message %s",msg.pk)
    try:
        from apps.moderation.services import moderate_text_message
        moderate_text_message(msg)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Text moderation hook failed for message %s",msg.pk)
    return msg

def _broadcast_read_receipt(payload,sender_ids):
    layer=get_channel_layer()
    if not layer:return
    send=async_to_sync(layer.group_send)
    send(f"chat_{payload['conversation_id']}",{"type":"chat.event","event":"read","payload":payload})
    for sender_id in set(sender_ids):
        send(f"user_{sender_id}",{"type":"app.event","event":"read","payload":payload})


def mark_read(user,conversation,message=None,broadcast_realtime=True):
    m=membership(user,conversation)
    if not m:return None
    if message is None:message=visible_messages_for(user,conversation).order_by("-id").first()
    if message and (not m.last_read_message_id or message.id>m.last_read_message_id):
        m.last_read_message=message;m.save(update_fields=["last_read_message"])
        now=timezone.now()
        receipt_qs=MessageReceipt.objects.filter(user=user,message__conversation=conversation,message_id__lte=message.id,read_at__isnull=True)
        sender_ids=list(receipt_qs.exclude(message__sender_id__isnull=True).values_list("message__sender_id",flat=True).distinct())
        receipt_qs.update(read_at=now,delivered_at=now)
        UserNotification.objects.filter(user=user,message__conversation=conversation,message_id__lte=message.id,read_at__isnull=True).update(read_at=now)
        payload={"conversation_id":str(conversation.pk),"user_id":user.pk,"message_id":message.pk,"read_at":now.isoformat()}
        if broadcast_realtime:
            transaction.on_commit(lambda p=payload,s=sender_ids:_broadcast_read_receipt(p,s))
        return payload
    return None

def delete_chat_for_user(actor,conversation,for_everyone=False,clear_history=False,scope=None):
    last_id=conversation.messages.order_by("-id").values_list("id",flat=True).first()
    affected=[];protected=[]
    members=list(conversation.members.select_related("user"))
    scope=scope or (ChatDeletionEvent.Scope.EVERYONE if for_everyone else ChatDeletionEvent.Scope.SELF)
    if scope not in {ChatDeletionEvent.Scope.SELF,ChatDeletionEvent.Scope.PEER,ChatDeletionEvent.Scope.EVERYONE}:
        scope=ChatDeletionEvent.Scope.SELF
    if scope==ChatDeletionEvent.Scope.PEER:
        if not actor.is_developer or conversation.kind!=Conversation.Kind.DIRECT:
            raise PermissionError("Удаление только у собеседника доступно разработчику в личном чате.")
        targets=[m for m in members if m.user_id!=actor.id]
    elif scope==ChatDeletionEvent.Scope.EVERYONE and conversation.kind==Conversation.Kind.DIRECT:
        targets=members
    else:
        targets=[m for m in members if m.user_id==actor.id]
        scope=ChatDeletionEvent.Scope.SELF

    protected_chat=conversation.kind==Conversation.Kind.DIRECT and any(m.user.is_developer for m in members)
    for m in targets:
        # A regular participant cannot erase the developer's copy. The developer
        # can explicitly remove their own copy, the peer's copy, or both.
        if protected_chat and m.user.is_developer and not actor.is_developer:
            protected.append(m.user_id)
            continue
        m.is_hidden=False if clear_history else True
        m.is_archived=False
        if last_id:
            m.hidden_before_message_id=max(m.hidden_before_message_id or 0,last_id)
        m.save(update_fields=["is_hidden","is_archived","hidden_before_message_id"])
        affected.append(m.user_id)

    event=ChatDeletionEvent.objects.create(
        conversation=conversation,actor=actor,action=ChatDeletionEvent.Action.CLEAR if clear_history else ChatDeletionEvent.Action.DELETE,
        scope=scope,through_message_id=last_id,
        affected_user_ids=affected,protected_developer_ids=protected,
    )
    return event


def delete_message_for_user(actor,message,scope="everyone",reason="user request"):
    """Apply deletion with protected-copy rules and developer-only peer scope."""
    if scope=="self":
        MessageHiddenFor.objects.get_or_create(message=message,user=actor)
        return {"scope":"self","hidden_for_user_ids":[actor.pk],"protected_developer_ids":[]}
    members=list(message.conversation.members.select_related("user"))
    if scope=="peer":
        if not actor.is_developer or message.conversation.kind!=Conversation.Kind.DIRECT:
            raise PermissionError("Удаление только у собеседника доступно разработчику в личном чате.")
        hidden_ids=[m.user_id for m in members if m.user_id!=actor.pk]
        MessageHiddenFor.objects.bulk_create(
            [MessageHiddenFor(message=message,user_id=uid) for uid in hidden_ids],ignore_conflicts=True,
        )
        return {"scope":"peer","hidden_for_user_ids":hidden_ids,"protected_developer_ids":[]}
    developer_ids=[m.user_id for m in members if m.user.is_developer]
    if message.conversation.kind==Conversation.Kind.DIRECT and developer_ids and not actor.is_developer:
        hidden_ids=[m.user_id for m in members if not m.user.is_developer]
        MessageHiddenFor.objects.bulk_create(
            [MessageHiddenFor(message=message,user_id=uid) for uid in hidden_ids],ignore_conflicts=True,
        )
        return {"scope":"everyone","hidden_for_user_ids":hidden_ids,"protected_developer_ids":developer_ids}
    message.soft_delete(actor,reason)
    return {"scope":"everyone","hidden_for_user_ids":[m.user_id for m in members],"protected_developer_ids":[]}

def conversation_cards(user,query="",folder="all"):
    ms=ConversationMember.objects.filter(user=user,conversation__is_archived=False,is_hidden=False).select_related(
        "conversation","conversation__pinned_message"
    ).prefetch_related("conversation__members__user")
    if folder=="archived":
        ms=ms.filter(is_archived=True)
    else:
        ms=ms.filter(is_archived=False)
        if folder=="direct":ms=ms.filter(conversation__kind=Conversation.Kind.DIRECT)
        elif folder=="groups":ms=ms.filter(conversation__kind=Conversation.Kind.GROUP)
        elif folder=="channels":ms=ms.filter(conversation__kind=Conversation.Kind.CHANNEL)
        elif folder=="saved":ms=ms.filter(conversation__kind=Conversation.Kind.SAVED)
        elif folder.startswith("f-") and folder[2:].isdigit():
            ids=ChatFolderConversation.objects.filter(folder_id=int(folder[2:]),folder__user=user).values_list("conversation_id",flat=True)
            ms=ms.filter(conversation_id__in=ids)
    cards=[]
    q=(query or "").strip()
    normalized_q=q.lstrip("@")
    for m in ms:
        c=m.conversation
        msgs=visible_messages_for(user,c)
        # IDs are not a clock (imports/retries can allocate them out of order),
        # therefore the sidebar must choose the newest message by its server
        # timestamp first.
        last=msgs.select_related("sender").order_by("-created_at","-id").first()
        unread_q=msgs.exclude(sender=user)
        if m.last_read_message_id:unread_q=unread_q.filter(id__gt=m.last_read_message_id)
        unread=unread_q.count()
        title=c.display_title_for(user)
        if folder=="unread" and not unread:continue
        if q:
            ql=normalized_q.lower()
            peer=c.peer_for(user)
            searchable=" ".join(filter(None,[title,peer.email if peer else "",peer.handle if peer else "",("" if (last and last.is_deleted) else (last.body if last else ""))])).lower()
            if ql not in searchable:continue
        cards.append({"conversation":c,"membership":m,"title":title,"last":last,"unread":unread,"peer":c.peer_for(user)})
    cards.sort(key=lambda x:(not x["membership"].is_pinned,-x["conversation"].updated_at.timestamp()))
    return cards

def message_payload(msg):
    reactions={}
    for r in msg.reactions.select_related("user").all():
        reactions.setdefault(r.emoji,[]).append(r.user_id)
    atts=[]
    for a in msg.attachments.all():
        preview_allowed=a.scan_status!="infected"
        content_url=reverse("chat:attachment_content",args=[a.pk]) if preview_allowed else ""
        atts.append({
            "id":a.pk,"url":content_url,"download_url":f"{content_url}?download=1" if content_url else "",
            "preview_url":reverse("chat:attachment_preview",args=[a.pk]) if preview_allowed else "",
            "name":a.original_name,"size":a.size,"content_type":a.content_type,"scan_status":a.scan_status,
            "scan_signature":a.scan_signature if a.scan_status=="infected" else "",
        })
    timestamp = server_timestamp_parts(msg.created_at)
    return {
        "id":msg.pk,"conversation_id":str(msg.conversation_id),"kind":msg.kind,"client_message_id":msg.client_message_id,
        "body":"" if msg.is_deleted else msg.body,"is_deleted":msg.is_deleted,
        # Keep both the canonical instant and the already-localised display
        # value.  Clients use time_hm for the visible clock and only use the
        # epoch for ordering/duration calculations.
        "edited":bool(msg.edited_at),**timestamp,
        "sender":None if not msg.sender else {
            "id":msg.sender_id,"name":msg.sender.display_name,"email":msg.sender.email,
            "initials":msg.sender.initials,"avatar":msg.sender.avatar_url,
        },
        "reply_to":None if not msg.reply_to else {"id":msg.reply_to_id,"body":msg.reply_to.body[:140],"sender":str(msg.reply_to.sender) if msg.reply_to.sender else "—"},
        "forwarded_from":None if not msg.forwarded_from else {"id":msg.forwarded_from_id,"sender":str(msg.forwarded_from.sender) if msg.forwarded_from.sender else "—"},
        "reactions":reactions,"attachments":atts,"receipts":receipt_summary(msg),
        "pinned":msg.pin_records.exists(),
        "sticker":None if not msg.sticker else {"id":msg.sticker_id,"emoji":msg.sticker.emoji,"title":msg.sticker.title,"url":msg.sticker.image.url},
        "poll":None if not msg.poll else {
            "id":msg.poll_id,"question":msg.poll.question,"anonymous":msg.poll.anonymous,"multiple_choice":msg.poll.multiple_choice,
            "closed":msg.poll.is_closed,"closes_at":msg.poll.closes_at.isoformat() if msg.poll.closes_at else None,
            "options":[{"id":o.pk,"text":o.text,"votes":o.votes.count()} for o in msg.poll.options.all()],
        },
    }

def broadcast(conversation_id,event,payload):
    layer=get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(f"chat_{conversation_id}",{"type":"chat.event","event":event,"payload":payload})


def process_due_scheduled_post(now=None):
    from django.db import transaction
    from django.utils import timezone
    now=now or timezone.now()
    with transaction.atomic():
        row=(ScheduledPost.objects.select_for_update(skip_locked=True).select_related("conversation","created_by").filter(status=ScheduledPost.Status.SCHEDULED,scheduled_for__lte=now).order_by("scheduled_for").first())
        if not row:return None
        try:
            msg=create_message(row.created_by,row.conversation,row.body,kind=Message.Kind.TEXT,notify=not row.silent)
            row.sent_message=msg;row.status=ScheduledPost.Status.SENT;row.last_error="";row.save(update_fields=["sent_message","status","last_error","updated_at"])
            broadcast(row.conversation_id,"message",message_payload(msg))
        except Exception as exc:
            row.status=ScheduledPost.Status.ERROR;row.last_error=str(exc)[:4000];row.save(update_fields=["status","last_error","updated_at"])
        return row
