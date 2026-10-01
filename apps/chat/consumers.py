import time
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.presence import set_active as presence_set_active
from .models import Conversation, ConversationMember, Message
from apps.accounts.models import User, DeviceToken, ApiToken, PresencePrivacyException
from .services import create_message, mark_all_delivered, mark_delivered, mark_read, message_payload, pair_is_blocked, create_call_signal_event


def _token_from_scope(scope):
    """Extract an optional API/device bearer used by native clients."""
    query=parse_qs((scope.get("query_string") or b"").decode("utf-8",errors="ignore"))
    raw=(query.get("access_token") or query.get("token") or [""])[0]
    if raw:
        return raw[:4096]
    for key,value in scope.get("headers",[]):
        if key.lower()==b"authorization":
            text=value.decode("utf-8",errors="ignore")
            if text.lower().startswith("bearer "):
                return text.split(" ",1)[1].strip()[:4096]
    return ""


@database_sync_to_async
def _auth_lease_valid(user_id,session_key="",token=""):
    """Revalidate long-lived sockets so logout/revoke cannot leave ghost-online clients."""
    user=User.objects.filter(pk=user_id,is_active=True,can_login=True,is_suspended=False).first()
    if not user:
        return False
    if token:
        try:
            dt=DeviceToken.authenticate_access(token)
            if dt and dt.user_id==user_id and dt.revoked_at is None:
                return True
        except Exception:
            pass
        try:
            legacy=ApiToken.authenticate(token)
            if legacy and legacy.user_id==user_id and legacy.revoked_at is None:
                return True
        except Exception:
            pass
        return False
    if not session_key:
        return False
    row=Session.objects.filter(session_key=session_key,expire_date__gt=timezone.now()).first()
    if not row:
        return False
    try:
        return str(row.get_decoded().get("_auth_user_id") or "")==str(user_id)
    except Exception:
        return False


