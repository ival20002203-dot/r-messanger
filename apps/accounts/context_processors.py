import json,re
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from .models import AppSetting,UserPreference


def _version_tuple(value):
    nums=[int(x) for x in re.findall(r"\d+",str(value or "0"))[:3]]
    return tuple((nums+[0,0,0])[:3])


def _client_from_request(request):
    ua=request.META.get("HTTP_USER_AGENT") or ""
    patterns=(
        ("windows",r"RMesDesktop/([0-9A-Za-z._+-]+)"),
        ("android",r"RMesAndroid/([0-9A-Za-z._+-]+)"),
        ("ios",r"RMesIOS/([0-9A-Za-z._+-]+)"),
    )
    for platform,pattern in patterns:
        m=re.search(pattern,ua,re.I)
        if m:return platform,m.group(1)
    return "",""


def app_context(request):
    vals={x.key:x.value for x in AppSetting.objects.all()}
    pref=None
    if getattr(request,"user",None) and request.user.is_authenticated:
        pref,_=UserPreference.objects.get_or_create(user=request.user)
    language=(getattr(pref,"language",None) or getattr(request,"LANGUAGE_CODE",None) or "ru").split("-",1)[0].lower()
    language_options=[{"code":code,"label":label} for code,label in getattr(settings,"LANGUAGES",(("ru","Русский"),))]
    ua=(request.META.get("HTTP_USER_AGENT") or "")
    platform,current_version=_client_from_request(request)
    client_update=None
    if platform and current_version:
        try:
            from apps.operations.models import ClientVersionPolicy
            row=ClientVersionPolicy.objects.filter(platform=platform,enabled=True).first()
            if row and _version_tuple(current_version)<_version_tuple(row.latest_version):
                from django.urls import reverse
                try:
                    from apps.operations.views import _client_artifact,_artifact_sha256
                    artifact=_client_artifact(platform,row.latest_version) or _client_artifact(platform)
                except Exception:
                    artifact=None
                update_url=row.update_url or (request.build_absolute_uri(reverse("operations:client_update_download")+f"?platform={platform}&version={row.latest_version}") if artifact else "")
                # A policy row may be migrated before the native installer is
                # uploaded.  Do not leave a permanent, unusable "Обновить"
                # banner in the web shell in that state; it becomes visible as
                # soon as an URL/artifact is actually published (or when an
                # explicitly forced update requires operator attention).
                if update_url or row.force_update:
                    client_update={
                        "platform":platform,"current_version":current_version,"latest_version":row.latest_version,
                        "minimum_version":row.minimum_version,"force_update":row.force_update,
                        "update_url":update_url,"release_notes":row.release_notes,"ready":bool(update_url),
                        "sha256":_artifact_sha256(artifact) if artifact else "",
                    }
        except Exception:
            client_update=None
    app_name=(vals.get("app_name") or "R-Messanger").strip()
    if app_name.lower() in {"artel link","artellink","r-mes","r mes"}:
        app_name="R-Messanger"
    return {
        "APP_NAME":app_name,
        "APP_VERSION":getattr(settings,"APP_VERSION","15.1.1"),
        "MONITORING_NOTICE":vals.get("monitoring_notice",settings.MONITORING_NOTICE),
        "MAX_UPLOAD_MB":settings.MAX_UPLOAD_MB,
        "CONTENT_MODERATION_POLICY_NOTICE":settings.CONTENT_MODERATION_POLICY_NOTICE,
        "RTC_ICE_SERVERS_JSON":json.dumps(getattr(settings,"RTC_ICE_SERVERS",[]),ensure_ascii=False),
        "SERVER_TIME_ZONE":getattr(settings,"TIME_ZONE","Asia/Tashkent"),
        "SERVER_NOW_ISO":timezone.now().isoformat(),
        "USER_PREF":pref,
        "IS_DESKTOP_APP":("RMesDesktop/" in ua),
        "IS_ANDROID_APP":("RMesAndroid/" in ua),
        "IS_IOS_APP":("RMesIOS/" in ua),
        "CLIENT_UPDATE":client_update,
        "CURRENT_LANGUAGE":language,
        "LANGUAGE_OPTIONS":language_options,
    }
