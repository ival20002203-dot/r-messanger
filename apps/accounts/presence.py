import hashlib
import re
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import get_language

# R-Mes presence is intentionally short-lived. Normal blur/close/logout events
# remove a window lease immediately; the lease only protects against crashed
# browsers/processes that never get a chance to send the final offline event.
PRESENCE_LEASE_SECONDS = 8
PRESENCE_STATE_TTL = 45
DB_TOUCH_SECONDS = 3
MAX_CLIENTS_PER_USER = 24
CLIENT_ID_RE = re.compile(r"[^a-zA-Z0-9_.:-]+")


def _state_key(user_id):
    return f"rmes:presence:leases:{user_id}"


def _db_touch_key(user_id):
    return f"rmes:presence:dbtouch:{user_id}"


def _lock_key(user_id):
    return f"rmes:presence:lock:{user_id}"


def _session_clients_key(user_id, session_key):
    digest=hashlib.sha256(str(session_key or "").encode("utf-8")).hexdigest()[:24]
    return f"rmes:presence:session:{user_id}:{digest}"


def _load_session_clients(user_id,session_key):
    if not session_key:
        return set()
    try:
        raw=cache.get(_session_clients_key(user_id,session_key),[]) or []
        return {normalize_client_id(x) for x in raw if x}
    except Exception:
        return set()


def _track_session_client(user_id,session_key,client_id,active):
    if not session_key:
        return
    key=_session_clients_key(user_id,session_key)
    try:
        clients=_load_session_clients(user_id,session_key)
        if active:
            clients.add(normalize_client_id(client_id))
        else:
            clients.discard(normalize_client_id(client_id))
        if clients:
            cache.set(key,sorted(clients),PRESENCE_STATE_TTL)
        else:
            cache.delete(key)
    except Exception:
        pass


@contextmanager
def _presence_lock(user_id):
    token = uuid.uuid4().hex
    acquired = False
    try:
        for _ in range(30):
            if cache.add(_lock_key(user_id), token, timeout=3):
                acquired = True
                break
            time.sleep(.01)
    except Exception:
        yield
        return
    try:
        yield
    finally:
        try:
            if acquired and cache.get(_lock_key(user_id)) == token:
                cache.delete(_lock_key(user_id))
        except Exception:
            pass


def normalize_client_id(value):
    value = CLIENT_ID_RE.sub("", str(value or ""))[:96]
    return value or "legacy"


def _clean_state(raw, now=None):
    now = float(now or time.time())
    state = raw if isinstance(raw, dict) else {}
    clean = {}
    for key, expiry in state.items():
        try:
            expiry = float(expiry)
        except (TypeError, ValueError):
            continue
        if expiry > now:
            clean[normalize_client_id(key)] = expiry
    if len(clean) > MAX_CLIENTS_PER_USER:
        clean = dict(sorted(clean.items(), key=lambda kv: kv[1], reverse=True)[:MAX_CLIENTS_PER_USER])
    return clean


def _load(user_id):
    now = time.time()
    try:
        raw = cache.get(_state_key(user_id), {})
        clean = _clean_state(raw, now)
        if clean != raw:
            if clean:
                cache.set(_state_key(user_id), clean, PRESENCE_STATE_TTL)
            else:
                cache.delete(_state_key(user_id))
        return clean
    except Exception:
        return None


def _save(user_id, state):
    state = _clean_state(state)
    try:
        if state:
            cache.set(_state_key(user_id), state, PRESENCE_STATE_TTL)
        else:
            cache.delete(_state_key(user_id))
        return True
    except Exception:
        return False


def _update_user_fields(user, **fields):
    user_id = getattr(user, "pk", None)
    if not user_id:
        return 0
    from .models import User
    updated = User.objects.filter(pk=user_id).update(**fields)
    for name, value in fields.items():
        try:
            setattr(user, name, value)
        except Exception:
            pass
    return updated


def _touch_last_seen(user, force=False):
    try:
        if not force and cache.get(_db_touch_key(user.pk)):
            return
    except Exception:
        pass
    now = timezone.now()
    _update_user_fields(user, last_seen_at=now)
    try:
        cache.set(_db_touch_key(user.pk), 1, DB_TOUCH_SECONDS)
    except Exception:
        pass


def touch_last_seen(user):
    _touch_last_seen(user, force=False)


def _db_presence(user, active, now=None):
    now = now or timezone.now()
    _update_user_fields(user, last_seen_at=now, presence_active=bool(active))


