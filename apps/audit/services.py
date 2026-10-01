from .models import AuditEvent
from apps.accounts.utils import client_ip
def audit(request,action,object_type="",object_id="",metadata=None):
    actor=request.user if request is not None and getattr(request,"user",None) and request.user.is_authenticated else None
    return AuditEvent.objects.create(
        actor=actor,action=action,object_type=object_type,object_id=str(object_id or ""),
        ip_address=client_ip(request) if request else None,
        user_agent=request.META.get("HTTP_USER_AGENT","")[:2000] if request else "",
        metadata=metadata or {},
    )


def audit_actor(actor,action,object_type="",object_id="",metadata=None):
    """Record trusted background/real-time actions without an HTTP request."""
    return AuditEvent.objects.create(
        actor=actor if actor and getattr(actor,"is_authenticated",False) else None,
        action=action,object_type=object_type,object_id=str(object_id or ""),
        metadata=metadata or {},
    )
