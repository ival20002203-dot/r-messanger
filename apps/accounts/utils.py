import smtplib
import time
import ipaddress
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import CorporateDomain, EmailOTP, IPAccessRule

def client_ip(request):
    forwarded=request.META.get("HTTP_X_FORWARDED_FOR","")
    return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")

def domain_allowed(email):
    domain=email.lower().split("@")[-1] if "@" in email else ""
    db=set(CorporateDomain.objects.filter(active=True,registration_enabled=True).values_list("domain",flat=True))
    allowed=db or set(settings.CORP_EMAIL_DOMAINS)
    return domain in allowed

def ip_is_denied(ip):
    if not ip:return False
    try: target=ipaddress.ip_address(ip)
    except ValueError:return False
    matched=[]
    for rule in IPAccessRule.objects.filter(active=True):
        try:
            net=ipaddress.ip_network(rule.network,strict=False)
            if target in net: matched.append((net.prefixlen,rule.action))
        except ValueError:
            continue
    if not matched:return False
    matched.sort(reverse=True)
    return matched[0][1]==IPAccessRule.Action.DENY

def send_otp(email,purpose,request=None):
    cache_key=f"otp-resend:{purpose}:{email.lower()}"
    if cache.get(cache_key):
        raise ValueError("Код уже отправлен. Подождите перед повторной отправкой.")
    otp,code=EmailOTP.issue(email,purpose,settings.OTP_TTL_MINUTES)
    app_name = settings.APP_BRAND_NAME if hasattr(settings, "APP_BRAND_NAME") else "R-Messanger"
    subject=f"Код подтверждения {app_name}"
    body=render_to_string("accounts/otp_email.txt",{"code":code,"minutes":settings.OTP_TTL_MINUTES,"purpose":purpose,"app_name":app_name})
    last_exc=None
    for attempt in range(3):
        try:
            sent=send_mail(subject,body,settings.DEFAULT_FROM_EMAIL,[email],fail_silently=False)
            if sent!=1:raise RuntimeError("SMTP сервер не подтвердил отправку письма")
            last_exc=None;break
        except smtplib.SMTPAuthenticationError:
            raise
        except (smtplib.SMTPServerDisconnected,smtplib.SMTPConnectError,smtplib.SMTPResponseException,OSError) as exc:
            last_exc=exc
            if isinstance(exc,smtplib.SMTPResponseException) and int(getattr(exc,"smtp_code",500) or 500)>=500:
                raise
            if attempt<2:time.sleep(0.35*(attempt+1))
    if last_exc is not None:raise last_exc
    cache.set(cache_key,True,settings.OTP_RESEND_SECONDS)
    return otp