def is_online(user_id):
    state = _load(user_id)
    if state is not None:
        online = bool(state)
        if not online:
            try:
                from .models import User
                User.objects.filter(pk=user_id, presence_active=True).update(presence_active=False)
            except Exception:
                pass
        return online
    try:
        from .models import User
        cutoff = timezone.now() - timedelta(seconds=PRESENCE_LEASE_SECONDS * 2)
        return User.objects.filter(
            pk=user_id, presence_active=True, last_seen_at__gte=cutoff,
        ).exists()
    except Exception:
        return False


def set_active(user, client_id, active=True, session_key=""):
    """Open/refresh or immediately close one browser/device presence lease."""
    if not getattr(user, "pk", None):
        return False, False
    client_id = normalize_client_id(client_id)
    with _presence_lock(user.pk):
        before_state = _load(user.pk)
        if before_state is None:
            before = bool(
                getattr(user, "presence_active", False)
                and getattr(user, "last_seen_at", None)
                and (timezone.now() - user.last_seen_at).total_seconds() < PRESENCE_LEASE_SECONDS * 2
            )
            _db_presence(user, active, timezone.now())
            return bool(active), before != bool(active)

        before = bool(before_state)
        state = dict(before_state)
        if active:
            state[client_id] = time.time() + PRESENCE_LEASE_SECONDS
            _track_session_client(user.pk,session_key,client_id,True)
            _touch_last_seen(user, force=False)
        else:
            # Immediate removal is important for Telegram-like behaviour: switching
            # away, closing the window, logging out or losing a websocket should
            # not leave a ghost "online" lease behind.
            state.pop(client_id, None)
            _track_session_client(user.pk,session_key,client_id,False)
            _touch_last_seen(user, force=True)

        _save(user.pk, state)
        after_state = _load(user.pk)
        after = bool(after_state) if after_state is not None else bool(active)
        if bool(getattr(user, "presence_active", False)) != after:
            _update_user_fields(user, presence_active=after)
    return after, before != after


def clear_presence_session(user,session_key):
    """Clear only the browser tabs/windows that belong to one Django session."""
    if not getattr(user,"pk",None) or not session_key:
        return clear_presence(user)
    with _presence_lock(user.pk):
        before_state=_load(user.pk)
        before=bool(before_state) if before_state is not None else is_online(user.pk)
        clients=_load_session_clients(user.pk,session_key)
        if before_state is None:
            # Cache unavailable: durable DB state is the safest fallback.
            now=timezone.now()
            _update_user_fields(user,last_seen_at=now,presence_active=False)
            return False,bool(before)
        state=dict(before_state)
        for client_id in clients:
            state.pop(client_id,None)
        try:
            cache.delete(_session_clients_key(user.pk,session_key))
        except Exception:
            pass
        _save(user.pk,state)
        after=bool(_load(user.pk) or {})
        now=timezone.now()
        _update_user_fields(user,last_seen_at=now,presence_active=after)
    return after,before!=after


def clear_presence(user):
    """Immediately clear every lease for an account (used on logout/revoke)."""
    if not getattr(user, "pk", None):
        return False, False
    with _presence_lock(user.pk):
        before = is_online(user.pk)
        try:
            cache.delete(_state_key(user.pk))
            cache.delete(_db_touch_key(user.pk))
        except Exception:
            pass
        now = timezone.now()
        _update_user_fields(user, last_seen_at=now, presence_active=False)
    return False, bool(before)


def mark_active(user, client_id="legacy"):
    return set_active(user, client_id, True)


def heartbeat(user, client_id="legacy"):
    return set_active(user, client_id, True)


def mark_inactive(user, client_id="legacy"):
    return set_active(user, client_id, False)


def snapshot(user_ids):
    result = {}
    for user_id in {int(x) for x in user_ids if str(x).isdigit()}:
        result[user_id] = is_online(user_id)
    return result


def is_presence_protected(peer):
    if not peer:
        return False
    try:
        return peer.role in {peer.Role.DEVELOPER, peer.Role.SUPERADMIN}
    except Exception:
        return getattr(peer, "role", "") in {"developer", "superadmin"}


def _peer_privacy(peer):
    """Return everybody/recently/nobody without failing when preferences are absent."""
    try:
        pref = peer.preferences
        return getattr(pref, "last_seen_privacy", "everybody") or "everybody"
    except Exception:
        try:
            from .models import UserPreference
            return (UserPreference.objects.filter(user_id=peer.pk)
                    .values_list("last_seen_privacy", flat=True).first() or "everybody")
        except Exception:
            return "everybody"


