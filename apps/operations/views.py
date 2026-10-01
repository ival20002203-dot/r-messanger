import hmac,json,mimetypes,re,hashlib
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.db.models import Sum
from django.http import HttpResponse,JsonResponse,HttpResponseForbidden,FileResponse,Http404
from django.utils import timezone
from django.urls import reverse

from apps.accounts.models import User,DeviceSession,LoginEvent
from apps.chat.models import Conversation,Message,Attachment
from apps.moderation.models import ModerationCase,ModerationScanJob
from apps.securitycenter.models import AttachmentScanJob,DLPCase
from .models import ClientVersionPolicy

try:
    from prometheus_client import Gauge,generate_latest,CONTENT_TYPE_LATEST
    USERS=Gauge("localgram_users_total","Users",["state"])
    CHATS=Gauge("localgram_conversations_total","Conversations",["kind"])
    MESSAGES=Gauge("localgram_messages_total","Messages")
    ATTACHMENTS=Gauge("localgram_attachments_total","Attachments",["scan_status"])
    SECURITY_QUEUE=Gauge("localgram_security_queue","Security worker queue")
    MOD_QUEUE=Gauge("localgram_moderation_queue","Moderation worker queue")
    DLP_OPEN=Gauge("localgram_dlp_open","Open DLP cases")
    MOD_PENDING=Gauge("localgram_moderation_pending","Pending moderation cases")
    ONLINE=Gauge("localgram_online_users","Users active within 120 seconds")
    WORKER=Gauge("localgram_worker_alive","Worker heartbeat",["worker"])
except Exception:
    Gauge=generate_latest=CONTENT_TYPE_LATEST=None

def _allowed_metrics(request):
    if not getattr(settings,"METRICS_ENABLED",True):return False
    token=getattr(settings,"METRICS_TOKEN","")
    if token:
        auth=request.headers.get("Authorization","")
        bearer=auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        supplied=request.headers.get("X-Metrics-Token","") or bearer or request.GET.get("token","")
        return hmac.compare_digest(str(token),str(supplied))
    remote=request.META.get("REMOTE_ADDR","")
    return settings.DEBUG or remote.startswith(("127.","172.","192.168.")) or remote=="::1"

def metrics(request):
    if not _allowed_metrics(request):return HttpResponseForbidden("metrics access denied")
    if not generate_latest:return HttpResponse("prometheus_client unavailable",status=503)
    now=timezone.now()
    USERS.labels("active").set(User.objects.filter(is_active=True,is_suspended=False).count())
    USERS.labels("suspended").set(User.objects.filter(is_suspended=True).count())
    for kind in ["direct","group","channel","saved"]:CHATS.labels(kind).set(Conversation.objects.filter(kind=kind).count())
    MESSAGES.set(Message.objects.count())
    for status in ["pending","safe","infected","error"]:ATTACHMENTS.labels(status).set(Attachment.objects.filter(scan_status=status).count())
    SECURITY_QUEUE.set(AttachmentScanJob.objects.filter(status__in=["queued","processing"]).count())
    MOD_QUEUE.set(ModerationScanJob.objects.filter(status__in=["queued","processing"]).count())
    DLP_OPEN.set(DLPCase.objects.filter(status="open").count())
    MOD_PENDING.set(ModerationCase.objects.filter(status="pending").count())
    ONLINE.set(User.objects.filter(last_seen_at__gte=now-timedelta(seconds=120)).count())
    WORKER.labels("security").set(1 if cache.get("localgram:security_worker:alive") else 0)
    WORKER.labels("moderation").set(1 if cache.get("localgram:moderation_worker:alive") else 0)
    WORKER.labels("scheduler").set(1 if cache.get("localgram:scheduler_worker:alive") else 0)
    return HttpResponse(generate_latest(),content_type=CONTENT_TYPE_LATEST)

def _version_tuple(value):
    nums=[int(x) for x in re.findall(r"\d+",str(value or "0"))[:3]]
    return tuple((nums+[0,0,0])[:3])

def _client_artifact(platform,version=""):
    root=settings.CLIENT_UPDATE_DIR / platform
    if not root.exists():
        return None
    suffix=".exe" if platform=="windows" else ".apk" if platform=="android" else ""
    if not suffix:
        return None
    rows=[p for p in root.iterdir() if p.is_file() and p.suffix.lower()==suffix]
    if version:
        exact=[p for p in rows if version in p.name]
        if exact: rows=exact
    if not rows:
        return None
    def key(path):
        m=re.search(r"(\d+\.\d+(?:\.\d+)?)",path.name)
        return (_version_tuple(m.group(1) if m else "0"),path.stat().st_mtime)
    return sorted(rows,key=key,reverse=True)[0]