class AppConsumer(AsyncJsonWebsocketConsumer):
    """One websocket per R-Mes window for background events and presence."""

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            return await self.close(code=4401)
        query=parse_qs((self.scope.get("query_string") or b"").decode("utf-8",errors="ignore"))
        self.client_id=(query.get("client_id") or [""])[0][:96] or f"ws-{self.channel_name[-20:]}"
        self.auth_token=_token_from_scope(self.scope)
        session=self.scope.get("session")
        self.session_key=getattr(session,"session_key",None) or ""
        self.presence_active=False
        self.last_auth_check=0.0
        self.group=f"user_{self.user.pk}"
        await self.channel_layer.group_add(self.group,self.channel_name)
        await self.accept()
        await self._mark_all_delivered()
        await self.send_json({"type":"app_ready","server_time":timezone.now().isoformat()})

    async def disconnect(self, code):
        # Every browser/window owns a separate presence lease.  When its global
        # websocket dies we immediately release that lease; any other active
        # R-Mes window/device keeps the account online through its own lease.
        if getattr(self,"presence_active",False):
            try:
                online,changed=await self._set_presence(False)
                self.presence_active=False
                if changed:
                    await self._broadcast_presence(online)
            except Exception:
                pass
        if hasattr(self,"group"):
            await self.channel_layer.group_discard(self.group,self.channel_name)

    async def receive_json(self,data,**kwargs):
        kind=data.get("type")
        if kind=="presence":
            active=bool(data.get("active"))
            if active and not await self._auth_still_valid():
                online,changed=await self._set_presence(False)
                self.presence_active=False
                if changed:
                    await self._broadcast_presence(online)
                return await self.close(code=4401)
            self.presence_active=active
            online,changed=await self._set_presence(active)
            if changed:
                await self._broadcast_presence(online)
            await self.send_json({"type":"presence_ack","online":online})
        elif kind in {"ping","presence_ping"}:
            if not await self._auth_still_valid():
                if self.presence_active:
                    online,changed=await self._set_presence(False)
                    self.presence_active=False
                    if changed:
                        await self._broadcast_presence(online)
                return await self.close(code=4401)
            if self.presence_active:
                online,changed=await self._set_presence(True)
                if changed:
                    await self._broadcast_presence(online)
            await self.send_json({"type":"pong","ts":timezone.now().isoformat()})
        elif kind=="resync":
            await self._mark_all_delivered()
            await self.send_json({"type":"resync_ack","ts":timezone.now().isoformat()})
        elif kind in {"call_offer","call_answer","call_ice","call_end","call_reject","call_busy"}:
            await self._relay_call(kind,data)

    async def app_event(self,event):
        event_name=event.get("event")
        payload=event.get("payload",{})
        if event_name=="session_logout":
            target_session=str(payload.get("session_key") or "")
            if target_session and target_session==self.session_key:
                if self.presence_active:
                    online,changed=await self._set_presence(False)
                    self.presence_active=False
                    if changed:
                        await self._broadcast_presence(online)
                return await self.close(code=4401)
            return
        await self.send_json({"type":event_name,**payload})

    async def _relay_call(self,kind,data):
        conversation_id=str(data.get("conversation_id") or "").strip()
        call_id=str(data.get("call_id") or "").strip()[:96]
        if not conversation_id or not call_id:
            return await self.send_json({"type":"call_error","call_id":call_id,"message":"Некорректный идентификатор звонка."})
        try:
            signal_id,payload,peer_id=await self._create_call_event(conversation_id,kind,data)
        except (ValueError,PermissionError) as exc:
            return await self.send_json({"type":"call_error","call_id":call_id,"message":str(exc)})
        await self.channel_layer.group_send(f"user_{peer_id}",{
            "type":"app.event","event":kind,"payload":payload,
        })
        if kind=="call_offer":
            await self.send_json({"type":"call_signal_ack","call_id":call_id,"peer_id":peer_id,"signal_id":signal_id})

    @database_sync_to_async
    def _create_call_event(self,conversation_id,kind,data):
        row,payload,peer_id=create_call_signal_event(self.user,conversation_id,kind,data)
        return row.pk,payload,peer_id

    @database_sync_to_async
    def _call_context(self,conversation_id):
        conv=Conversation.objects.filter(pk=conversation_id,kind=Conversation.Kind.DIRECT).first()
        if not conv or not self.user.can_make_calls:return None
        if not ConversationMember.objects.filter(conversation=conv,user=self.user).exists():return None
        peer=conv.peer_for(self.user)
        if not peer or not peer.can_make_calls or pair_is_blocked(self.user,peer):return None
        return {"peer_id":peer.pk}

    async def _auth_still_valid(self,force=False):
        # Revalidate occasionally; explicit logout is pushed instantly through
        # the private user channel, so a DB query is not needed on every 3s ping.
        now=time.monotonic()
        if not force and self.last_auth_check and now-self.last_auth_check<20:
            return True
        ok=await _auth_lease_valid(self.user.pk,self.session_key,self.auth_token)
        self.last_auth_check=now
        return ok

    @database_sync_to_async
    def _set_presence(self,active):
        return presence_set_active(self.user,self.client_id,active,self.session_key)

    @database_sync_to_async
    def _mark_all_delivered(self):
        mark_all_delivered(self.user)

    @database_sync_to_async
    def _watcher_rows(self):
        conv_ids=list(ConversationMember.objects.filter(user=self.user).values_list("conversation_id",flat=True))
        rows=list(
            ConversationMember.objects.filter(conversation_id__in=conv_ids)
            .exclude(user_id=self.user.pk)
            .values_list("user_id","user__role")
            .distinct()
        )
        watcher_ids=[uid for uid,_role in rows]
        overrides=dict(
            PresencePrivacyException.objects.filter(owner_id=self.user.pk,target_id__in=watcher_ids)
            .values_list("target_id","mode")
        ) if watcher_ids else {}
        return [(uid,role,overrides.get(uid,"")) for uid,role in rows]

    async def _broadcast_presence(self,online):
        seen_iso,seen_ms,now_iso,now_ms,privacy=await self._presence_values()
        exact={"user_id":self.user.pk,"online":bool(online),"last_seen_at":seen_iso,"last_seen_at_ms":seen_ms,
               "server_time":now_iso,"server_time_ms":now_ms,
               "developer":bool(self.user.is_developer),"visibility":"exact","hidden":False}
        recent={**exact,"online":False,"last_seen_at":None,"last_seen_at_ms":None,"visibility":"recently","hidden":False}
        hidden={**exact,"online":False,"last_seen_at":None,"last_seen_at_ms":None,"visibility":"hidden","hidden":True}
        protected_sender=self.user.role in {User.Role.DEVELOPER,User.Role.SUPERADMIN}
        for uid,role,override in await self._watcher_rows():
            # Developer always sees exact technical presence. Everyone else obeys
            # the same Telegram-like privacy rules used by HTTP/API rendering.
            if role==User.Role.DEVELOPER:
                outgoing=exact
            elif protected_sender:
                outgoing=hidden
            elif override==PresencePrivacyException.Mode.ALWAYS:
                outgoing=exact
            elif override==PresencePrivacyException.Mode.EXCEPT:
                outgoing=recent
            elif privacy=="recently":
                outgoing=recent
            elif privacy=="nobody":
                outgoing=hidden if self.user.role==User.Role.DEVELOPER else recent
            else:
                outgoing=exact
            await self.channel_layer.group_send(f"user_{uid}",{"type":"app.event","event":"presence","payload":outgoing})


    @database_sync_to_async
    def _presence_values(self):
        user=User.objects.select_related("preferences").only("last_seen_at","role","preferences__last_seen_privacy").get(pk=self.user.pk)
        now=timezone.now()
        seen=user.last_seen_at or now
        if timezone.is_naive(seen):
            seen=timezone.make_aware(seen,timezone.get_default_timezone())
        try:
            privacy=user.preferences.last_seen_privacy or "everybody"
        except Exception:
            privacy="everybody"
        return seen.isoformat(),int(seen.timestamp()*1000),now.isoformat(),int(now.timestamp()*1000),privacy


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user=self.scope["user"]
        self.cid=self.scope["url_route"]["kwargs"]["conversation_id"]
        if not self.user.is_authenticated:
            return await self.close(code=4401)
        if not await self.has_access():
            return await self.close(code=4403)
        self.group=f"chat_{self.cid}"
        await self.channel_layer.group_add(self.group,self.channel_name)
        await self.accept()
        await self.mark_delivered_now()

    async def disconnect(self,code):
        if hasattr(self,"group"):
            await self.channel_layer.group_discard(self.group,self.channel_name)

    async def receive_json(self,data,**kwargs):
        t=data.get("type")
        if t=="message":
            client_id=data.get("client_id") or data.get("client_message_id") or ""
            if not await self.message_rate_allowed():
                return await self.send_json({"type":"error","client_message_id":client_id,"message":"Слишком много сообщений. Попробуйте через несколько секунд."})
            try:
                payload=await self.persist(data.get("body",""),data.get("reply_to"),client_id)
            except (ValueError,PermissionError) as exc:
                return await self.send_json({"type":"error","client_message_id":client_id,"message":str(exc)})
            await self.channel_layer.group_send(self.group,{"type":"chat.event","event":"message","payload":payload})
        elif t=="typing":
            await self.channel_layer.group_send(self.group,{"type":"chat.event","event":"typing","payload":{"user_id":self.user.pk,"name":self.user.display_name,"typing":bool(data.get("typing"))}})
        elif t in {"presence_active","presence_ping"}:
            # Presence is intentionally owned by /ws/app/ in v13.2. Keeping this
            # branch makes older clients harmless instead of double-counting leases.
            return
        elif t=="read":
            await self.read(data.get("message_id"))

    async def chat_event(self,event):
        await self.send_json({"type":event["event"],**event["payload"]})

    @database_sync_to_async
    def has_access(self):
        return ConversationMember.objects.filter(conversation_id=self.cid,user=self.user).exists()

    @database_sync_to_async
    def message_rate_allowed(self):
        bucket=int(timezone.now().timestamp())//10
        key=f"message-rate:{self.user.pk}:{bucket}"
        if cache.add(key,1,12):return True
        try:count=cache.incr(key)
        except ValueError:
            cache.set(key,1,12);count=1
        return count<=30

    @database_sync_to_async
    def persist(self,body,reply_id,client_id):
        conv=Conversation.objects.get(pk=self.cid)
        reply=Message.objects.filter(pk=reply_id,conversation=conv).first() if reply_id else None
        msg=create_message(self.user,conv,body,reply_to=reply,client_message_id=client_id)
        return message_payload(msg)

    @database_sync_to_async
    def mark_delivered_now(self):
        conv=Conversation.objects.get(pk=self.cid)
        mark_delivered(self.user,conv)

    @database_sync_to_async
    def call_allowed(self):
        conv=Conversation.objects.filter(pk=self.cid,kind=Conversation.Kind.DIRECT).first()
        if not conv or not self.user.can_make_calls:return False
        if not ConversationMember.objects.filter(conversation=conv,user=self.user).exists():return False
        peer=conv.peer_for(self.user)
        return bool(peer and peer.can_make_calls and not pair_is_blocked(self.user,peer))

    @database_sync_to_async
    def read(self,message_id):
        conv=Conversation.objects.get(pk=self.cid)
        msg=Message.objects.filter(pk=message_id,conversation=conv).first()
        if not msg:return None
        return mark_read(self.user,conv,msg)