def _privacy_exception(viewer, peer):
    """Return an explicit per-user visibility override, if configured."""
    viewer_id=getattr(viewer,"pk",None); peer_id=getattr(peer,"pk",None)
    if not viewer_id or not peer_id or viewer_id==peer_id:
        return ""
    try:
        from .models import PresencePrivacyException
        return (PresencePrivacyException.objects.filter(owner_id=peer_id,target_id=viewer_id)
                .values_list("mode",flat=True).first() or "")
    except Exception:
        return ""


def presence_visibility(viewer, peer):
    """exact/recently/hidden. Developer always gets exact server truth."""
    if not peer:
        return "hidden"
    viewer_id = getattr(viewer, "pk", None)
    if viewer_id and viewer_id == getattr(peer, "pk", None):
        return "exact"
    if bool(getattr(viewer, "is_developer", False)):
        return "exact"
    if is_presence_protected(peer):
        return "hidden"
    override=_privacy_exception(viewer,peer)
    if override=="always":
        return "exact"
    if override=="except":
        return "recently"
    mode = _peer_privacy(peer)
    if mode == "recently":
        return "recently"
    if mode == "nobody":
        # Full hiding remains a developer-only diagnostic/privacy option.
        return "hidden" if bool(getattr(peer,"is_developer",False)) else "recently"
    return "exact"


def can_view_presence(viewer, peer):
    """Compatibility helper: True only when exact online/time is allowed."""
    return presence_visibility(viewer, peer) == "exact"


def _approximate_label(seen, language, now):
    lang = language
    if not seen:
        return {"en":"last seen a long time ago","uz":"uzoq vaqt oldin onlayn bo‘lgan"}.get(lang,"был(а) давно")
    if timezone.is_naive(seen):
        seen = timezone.make_aware(seen, timezone.get_default_timezone())
    seconds = max(0, int((now - seen).total_seconds()))
    if seconds <= 3 * 24 * 3600:
        return {"en":"last seen recently","uz":"yaqinda onlayn edi"}.get(lang,"был(а) недавно")
    if seconds <= 7 * 24 * 3600:
        return {"en":"last seen within a week","uz":"shu hafta onlayn edi"}.get(lang,"был(а) на этой неделе")
    if seconds <= 30 * 24 * 3600:
        return {"en":"last seen within a month","uz":"shu oy onlayn edi"}.get(lang,"был(а) в этом месяце")
    return {"en":"last seen a long time ago","uz":"uzoq vaqt oldin onlayn bo‘lgan"}.get(lang,"был(а) давно")


def presence_label(viewer, peer, language=None, now=None, online=None):
    if not peer:
        return ""
    lang = (language or get_language() or "ru").lower().split("-", 1)[0].split("_", 1)[0]
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_default_timezone())

    visibility = presence_visibility(viewer, peer)
    if visibility == "hidden":
        return {"en":"last seen hidden","uz":"oxirgi tashrif yashirilgan"}.get(lang,"время посещения скрыто")
    seen = getattr(peer, "last_seen_at", None)
    if visibility == "recently":
        # Do not leak exact online state or timestamp; this mirrors Telegram-style
        # approximate presence buckets while developer still sees exact values.
        return _approximate_label(seen, lang, now)

    if online is None:
        try:
            online = bool(peer.is_online)
        except Exception:
            online = False
    else:
        online = bool(online)
    if online:
        return {"en":"online","uz":"onlayn"}.get(lang,"в сети")
    if not seen:
        return {"en":"last seen a long time ago","uz":"uzoq vaqt oldin onlayn bo‘lgan"}.get(lang,"давно не был(а) в сети")
    if timezone.is_naive(seen):
        seen = timezone.make_aware(seen, timezone.get_default_timezone())
    seconds = max(0, int((now - seen).total_seconds()))
    if seconds < 60:
        return {"en":"last seen just now","uz":"hozirgina onlayn edi"}.get(lang,"был(а) только что")
    if seconds < 3600:
        minutes = max(1, seconds // 60)
        if lang == "en":
            return f"last seen {minutes} min ago"
        if lang == "uz":
            return f"{minutes} daqiqa oldin onlayn edi"
        return f"был(а) {minutes} мин. назад"
    local_seen = timezone.localtime(seen)
    local_now = timezone.localtime(now)
    if local_seen.date() == local_now.date():
        clock = local_seen.strftime("%H:%M")
        if lang == "en":
            return f"last seen today at {clock}"
        if lang == "uz":
            return f"bugun {clock} da onlayn edi"
        return f"был(а) сегодня в {clock}"
    if lang == "en":
        return f"last seen {local_seen.strftime('%d.%m.%Y %H:%M')}"
    if lang == "uz":
        return f"{local_seen.strftime('%d.%m.%Y %H:%M')} da onlayn edi"
    return f"был(а) {local_seen.strftime('%d.%m.%Y в %H:%M')}"
