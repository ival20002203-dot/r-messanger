import contextvars
_current_request=contextvars.ContextVar("localgram_request",default=None)
class RequestContextMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        token=_current_request.set(request)
        try:return self.get_response(request)
        finally:_current_request.reset(token)
def current_request():return _current_request.get()
