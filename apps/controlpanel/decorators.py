from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def control_required(write=False,capability=None):
    def deco(view):
        @wraps(view)
        def wrapped(request,*a,**kw):
            if not request.user.is_authenticated:return redirect("accounts:login")
            if not request.user.is_control_admin:return HttpResponseForbidden("Control Center access denied.")
            required=capability or ("control.write" if write else "control.view")
            if not request.user.has_capability(required):return HttpResponseForbidden("Insufficient role capability.")
            return view(request,*a,**kw)
        return wrapped
    return deco

def developer_required(view):
    @wraps(view)
    def wrapped(request,*a,**kw):
        if not request.user.is_authenticated:return redirect("accounts:login")
        if not request.user.is_developer:return HttpResponseForbidden("Developer-only area.")
        return view(request,*a,**kw)
    return wrapped
