from django.conf import settings
from django.conf.urls.static import static
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse,FileResponse
from django.urls import include,path

def service_worker(request):
    response=FileResponse(open(settings.BASE_DIR / "static" / "sw.js","rb"),content_type="application/javascript")
    response["Service-Worker-Allowed"]="/"
    response["Cache-Control"]="no-cache"
    return response

def health(request):
    status={"service":"localgram","database":"unknown","redis":"unknown"}
    ok=True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        status["database"]="ok"
    except Exception as exc:
        status["database"]="error"
        status["database_error"]=str(exc)[:180]
        ok=False
    try:
        key="localgram-health-check"
        cache.set(key,"ok",10)
        if cache.get(key)!="ok":raise RuntimeError("cache read/write mismatch")
        status["redis"]="ok" if settings.REDIS_URL else "local-memory"
    except Exception as exc:
        status["redis"]="error"
        status["redis_error"]=str(exc)[:180]
        ok=False
    status["status"]="ok" if ok else "degraded"
    return JsonResponse(status,status=200 if ok else 503)

urlpatterns=[
    path("sw.js",service_worker),
    path("healthz/",health),
    path("readyz/",health),
    path("",include("apps.chat.urls")),
    path("auth/",include("apps.accounts.urls")),
    path("control/",include("apps.controlpanel.urls")),
    path("api/v1/",include("apps.chat.api_urls")),
    path("ops/",include("apps.operations.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
