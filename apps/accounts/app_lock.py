from __future__ import annotations

from datetime import datetime
from django.utils import timezone

LOCKED_KEY = "rmes_app_lock_locked"
LAST_ACTIVITY_KEY = "rmes_app_lock_last_activity"


def preference_for(user):
    from .models import UserPreference
    pref, _ = UserPreference.objects.get_or_create(user=user)
    return pref


def _timestamp_now() -> float:
    return timezone.now().timestamp()


def _last_activity(request) -> float | None:
    value = request.session.get(LAST_ACTIVITY_KEY)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def lock_session(request) -> None:
    request.session[LOCKED_KEY] = True
    request.session.modified = True


def unlock_session(request) -> None:
    request.session[LOCKED_KEY] = False
    request.session[LAST_ACTIVITY_KEY] = _timestamp_now()
    request.session.modified = True


def clear_lock_session(request) -> None:
    request.session.pop(LOCKED_KEY, None)
    request.session.pop(LAST_ACTIVITY_KEY, None)
    request.session.modified = True


def timed_out(request, pref=None) -> bool:
    if not getattr(request.user, "is_authenticated", False):
        return False
    pref = pref or preference_for(request.user)
    if not pref.app_lock_enabled:
        return False
    timeout_minutes = int(pref.app_lock_timeout_minutes or 0)
    if timeout_minutes <= 0:
        return False
    last = _last_activity(request)
    if last is None:
        request.session[LAST_ACTIVITY_KEY] = _timestamp_now()
        request.session.modified = True
        return False
    return (_timestamp_now() - last) >= timeout_minutes * 60


def requires_lock(request, pref=None) -> bool:
    if not getattr(request.user, "is_authenticated", False):
        return False
    pref = pref or preference_for(request.user)
    if not pref.app_lock_enabled:
        clear_lock_session(request)
        return False
    if bool(request.session.get(LOCKED_KEY, False)):
        return True
    if timed_out(request, pref):
        lock_session(request)
        return True
    return False


def touch_activity(request, pref=None) -> bool:
    """Return False when the session must remain locked; otherwise refresh activity."""
    if not getattr(request.user, "is_authenticated", False):
        return True
    pref = pref or preference_for(request.user)
    if not pref.app_lock_enabled:
        clear_lock_session(request)
        return True
    if requires_lock(request, pref):
        return False
    request.session[LAST_ACTIVITY_KEY] = _timestamp_now()
    request.session.modified = True
    return True