def _artifact_sha256(path):
    if not path:
        return ""
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def client_policy(request):
    if not getattr(settings,"CLIENT_UPDATE_API_PUBLIC",True) and not getattr(request,"user",None).is_authenticated:
        return HttpResponseForbidden("client policy access denied")
    platform=(request.GET.get("platform") or "windows").lower()
    current=(request.GET.get("current") or "").strip()
    row=ClientVersionPolicy.objects.filter(platform=platform,enabled=True).first()
    latest=(row.latest_version if row else getattr(settings,"APP_VERSION","13.0.0"))
    minimum=(row.minimum_version if row else latest)
    artifact=_client_artifact(platform,latest) or _client_artifact(platform)
    fallback_url=request.build_absolute_uri(reverse("operations:client_update_download")+f"?platform={platform}&version={latest}") if artifact else ""
    update_url=(row.update_url if row and row.update_url else fallback_url)
    return JsonResponse({
        "platform":platform,"latest_version":latest,"minimum_version":minimum,
        "force_update":bool(row.force_update) if row else False,"update_url":update_url,
        "release_notes":row.release_notes if row else "","updated_at":row.updated_at.isoformat() if row else None,
        "available":bool(current and _version_tuple(current)<_version_tuple(latest)),
        "artifact_ready":bool(artifact),
        "filename":artifact.name if artifact else "",
        "size":artifact.stat().st_size if artifact else 0,
        "sha256":_artifact_sha256(artifact),
    })

def client_update_download(request):
    platform=(request.GET.get("platform") or "windows").lower()
    version=(request.GET.get("version") or "").strip()[:32]
    path=_client_artifact(platform,version) or _client_artifact(platform)
    if not path:
        raise Http404("Client update is not published yet")
    content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    response=FileResponse(open(path,"rb"),as_attachment=True,filename=path.name,content_type=content_type)
    response["Cache-Control"]="private, no-store"
    return response


def client_update_feed(request,platform,filename):
    """Public read-only generic update feed used by electron-updater.

    Only explicitly published update metadata/artifacts under CLIENT_UPDATE_DIR
    are reachable; path traversal and unrelated server files are rejected.
    """
    if not getattr(settings,"CLIENT_UPDATE_API_PUBLIC",True) and not getattr(request,"user",None).is_authenticated:
        return HttpResponseForbidden("client update access denied")
    if platform not in {"windows","macos","linux"}:raise Http404
    root=(settings.CLIENT_UPDATE_DIR/platform).resolve()
    candidate=(root/filename).resolve()
    try:candidate.relative_to(root)
    except ValueError:raise Http404
    allowed={".yml",".yaml",".exe",".blockmap",".zip",".dmg",".appimage"}
    if not candidate.is_file() or candidate.suffix.lower() not in allowed:raise Http404
    content_type="text/yaml; charset=utf-8" if candidate.suffix.lower() in {".yml",".yaml"} else mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
    response=FileResponse(open(candidate,"rb"),as_attachment=False,content_type=content_type)
    response["Content-Length"]=str(candidate.stat().st_size)
    response["Cache-Control"]="no-cache, no-store" if candidate.suffix.lower() in {".yml",".yaml"} else "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"]="nosniff"
    return response

def status_summary(request):
    if not request.user.is_authenticated or not request.user.is_control_admin:return HttpResponseForbidden()
    now=timezone.now()
    return JsonResponse({
        "users":{"total":User.objects.count(),"online":User.objects.filter(last_seen_at__gte=now-timedelta(seconds=120)).count()},
        "messages":{"total":Message.objects.count(),"hour":Message.objects.filter(created_at__gte=now-timedelta(hours=1)).count()},
        "attachments":{"total":Attachment.objects.count(),"pending":Attachment.objects.filter(scan_status="pending").count(),"infected":Attachment.objects.filter(scan_status="infected").count()},
        "workers":{"security":bool(cache.get("localgram:security_worker:alive")),"moderation":bool(cache.get("localgram:moderation_worker:alive")),"scheduler":bool(cache.get("localgram:scheduler_worker:alive"))},
        "security":{"dlp_open":DLPCase.objects.filter(status="open").count(),"moderation_pending":ModerationCase.objects.filter(status="pending").count(),"failed_login_24h":LoginEvent.objects.filter(successful=False,created_at__gte=now-timedelta(hours=24)).count()},
    })
