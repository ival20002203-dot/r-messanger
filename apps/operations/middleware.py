import hashlib,time
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from apps.accounts.utils import client_ip

try:
    from prometheus_client import Counter,Histogram
    HTTP_REQUESTS=Counter("localgram_http_requests_total","HTTP requests",["method","status","path_group"])
    HTTP_DURATION=Histogram("localgram_http_request_duration_seconds","HTTP request duration",["method","path_group"])
except Exception:
    HTTP_REQUESTS=HTTP_DURATION=None

def _group(path):
    if path.startswith('/api/'):return 'api'
    if path.startswith('/control/'):return 'control'
    if path.startswith('/auth/'):return 'auth'
    if '/upload/' in path:return 'upload'
    if path.startswith('/search/') or '/search/' in path:return 'search'
    if path.startswith('/c/') or path.startswith('/m/'):return 'chat'
    return 'other'

class RequestMetricsMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        started=time.perf_counter();response=self.get_response(request)
        if HTTP_REQUESTS:
            group=_group(request.path)
            HTTP_REQUESTS.labels(request.method,str(response.status_code),group).inc()
            HTTP_DURATION.labels(request.method,group).observe(max(0,time.perf_counter()-started))
        return response

def _rule(request):
    path=request.path.lower()
    method=request.method.upper()

    # Never rate-limit GET/HEAD requests that merely render authentication
    # pages.  Background AJAX calls can be redirected to /auth/login/ after a
    # session expires; counting those redirects used to lock the real login
    # page and return raw JSON 429 responses to the browser.
    if '/auth/login' in path or path.endswith('/api/v1/auth/token/'):
        if method != 'POST':
            return None
        return 'login',int(settings.RATE_LIMIT_LOGIN),300
    if 'otp' in path or path.endswith('/api/v1/auth/token/verify/'):
        if method != 'POST':
            return None
        return 'otp',8,300
    if path.endswith('/api/v1/auth/refresh/'):return 'token-refresh',max(30,int(settings.RATE_LIMIT_LOGIN)*6),300
    if '/upload/' in path:return 'upload',int(settings.RATE_LIMIT_UPLOAD),60
    if '/search/' in path:return 'search',int(settings.RATE_LIMIT_SEARCH),60
    if request.method=='POST' and (path.startswith('/api/v1/conversations/') and path.endswith('/messages/')):return 'messages',int(settings.RATE_LIMIT_MESSAGES),60
    if request.method=='POST' and (path.startswith('/c/') or path.startswith('/m/')):return 'chat-write',int(settings.RATE_LIMIT_MESSAGES),60
    return None

class RateLimitMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        if not getattr(settings,'RATE_LIMIT_ENABLED',True):return self.get_response(request)
        rule=_rule(request)
        if not rule:return self.get_response(request)
        category,limit,window=rule
        user=getattr(request,'user',None)
        identity=f"u:{user.pk}" if user and user.is_authenticated else f"ip:{client_ip(request) or 'unknown'}"
        bucket=int(time.time())//window
        raw=f"rl:{category}:{identity}:{bucket}"
        key='lg:'+hashlib.sha256(raw.encode()).hexdigest()
        if cache.add(key,1,timeout=window+5):count=1
        else:
            try:count=cache.incr(key)
            except Exception:count=1
        if count<=limit:return self.get_response(request)
        try:
            from .models import RateLimitEvent
            # Avoid one DB row for every blocked request.
            event_key=f"rl-event:{key}"
            if cache.add(event_key,1,timeout=window):
                RateLimitEvent.objects.create(user=user if user and user.is_authenticated else None,ip_address=client_ip(request),category=category,key=identity,path=request.path,count=count,limit=limit,details={"window_seconds":window})
        except Exception:pass
        return JsonResponse({"detail":"Слишком много запросов. Повторите позже.","retry_after":window},status=429)
