import uuid
from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.utils import timezone
from .utils import client_ip,ip_is_denied

DEVICE_COOKIE="lg_device_id"


def _friendly_access_denied(request, message="У вашей учётной записи нет доступа к R-Mes.", status=403):
    return render(request, "errors/access_denied.html", {
        "title": "Доступ запрещён",
        "message": message,
    }, status=status)


class WebAccessMiddleware:
    """Disable only the browser UI while keeping R-Mes Desktop and native APIs online.

    This is an availability/UI gate, not a cryptographic trust boundary: HTTP headers can be
    reproduced by a determined client. Real authorization continues to be enforced separately.
    """
    EXEMPT_PREFIXES=(
        "/healthz/",
        "/readyz/",
        "/api/v1/",
        "/ops/client-policy/",
        "/ops/client-update/",
    )

    def __init__(self,get_response):
        self.get_response=get_response

    @staticmethod
    def _is_native_client(request):
        desktop=(request.META.get("HTTP_X_R_MES_DESKTOP") or "").strip().lower()
        client=(request.META.get("HTTP_X_R_MES_CLIENT") or "").strip().lower()
        ua=request.META.get("HTTP_USER_AGENT") or ""
        return (
            desktop in {"1","true","yes","desktop"}
            or client in {"desktop","windows","macos","linux","android","ios","mobile"}
            or "RMesDesktop/" in ua
            or "RMesAndroid/" in ua
            or "RMesIOS/" in ua
        )

    def __call__(self,request):
        if getattr(settings,"WEB_ACCESS_ENABLED",True):
            return self.get_response(request)
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)
        if self._is_native_client(request):
            return self.get_response(request)
        return render(request,"errors/web_disabled.html",{
            "message":getattr(settings,"WEB_ACCESS_MESSAGE","Для работы используйте приложение R-Messanger."),
        },status=503)

class AccessControlMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        if ip_is_denied(client_ip(request)):
            return _friendly_access_denied(request,"Доступ к R-Messanger запрещён политикой доступа.")
        u=getattr(request,"user",None)
        if u and u.is_authenticated:
            if u.is_suspended or not u.can_login or not u.is_active:
                logout(request)
                return _friendly_access_denied(request,"Доступ к R-Messanger заблокирован. Обратитесь к администратору.")
        return self.get_response(request)

class DeviceTrackingMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        u=getattr(request,"user",None)
        device_id=(request.COOKIES.get(DEVICE_COOKIE) or "")[:80]
        existing=None
        try:
            from .models import DeviceSession
            if u and u.is_authenticated and device_id:
                existing=DeviceSession.objects.filter(user=u,device_id=device_id,revoked_at__isnull=True).order_by("-last_seen_at").first()
                if existing and existing.trust_status==DeviceSession.Trust.BLOCKED:
                    logout(request)
                    return _friendly_access_denied(request,"Это устройство не имеет доступа к R-Mes. Обратитесь к администратору.")
        except Exception:
            existing=None

        response=self.get_response(request)
        u=getattr(request,"user",None)
        if not u or not u.is_authenticated:return response
        try:
            from .models import DeviceSession
            key=request.session.session_key
            if not key:return response
            if not device_id:device_id=uuid.uuid4().hex
            ua=(request.META.get("HTTP_USER_AGENT") or "")[:1000]
            lower=ua.lower()
            platform="Windows" if "windows" in lower else "macOS" if "mac os" in lower or "macintosh" in lower else "iOS" if "iphone" in lower or "ipad" in lower else "Android" if "android" in lower else "Linux" if "linux" in lower else "Web"
            browser="Edge" if "edg/" in lower else "Firefox" if "firefox/" in lower else "Chrome" if "chrome/" in lower else "Safari" if "safari/" in lower else "Browser"
            now=timezone.now()
            obj=existing or DeviceSession.objects.filter(user=u,device_id=device_id,revoked_at__isnull=True).order_by("-last_seen_at").first()
            created=False
            if not obj:
                obj=DeviceSession.objects.create(user=u,session_key=key,device_id=device_id,device_name=f"{platform} · {browser}",platform=platform,browser=browser,ip_address=client_ip(request),user_agent=ua,last_seen_at=now,is_current=True,trust_status=DeviceSession.Trust.NEW)
                created=True
            elif (now-obj.last_seen_at).total_seconds()>45 or obj.session_key!=key:
                obj.last_seen_at=now;obj.ip_address=client_ip(request);obj.user_agent=ua;obj.is_current=True;obj.session_key=key;obj.device_name=f"{platform} · {browser}";obj.platform=platform;obj.browser=browser
                obj.save(update_fields=["last_seen_at","ip_address","user_agent","is_current","session_key","device_name","platform","browser"])
            if created:
                try:
                    from apps.securitycenter.models import SecurityIncident
                    SecurityIncident.objects.create(kind=SecurityIncident.Kind.DEVICE,user=u,severity="low",title="New device session",details={"device_id":obj.pk,"ip":str(obj.ip_address or ""),"platform":platform,"browser":browser})
                except Exception:pass
            response.set_cookie(DEVICE_COOKIE,device_id,max_age=365*24*3600,httponly=True,samesite="Lax",secure=not settings.DEBUG)
        except Exception:
            pass
        return response


