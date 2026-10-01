import hashlib,time
from django.conf import settings
from django.core.cache import cache
from apps.accounts.utils import client_ip


def enforce_message_policy(user,conversation,body):
    if not getattr(settings,"ANTI_SPAM_ENABLED",True):return
    normalized=" ".join((body or "").lower().split())[:1000]
    digest=hashlib.sha256(normalized.encode()).hexdigest()[:20]
    window=int(getattr(settings,"ANTI_SPAM_WINDOW_SECONDS",60))
    dup_limit=int(getattr(settings,"ANTI_SPAM_DUPLICATE_LIMIT",8))
    bucket=int(time.time())//window
    duplicate_key=f"spam:dup:{user.pk}:{digest}:{bucket}"
    flood_key=f"spam:flood:{user.pk}:{bucket}"
    def bump(key):
        if cache.add(key,1,window+5):return 1
        try:return cache.incr(key)
        except Exception:return 1
    duplicate_count=bump(duplicate_key);flood_count=bump(flood_key)
    reason=None
    if duplicate_count>dup_limit:reason="Повтор одного и того же сообщения слишком много раз."
    elif flood_count>int(getattr(settings,"RATE_LIMIT_MESSAGES",80)):reason="Слишком высокая частота сообщений."
    if not reason:return
    try:
        from apps.operations.models import RateLimitEvent
        from apps.securitycenter.models import SecurityIncident
        event_guard=f"spam:event:{user.pk}:{bucket}:{digest if duplicate_count>dup_limit else 'flood'}"
        if cache.add(event_guard,1,window):
            RateLimitEvent.objects.create(user=user,category="message_spam",key=f"user:{user.pk}",count=max(duplicate_count,flood_count),limit=dup_limit if duplicate_count>dup_limit else int(getattr(settings,"RATE_LIMIT_MESSAGES",80)),details={"conversation":str(conversation.pk),"duplicate_count":duplicate_count,"flood_count":flood_count})
            SecurityIncident.objects.create(kind=SecurityIncident.Kind.AUTH,user=user,severity="medium",title="Message anti-spam throttle",details={"conversation":str(conversation.pk),"reason":reason})
    except Exception:pass
    raise PermissionError(reason)
