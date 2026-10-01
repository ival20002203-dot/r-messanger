"""Optional native push delivery for R-Mes mobile clients.

Push is deliberately best-effort: chat delivery never depends on FCM/APNs.
Configure provider credentials in .env; without credentials this module is a no-op.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log=logging.getLogger(__name__)


def _fcm_send(token,title,body,data):
    path=str(getattr(settings,"FCM_SERVICE_ACCOUNT_FILE","") or "").strip()
    project=str(getattr(settings,"FCM_PROJECT_ID","") or "").strip()
    if not path or not project or not Path(path).exists():return False
    try:
        import requests
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        creds=service_account.Credentials.from_service_account_file(path,scopes=["https://www.googleapis.com/auth/firebase.messaging"])
        creds.refresh(Request())
        payload={"message":{"token":token,"notification":{"title":title,"body":body},"data":{str(k):str(v) for k,v in (data or {}).items()},"android":{"priority":"high","notification":{"channel_id":"rmes_messages","sound":"default"}}}}
        r=requests.post(f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",headers={"Authorization":f"Bearer {creds.token}","Content-Type":"application/json"},json=payload,timeout=4)
        if r.status_code>=300:log.warning("FCM push failed %s %s",r.status_code,r.text[:300]);return False
        return True
    except Exception:
        log.exception("FCM push failed");return False


def _apns_send(token,title,body,data):
    key_file=str(getattr(settings,"APNS_KEY_FILE","") or "").strip()
    key_id=str(getattr(settings,"APNS_KEY_ID","") or "").strip()
    team_id=str(getattr(settings,"APNS_TEAM_ID","") or "").strip()
    topic=str(getattr(settings,"APNS_BUNDLE_ID","uz.rmes.ios") or "uz.rmes.ios").strip()
    if not all([key_file,key_id,team_id,topic]) or not Path(key_file).exists():return False
    try:
        import jwt,httpx
        key=Path(key_file).read_text()
        auth=jwt.encode({"iss":team_id,"iat":int(time.time())},key,algorithm="ES256",headers={"kid":key_id})
        payload={"aps":{"alert":{"title":title,"body":body},"sound":"default","badge":1},"rmes":data or {}}
        host="https://api.sandbox.push.apple.com" if getattr(settings,"APNS_USE_SANDBOX",True) else "https://api.push.apple.com"
        with httpx.Client(http2=True,timeout=4) as client:
            r=client.post(f"{host}/3/device/{token}",headers={"authorization":f"bearer {auth}","apns-topic":topic,"apns-push-type":"alert","apns-priority":"10"},json=payload)
        if r.status_code>=300:log.warning("APNs push failed %s %s",r.status_code,r.text[:300]);return False
        return True
    except Exception:
        log.exception("APNs push failed");return False


def send_to_user(user,title,body,data=None):
    if not getattr(settings,"PUSH_ENABLED",False):return
    from .models import DeviceSession
    devices=list(DeviceSession.objects.filter(user=user,revoked_at__isnull=True).exclude(push_token="").only("push_token","push_provider","platform","pk"))
    for d in devices:
        provider=(d.push_provider or ("apns" if str(d.platform).lower()=="ios" else "fcm")).lower()
        ok=_apns_send(d.push_token,title,body,data) if provider=="apns" else _fcm_send(d.push_token,title,body,data)
        if not ok and getattr(settings,"DEBUG",False):log.debug("Push skipped/failed for device %s provider=%s",d.pk,provider)


def send_message_push_async(message):
    """Fire-and-forget push fan-out. WebSocket delivery remains primary."""
    if not getattr(settings,"PUSH_ENABLED",False):return
    message_id=getattr(message,"pk",None)
    if not message_id:return
    def worker():
        try:
            from apps.chat.models import Message,ConversationMember
            from apps.accounts.models import UserPreference
            msg=Message.objects.select_related("sender","conversation").get(pk=message_id)
            for member in ConversationMember.objects.select_related("user").filter(conversation=msg.conversation,notifications_enabled=True,is_hidden=False).exclude(user=msg.sender):
                pref=UserPreference.objects.filter(user=member.user).first()
                kind=msg.conversation.kind
                if pref:
                    if kind=="direct" and not pref.notify_direct_chats: continue
                    if kind=="group" and not pref.notify_groups: continue
                    if kind=="channel" and not pref.notify_channels: continue
                title=(msg.sender.display_name if msg.sender else "R-Messanger") if not pref or pref.show_sender_name else "R-Messanger"
                preview=(msg.body or ("Голосовое сообщение" if msg.kind=="voice" else "Новое сообщение"))[:180]
                body=preview if not pref or pref.show_message_preview else "Новое сообщение"
                send_to_user(member.user,title,body,{"type":"message","conversation_id":str(msg.conversation_id),"message_id":str(msg.pk),"url":f"rmes://chat/{msg.conversation_id}?message={msg.pk}"})
        except Exception:log.exception("Push fan-out failed for message %s",message_id)
    threading.Thread(target=worker,name=f"rmes-push-{message_id}",daemon=True).start()