class UserLanguageMiddleware:
    """Apply each user's persisted interface language for every request.

    Django's LocaleMiddleware handles anonymous sessions/cookies; this small
    layer gives an authenticated user a stable language even when an old
    browser still carries a different locale cookie.
    """
    allowed={"ru", "en", "uz"}

    def __init__(self,get_response):
        self.get_response=get_response

    def __call__(self,request):
        from django.utils import translation
        language=(getattr(request,"LANGUAGE_CODE","") or "ru").split("-",1)[0].lower()
        user=getattr(request,"user",None)
        if user and user.is_authenticated:
            try:
                from .models import UserPreference
                saved=UserPreference.objects.filter(user=user).values_list("language",flat=True).first()
                if saved in self.allowed:
                    language=saved
            except Exception:
                pass
        if language not in self.allowed:
            language="ru"
        translation.activate(language)
        request.LANGUAGE_CODE=language
        try:
            response=self.get_response(request)
            if user and user.is_authenticated:
                response.set_cookie(
                    "rmes_language",language,max_age=365*24*60*60,
                    httponly=False,samesite="Lax",secure=not settings.DEBUG,
                )
            return response
        finally:
            translation.deactivate()

class AppLockMiddleware:
    """Server-side gate for an authenticated session protected by the R-Mes passcode."""
    EXEMPT_PREFIXES=(
        "/auth/app-lock/",
        "/auth/logout/",
        "/auth/presence/",
        "/static/",
        "/media/",
        "/healthz/",
        "/readyz/",
    )
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        u=getattr(request,"user",None)
        if not u or not u.is_authenticated or request.path.startswith(self.EXEMPT_PREFIXES):
            return self.get_response(request)
        try:
            from django.http import JsonResponse
            from django.shortcuts import redirect
            from django.urls import reverse
            from urllib.parse import urlencode
            from .app_lock import preference_for,requires_lock
            pref=preference_for(u)
            if pref.app_lock_enabled and requires_lock(request,pref):
                wants_json=(request.headers.get("X-Requested-With")=="XMLHttpRequest" or request.path.startswith("/api/"))
                unlock_url=reverse("accounts:app_lock")
                if wants_json:
                    return JsonResponse({"ok":False,"locked":True,"detail":"R-Messanger заблокирован.","unlock_url":unlock_url},status=423)
                return redirect(f"{unlock_url}?{urlencode({'next':request.get_full_path()})}")
        except Exception:
            # A migration should never make the whole application unreachable.
            pass
        return self.get_response(request)
