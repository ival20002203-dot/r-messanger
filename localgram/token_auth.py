from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

@database_sync_to_async
def _user_for_token(raw):
    if not raw:return AnonymousUser()
    from apps.accounts.models import DeviceToken,ApiToken
    dt=DeviceToken.authenticate_access(raw)
    if dt and dt.user.is_active and dt.user.can_login and not dt.user.is_suspended:return dt.user
    legacy=ApiToken.authenticate(raw)
    if legacy and legacy.user.is_active and legacy.user.can_login and not legacy.user.is_suspended:return legacy.user
    return AnonymousUser()

class TokenAuthMiddleware:
    def __init__(self,inner):self.inner=inner
    async def __call__(self,scope,receive,send):
        if not scope.get("user") or not scope["user"].is_authenticated:
            raw=""
            qs=parse_qs(scope.get("query_string",b"").decode("utf-8",errors="ignore"))
            raw=(qs.get("access_token") or qs.get("token") or [""])[0]
            if not raw:
                for key,val in scope.get("headers",[]):
                    if key.lower()==b"authorization":
                        text=val.decode("utf-8",errors="ignore")
                        if text.lower().startswith("bearer "):raw=text.split(" ",1)[1].strip()
            if raw:scope["user"]=await _user_for_token(raw)
        return await self.inner(scope,receive,send)
