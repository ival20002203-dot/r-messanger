import mimetypes
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate,login,logout,update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import check_password,make_password
from django.core.cache import cache
from django.contrib.sessions.models import Session
from django.shortcuts import redirect,render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse, FileResponse, Http404
from django.utils import timezone
from django.views.decorators.http import require_http_methods,require_POST

from apps.audit.services import audit
from .forms import LoginForm,PreferenceForm,ProfileForm,RegisterForm
from .models import ApiToken,DeviceSession,DeviceToken,EmailOTP,LoginEvent,PresencePrivacyException,ReservedUsername,User,UserBlock,UserPreference
from .utils import client_ip,send_otp
from .app_lock import clear_lock_session,lock_session,preference_for,requires_lock,touch_activity,unlock_session

def _event(request,email,user=None,ok=False,reason=""):
    LoginEvent.objects.create(
        user=user,email=(email or "").lower(),ip_address=client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT","")[:2000],
        successful=ok,reason=reason[:255],
    )


def _presence_timestamp(value):
    """Serialise a last-seen value in the server timezone/epoch.

    ``last_seen_at`` is normally aware UTC.  The fallback also handles legacy
    naive rows without allowing the host machine's timezone to leak into the
    response sent to clients.
    """
    if not value:
        return None, None
    if timezone.is_naive(value):
        value=timezone.make_aware(value,timezone.get_default_timezone())
    return value.isoformat(),int(value.timestamp()*1000)

@require_http_methods(["GET","POST"])
def register_view(request):
    if request.user.is_authenticated:return redirect("chat:home")
    pending=request.session.get("pending_registration") or {}
    initial=None
    editing_registration=False
    if request.method=="GET" and request.GET.get("edit")=="1" and pending:
        initial={
            "email":pending.get("email", ""),
            "display_name":pending.get("display_name", ""),
            "accept_policy":True,
        }
        editing_registration=True
    form=RegisterForm(request.POST or None,initial=initial)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data
        request.session["pending_registration"]={
            "email":d["email"],"display_name":d["display_name"],
            "password_hash":make_password(d["password1"]),
        }
        try:
            otp=send_otp(d["email"],EmailOTP.Purpose.REGISTER,request)
            request.session["pending_registration"]["otp_id"]=otp.pk
            request.session.modified=True
            audit(request,"auth.registration_otp_sent","EmailOTP",str(otp.pk),{"email":d["email"]})
            return redirect("accounts:register_verify")
        except Exception as exc:
            form.add_error(None,f"Не удалось отправить код на почту: {exc}")
    return render(request,"accounts/register.html",{
        "form":form,
        "editing_registration":editing_registration,
    })

@require_http_methods(["GET","POST"])
def register_verify(request):
    pending=request.session.get("pending_registration")
    if not pending:return redirect("accounts:register")
    error=None
    if request.method=="POST":
        code=request.POST.get("code","").strip()
        otp=EmailOTP.objects.filter(pk=pending.get("otp_id"),email=pending["email"],purpose=EmailOTP.Purpose.REGISTER).first()
        if otp and otp.verify_code(code,settings.OTP_MAX_ATTEMPTS):
            if User.objects.filter(email=pending["email"]).exists():
                request.session.pop("pending_registration",None)
                return redirect("accounts:login")
            user=User(
                email=pending["email"],username=pending["email"],display_name=pending["display_name"],
                password=pending["password_hash"],email_verified=True,
            )
            user.save();UserPreference.objects.get_or_create(user=user)
            request.session.pop("pending_registration",None)
            login(request,user)
            unlock_session(request)
            _event(request,user.email,user,True,"registration_email_verified")
            audit(request,"auth.register","User",str(user.pk),{"email":user.email})
            return redirect("chat:home")
        error="Неверный, использованный или просроченный код."
    return render(request,"accounts/verify.html",{"email":pending["email"],"error":error,"purpose":"register"})

@require_POST
def register_resend(request):
    pending=request.session.get("pending_registration")
    if not pending:return redirect("accounts:register")
    try:
        otp=send_otp(pending["email"],EmailOTP.Purpose.REGISTER,request)
        pending["otp_id"]=otp.pk;request.session["pending_registration"]=pending
        messages.success(request,"Новый код отправлен.")
    except Exception as exc:messages.error(request,str(exc))
    return redirect("accounts:register_verify")

@require_http_methods(["GET","POST"])
def login_view(request):
    if request.user.is_authenticated:return redirect("chat:home")
    form=LoginForm(request,data=request.POST or None)
    if request.method=="POST":
        email=request.POST.get("username","").lower().strip()
        throttle_key=f"login-fail:{client_ip(request)}:{email[:160]}"
        failures=int(cache.get(throttle_key,0) or 0)
        if failures>=10:
            _event(request,email,None,False,"rate_limited")
            form.add_error(None,"Слишком много неудачных попыток входа. Повторите позже.")
            return render(request,"accounts/login.html",{"form":form})
        if form.is_valid():
            cache.delete(throttle_key)
            user=form.get_user()
            if user.is_suspended or not user.can_login:
                _event(request,email,user,False,"suspended")
                form.add_error(None,"Доступ к аккаунту приостановлен.")
            elif settings.LOGIN_EMAIL_2FA or (getattr(settings,"ADMIN_EMAIL_2FA_REQUIRED",True) and user.role in {User.Role.DEVELOPER,User.Role.SUPERADMIN,User.Role.INFRA_ADMIN,User.Role.MODERATOR,User.Role.AUDITOR}):
                request.session["pending_login_user_id"]=user.pk
                try:
                    otp=send_otp(user.email,EmailOTP.Purpose.LOGIN,request)
                    request.session["pending_login_otp_id"]=otp.pk
                    audit(request,"auth.login_otp_sent","EmailOTP",str(otp.pk),{"email":user.email})
                    return redirect("accounts:login_verify")
                except Exception as exc:
                    form.add_error(None,f"Не удалось отправить код входа: {exc}")
            else:
                login(request,user)
                unlock_session(request)
                UserPreference.objects.get_or_create(user=user)
                _event(request,email,user,True,"password")
                audit(request,"auth.login","User",str(user.pk),{"email":user.email})
                return redirect(request.GET.get("next") or "chat:home")
        else:
            cache.set(throttle_key,failures+1,600)
            _event(request,email,None,False,"bad_credentials")
    return render(request,"accounts/login.html",{"form":form})

@require_http_methods(["GET","POST"])
def login_verify(request):
    uid=request.session.get("pending_login_user_id");otp_id=request.session.get("pending_login_otp_id")
    if not uid or not otp_id:return redirect("accounts:login")
    user=User.objects.filter(pk=uid,is_active=True,is_suspended=False,can_login=True).first()
    otp=EmailOTP.objects.filter(pk=otp_id,purpose=EmailOTP.Purpose.LOGIN).first()
    error=None
    if not user or not otp:return redirect("accounts:login")
    if request.method=="POST":
        if otp.verify_code(request.POST.get("code","").strip(),settings.OTP_MAX_ATTEMPTS):
            login(request,user,backend="django.contrib.auth.backends.ModelBackend")
            unlock_session(request)
            UserPreference.objects.get_or_create(user=user)
            request.session.pop("pending_login_user_id",None);request.session.pop("pending_login_otp_id",None)
            _event(request,user.email,user,True,"password+email_otp")
            audit(request,"auth.login_2fa","User",str(user.pk),{})
            return redirect("chat:home")
        error="Неверный или просроченный код."
    return render(request,"accounts/verify.html",{"email":user.email,"error":error,"purpose":"login"})

@login_required
def logout_view(request):
    # Clear server truth first, then close every still-open tab/window that owns
    # this exact Django session. This prevents an old WebSocket from reviving
    # the account as online after logout. Other devices/sessions are untouched.
    from .presence import clear_presence_session
    session_key=request.session.session_key or ""
    online,changed=clear_presence_session(request.user,session_key)
    if changed:
        _broadcast_presence_to_user_chats(request.user,online)
    if session_key:
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            layer=get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f"user_{request.user.pk}",
                    {"type":"app.event","event":"session_logout","payload":{"session_key":session_key}},
                )
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Unable to close R-Mes sockets for logout session")
    audit(request,"auth.logout","User",str(request.user.pk),{})
    logout(request)
    return redirect("accounts:login")

@login_required
@require_http_methods(["GET","POST"])
def profile_view(request):
    pref,_=UserPreference.objects.get_or_create(user=request.user)
    pf=ProfileForm(request.POST or None,request.FILES or None,instance=request.user,prefix="profile")
    pref_form=PreferenceForm(request.POST or None,instance=pref,prefix="pref")
    pw=PasswordChangeForm(request.user,request.POST or None,prefix="pw")

    if request.method=="POST":
        action=request.POST.get("action")
        if action=="profile" and pf.is_valid():
            avatar_changed="avatar" in pf.changed_data
            saved_user=pf.save()
            if avatar_changed and saved_user.avatar:
                try:
                    from apps.moderation.services import queue_avatar_scan
                    queue_avatar_scan(saved_user)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Unable to queue avatar moderation for user %s",saved_user.pk)
            messages.success(request,"Профиль и фото обновлены.")
            audit(request,"profile.update","User",str(request.user.pk),{})
            return redirect("accounts:profile")
        if action=="preferences" and pref_form.is_valid():
            pref_form.save();messages.success(request,"Настройки сохранены.")
            audit(request,"profile.preferences","UserPreference",str(pref.pk),{})
            return redirect("accounts:profile")
        if action=="password" and pw.is_valid():
            u=pw.save();update_session_auth_hash(request,u);messages.success(request,"Пароль изменён.")
            audit(request,"profile.password_change","User",str(request.user.pk),{})
            return redirect("accounts:profile")
        if action=="remove_avatar":
            if request.user.avatar:
                request.user.avatar.delete(save=False);request.user.avatar=""
                request.user.save(update_fields=["avatar"])
                audit(request,"profile.avatar_remove","User",str(request.user.pk),{})
            return redirect("accounts:profile")

    blocked=UserBlock.objects.filter(blocker=request.user).select_related("blocked")
    active_tokens=request.user.api_tokens.filter(revoked_at__isnull=True).order_by("-created_at")
    device_sessions=request.user.device_sessions.filter(revoked_at__isnull=True).order_by("-last_seen_at")
    presence_rules=PresencePrivacyException.objects.filter(owner=request.user).select_related("target")
    presence_always=[row for row in presence_rules if row.mode==PresencePrivacyException.Mode.ALWAYS]
    presence_except=[row for row in presence_rules if row.mode==PresencePrivacyException.Mode.EXCEPT]
    return render(request,"accounts/profile.html",{
        "profile_form":pf,"preference_form":pref_form,"password_form":pw,
        "blocked_rows":blocked,"active_tokens":active_tokens,"device_sessions":device_sessions,
        "login_2fa_enabled":settings.LOGIN_EMAIL_2FA,
        "app_lock_enabled":pref.app_lock_enabled,
        "app_lock_timeout_minutes":pref.app_lock_timeout_minutes,
        "app_lock_lock_on_start":pref.app_lock_lock_on_start,
        "last_seen_privacy":pref.last_seen_privacy,
        "presence_always":presence_always,"presence_except":presence_except,
    })


@login_required
@require_POST
def profile_save_api(request):
    form=ProfileForm(request.POST,request.FILES,instance=request.user,prefix="profile")
    if not form.is_valid():
        return JsonResponse({
            "ok":False,
            "errors":{k:[str(x) for x in v] for k,v in form.errors.items()},
        },status=400)
    avatar_changed="avatar" in form.changed_data
    user=form.save()
    if avatar_changed and user.avatar:
        try:
            from apps.moderation.services import queue_avatar_scan
            queue_avatar_scan(user)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Unable to queue avatar moderation for user %s",user.pk)
    audit(request,"profile.autosave","User",str(user.pk),{
        "handle":user.handle,"display_name":user.display_name,
    })
    return JsonResponse({
        "ok":True,
        "display_name":user.display_name,
        "handle":user.handle or "",
        "bio":user.bio,
        "avatar_url":user.avatar_url,
    })

@login_required
@require_POST
def preferences_save_api(request):
    pref,_=UserPreference.objects.get_or_create(user=request.user)
    form=PreferenceForm(request.POST,instance=pref,prefix="pref")
    if not form.is_valid():
        return JsonResponse({
            "ok":False,
            "errors":{k:[str(x) for x in v] for k,v in form.errors.items()},
        },status=400)
    pref=form.save()
    audit(request,"profile.preferences_autosave","UserPreference",str(pref.pk),{})
    return JsonResponse({
        "ok":True,
        "theme":pref.theme,
        "accent_color":pref.accent_color,
        "chat_background":pref.chat_background,
        "font_scale":pref.font_scale,
        "animations_enabled":pref.animations_enabled,
        "compact_mode":pref.compact_mode,
        "desktop_notifications":pref.desktop_notifications,
        "notification_sound":pref.notification_sound,
        "show_message_preview":pref.show_message_preview,
        "show_sender_name":pref.show_sender_name,
        "notify_direct_chats":pref.notify_direct_chats,
        "notify_groups":pref.notify_groups,
        "notify_channels":pref.notify_channels,
        "suppress_active_chat_notifications":pref.suppress_active_chat_notifications,
    })


@login_required
@require_POST
def presence_privacy_api(request):
    """Telegram-like presence privacy with developer-only full hiding."""
    mode=(request.POST.get("mode") or "").strip().lower()
    allowed={UserPreference.LastSeenPrivacy.EVERYBODY,UserPreference.LastSeenPrivacy.RECENTLY}
    if request.user.is_developer:
        allowed.add(UserPreference.LastSeenPrivacy.NOBODY)
    if mode not in allowed:
        return JsonResponse({"ok":False,"detail":"Этот режим недоступен для вашей роли."},status=403 if mode=="nobody" else 400)
    pref,_=UserPreference.objects.get_or_create(user=request.user)
    pref.last_seen_privacy=mode
    pref.save(update_fields=["last_seen_privacy","updated_at"])
    audit(request,"privacy.last_seen","UserPreference",str(pref.pk),{"mode":mode})
    return JsonResponse({"ok":True,"mode":mode})


@login_required
@require_POST
def presence_privacy_exception_api(request):
    action=(request.POST.get("action") or "add").strip().lower()
    mode=(request.POST.get("mode") or "").strip().lower()
    try: target_id=int(request.POST.get("target_id") or 0)
    except (TypeError,ValueError): target_id=0
    target=User.objects.filter(pk=target_id,is_active=True,is_suspended=False).first()
    if not target or target.pk==request.user.pk:
        return JsonResponse({"ok":False,"detail":"Пользователь не найден."},status=404)
    if action=="remove":
        PresencePrivacyException.objects.filter(owner=request.user,target=target).delete()
        audit(request,"privacy.last_seen_exception_remove","User",str(target.pk),{})
        return JsonResponse({"ok":True,"removed":target.pk})
    if mode not in {PresencePrivacyException.Mode.ALWAYS,PresencePrivacyException.Mode.EXCEPT}:
        return JsonResponse({"ok":False,"detail":"Некорректное исключение."},status=400)
    row,_=PresencePrivacyException.objects.update_or_create(owner=request.user,target=target,defaults={"mode":mode})
    audit(request,"privacy.last_seen_exception","User",str(target.pk),{"mode":mode})
    return JsonResponse({"ok":True,"id":row.pk,"target_id":target.pk,"mode":row.mode,"name":target.display_name,"handle":target.handle or "","email":target.email})


@login_required
@require_POST
def language_api(request):
    """Persist and activate the interface language without reinstalling the app."""
    language=(request.POST.get("language") or "").strip().lower().replace("_", "-").split("-", 1)[0]
    allowed={code for code,_label in getattr(settings, "LANGUAGES", (("ru", "Русский"),))}
    if language not in allowed:
        return JsonResponse({"ok":False,"detail":"Неподдерживаемый язык интерфейса."},status=400)
    pref,_=UserPreference.objects.get_or_create(user=request.user)
    pref.language=language
    pref.save(update_fields=["language","updated_at"])
    request.session["django_language"]=language
    request.session.modified=True
    from django.utils import translation
    translation.activate(language)
    response=JsonResponse({"ok":True,"language":language})
    response.set_cookie(
        getattr(settings,"LANGUAGE_COOKIE_NAME","rmes_language"),language,
        max_age=getattr(settings,"LANGUAGE_COOKIE_AGE",365*24*60*60),
        httponly=False,samesite="Lax",secure=not settings.DEBUG,
    )
    audit(request,"profile.language","UserPreference",str(pref.pk),{"language":language})
    return response


@login_required
def avatar_image(request,user_id):
    target=User.objects.filter(pk=user_id,is_active=True).first()
    if not target or not target.avatar:
        raise Http404("Avatar not found")
    try:
        handle=target.avatar.open("rb")
    except Exception as exc:
        raise Http404("Avatar unavailable") from exc
    content_type=mimetypes.guess_type(target.avatar.name or "")[0] or "application/octet-stream"
    response=FileResponse(handle,content_type=content_type)
    response["Cache-Control"]="private, max-age=300"
    response["X-Content-Type-Options"]="nosniff"
    return response


def _broadcast_presence_to_user_chats(user,online):
    """Push privacy-safe presence transitions to each participant's private app channel."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        from apps.chat.models import ConversationMember
        from .models import User as AccountUser
        from .presence import presence_visibility
        layer=get_channel_layer()
        if not layer:
            return
        conversation_ids=list(ConversationMember.objects.filter(user=user).values_list("conversation_id",flat=True))
        if not conversation_ids:
            return
        watcher_ids=list(ConversationMember.objects.filter(conversation_id__in=conversation_ids)
                         .exclude(user_id=user.pk).values_list("user_id",flat=True).distinct())
        if not watcher_ids:
            return
        send=async_to_sync(layer.group_send)
        fresh=AccountUser.objects.select_related("preferences").only("id","last_seen_at","role").get(pk=user.pk)
        seen=getattr(fresh,"last_seen_at",None) or timezone.now()
        seen_iso,seen_ms=_presence_timestamp(seen)
        now=timezone.now()
        exact={"user_id":user.pk,"online":bool(online),"last_seen_at":seen_iso,"last_seen_at_ms":seen_ms,
               "server_time":now.isoformat(),"server_time_ms":int(now.timestamp()*1000),
               "developer":bool(fresh.is_developer),"visibility":"exact","hidden":False}
        recent={**exact,"online":False,"last_seen_at":None,"last_seen_at_ms":None,"visibility":"recently","hidden":False}
        hidden={**exact,"online":False,"last_seen_at":None,"last_seen_at_ms":None,"visibility":"hidden","hidden":True}
        watchers=AccountUser.objects.filter(pk__in=watcher_ids).only("id","role")
        for watcher in watchers.iterator(chunk_size=200):
            visibility=presence_visibility(watcher,fresh)
            outgoing=exact if visibility=="exact" else recent if visibility=="recently" else hidden
            send(f"user_{watcher.pk}",{"type":"app.event","event":"presence","payload":outgoing})
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Unable to broadcast presence transition")


@login_required
@require_http_methods(["GET", "POST"])
def presence_api(request):
    from .presence import set_active,is_online,normalize_client_id
    source=request.POST if request.method=="POST" else request.GET
    active=(source.get("active") or "1").strip().lower() in {"1","true","yes","on"}
    client_id=normalize_client_id(source.get("client_id") or request.headers.get("X-R-Mes-Presence-Client") or request.session.session_key or "web")
    online,changed=set_active(request.user,client_id,active,request.session.session_key or "")
    if changed:
        _broadcast_presence_to_user_chats(request.user,online)
    now=timezone.now()
    # set_active may have been throttled by another window.  Read the durable
    # value back so this response cannot echo an old in-memory ORM snapshot.
    try:
        seen=User.objects.only("last_seen_at").get(pk=request.user.pk).last_seen_at
        request.user.last_seen_at=seen
    except Exception:
        seen=getattr(request.user,"last_seen_at",None)
    seen_iso,seen_ms=_presence_timestamp(seen)
    response=JsonResponse({
        "ok":True,"online":bool(is_online(request.user.pk)),"client_id":client_id,
        "server_time":now.isoformat(),"server_time_ms":int(now.timestamp()*1000),
        "last_seen_at":seen_iso,"last_seen_at_ms":seen_ms,
    })
    response["Cache-Control"]="no-store, private"
    return response


@login_required
def presence_batch_api(request):
    from .presence import snapshot, presence_label, presence_visibility
    raw=(request.GET.get("ids") or "")[:4000]
    ids=[]
    for part in raw.split(","):
        part=part.strip()
        if part.isdigit():
            ids.append(int(part))
        if len(ids)>=120:
            break
    online=snapshot(ids)
    users={u.pk:u for u in User.objects.filter(pk__in=ids).select_related("preferences").only(
        "id","last_seen_at","role","presence_active","preferences__last_seen_privacy"
    )}
    now=timezone.now()
    rows={}
    for uid in ids:
        u=users.get(uid)
        if not u:
            continue
        visibility=presence_visibility(request.user,u)
        exact=visibility=="exact"
        seen_iso,seen_ms=_presence_timestamp(u.last_seen_at if exact else None)
        visible_online=bool(online.get(uid,False)) if exact else False
        rows[str(uid)]={
            "online":visible_online,
            "hidden":visibility=="hidden",
            "visibility":visibility,
            "developer":bool(u.is_developer),
            "last_seen_at":seen_iso,
            "last_seen_at_ms":seen_ms,
            "label":presence_label(request.user,u,now=now,online=visible_online),
        }
    response=JsonResponse({"ok":True,"users":rows,"server_time":now.isoformat(),"server_time_ms":int(now.timestamp()*1000)})
    response["Cache-Control"]="no-store, private"
    return response


@login_required
@require_POST
def avatar_remove_api(request):
    if request.user.avatar:
        request.user.avatar.delete(save=False)
        request.user.avatar=""
        request.user.save(update_fields=["avatar"])
        audit(request,"profile.avatar_remove","User",str(request.user.pk),{})
    return JsonResponse({"ok":True,"avatar_url":"","initials":request.user.initials})

@login_required
@require_POST
def unblock_from_settings(request,user_id):
    target=User.objects.filter(pk=user_id).first()
    if target:
        UserBlock.objects.filter(blocker=request.user,blocked=target).delete()
        audit(request,"privacy.unblock_user","User",str(target.pk),{"email":target.email})
        messages.success(request,f"{target.display_name} разблокирован.")
    return redirect("accounts:profile")

@login_required
@require_POST
def revoke_other_sessions(request):
    current=request.session.session_key;count=0
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        if s.session_key==current:continue
        try:
            if str(s.get_decoded().get("_auth_user_id"))==str(request.user.pk):
                s.delete();count+=1
        except Exception:pass
    now=timezone.now()
    ApiToken.objects.filter(user=request.user,revoked_at__isnull=True).update(revoked_at=now)
    DeviceToken.objects.filter(user=request.user,revoked_at__isnull=True).update(revoked_at=now)
    DeviceSession.objects.filter(user=request.user,revoked_at__isnull=True).exclude(session_key=current).update(revoked_at=now,is_current=False)
    audit(request,"security.revoke_other_sessions","User",str(request.user.pk),{"web_sessions":count})
    messages.success(request,f"Остальные сессии завершены: {count}. API-токены также отозваны.")
    return redirect("accounts:profile")


@login_required
def username_check(request):
    raw=(request.GET.get("username") or "").lower().strip().lstrip("@")
    import re
    if not raw:
        return JsonResponse({"available":False,"reason":"Введите username."})
    if not re.fullmatch(r"[a-z0-9_]{4,32}",raw):
        return JsonResponse({"available":False,"reason":"4–32 символа: a-z, 0-9 и _."})
    if raw==(request.user.handle or "").lower():
        return JsonResponse({"available":True,"username":raw,"reason":"Это ваш текущий username."})
    reserved=ReservedUsername.objects.filter(username=raw,active=True).first()
    if reserved:
        if request.user.is_developer:
            owner=reserved.assigned_to
            return JsonResponse({
                "available":False,"username":raw,"reserved":True,
                "reason":f"Имя зарезервировано{f' и назначено {owner.email}' if owner else ''}.",
            })
        return JsonResponse({"available":False,"username":raw,"reason":"Этот username уже занят."})
    taken=User.objects.filter(handle=raw).exclude(pk=request.user.pk).exists()
    return JsonResponse({
        "available":not taken,
        "username":raw,
        "reserved":False,
        "reason":"Username свободен." if not taken else "Этот username уже занят.",
    })

@login_required
@require_POST
def revoke_device_session(request,device_id):
    device=DeviceSession.objects.filter(pk=device_id,user=request.user,revoked_at__isnull=True).first()
    if not device:return JsonResponse({"ok":False,"detail":"Session not found"},status=404)
    if device.session_key and device.session_key==request.session.session_key:
        return JsonResponse({"ok":False,"detail":"Текущую сессию завершайте через Выход."},status=400)
    now=timezone.now();device.revoked_at=now;device.is_current=False;device.save(update_fields=["revoked_at","is_current"])
    DeviceToken.objects.filter(device=device,revoked_at__isnull=True).update(revoked_at=now)
    if device.session_key:Session.objects.filter(session_key=device.session_key).delete()
    audit(request,"security.device_revoke","DeviceSession",str(device.pk),{"device_name":device.device_name})
    return JsonResponse({"ok":True})


APP_LOCK_TIMEOUTS={0,1,5,15,30,60}

def _safe_next(request, default="chat:home"):
    value=(request.POST.get("next") or request.GET.get("next") or "").strip()
    if value and url_has_allowed_host_and_scheme(value,allowed_hosts={request.get_host(),request.get_host().split(":")[0]},require_https=request.is_secure()):
        return value
    return reverse(default)

@login_required
@require_http_methods(["GET","POST"])
def app_lock_view(request):
    pref=preference_for(request.user)
    if not pref.app_lock_enabled or not pref.app_lock_code_hash:
        clear_lock_session(request)
        return redirect("chat:home")

    error=None
    if request.method=="POST":
        key=f"app-lock-fail:{request.user.pk}:{client_ip(request)}"
        failures=int(cache.get(key,0) or 0)
        if failures>=5:
            error="Слишком много попыток. Подождите минуту и попробуйте снова."
        else:
            code=(request.POST.get("code") or "").strip()
            if check_password(code,pref.app_lock_code_hash):
                cache.delete(key)
                unlock_session(request)
                audit(request,"security.app_lock_unlock","User",str(request.user.pk),{"client":"desktop" if request.META.get("HTTP_X_R_MES_DESKTOP") else "web"})
                return redirect(_safe_next(request))
            cache.set(key,failures+1,60)
            error="Неверный код-пароль."
    elif not requires_lock(request,pref):
        return redirect(_safe_next(request))

    return render(request,"accounts/app_lock.html",{
        "error":error,
        "next_url":_safe_next(request),
        "app_lock_timeout_minutes":pref.app_lock_timeout_minutes,
    })

@login_required
@require_POST
def app_lock_lock_api(request):
    pref=preference_for(request.user)
    if not pref.app_lock_enabled or not pref.app_lock_code_hash:
        return JsonResponse({"ok":False,"detail":"Код-пароль не настроен."},status=400)
    lock_session(request)
    audit(request,"security.app_lock_manual","User",str(request.user.pk),{"client":"desktop" if request.META.get("HTTP_X_R_MES_DESKTOP") else "web"})
    return JsonResponse({"ok":True,"locked":True,"unlock_url":reverse("accounts:app_lock")})

@login_required
@require_POST
def app_lock_activity_api(request):
    pref=preference_for(request.user)
    if not pref.app_lock_enabled:
        clear_lock_session(request)
        return JsonResponse({"ok":True,"enabled":False,"locked":False})
    if not touch_activity(request,pref):
        return JsonResponse({"ok":False,"enabled":True,"locked":True,"unlock_url":reverse("accounts:app_lock")},status=423)
    return JsonResponse({"ok":True,"enabled":True,"locked":False,"timeout_minutes":pref.app_lock_timeout_minutes})

@login_required
def app_lock_status_api(request):
    pref=preference_for(request.user)
    locked=requires_lock(request,pref) if pref.app_lock_enabled else False
    return JsonResponse({
        "ok":True,
        "enabled":bool(pref.app_lock_enabled),
        "locked":bool(locked),
        "timeout_minutes":int(pref.app_lock_timeout_minutes or 0),
        "lock_on_start":bool(pref.app_lock_lock_on_start),
        "unlock_url":reverse("accounts:app_lock"),
    },status=423 if locked else 200)

@login_required
@require_POST
def app_lock_settings_api(request):
    pref=preference_for(request.user)
    current_password=request.POST.get("current_password") or ""
    if not request.user.check_password(current_password):
        return JsonResponse({"ok":False,"detail":"Неверный пароль учётной записи."},status=400)

    enabled=(request.POST.get("enabled") or "").lower() in {"1","true","yes","on"}
    timeout_raw=request.POST.get("timeout_minutes",str(pref.app_lock_timeout_minutes or 5))
    try:timeout=int(timeout_raw)
    except (TypeError,ValueError):timeout=5
    if timeout not in APP_LOCK_TIMEOUTS:timeout=5
    lock_on_start=(request.POST.get("lock_on_start") or "").lower() in {"1","true","yes","on"}
    code=(request.POST.get("code") or "").strip()
    code_confirm=(request.POST.get("code_confirm") or "").strip()

    if enabled:
        if code or not pref.app_lock_code_hash:
            if not code.isdigit() or not (4<=len(code)<=8):
                return JsonResponse({"ok":False,"detail":"Код должен содержать от 4 до 8 цифр."},status=400)
            if code!=code_confirm:
                return JsonResponse({"ok":False,"detail":"Коды не совпадают."},status=400)
            pref.app_lock_code_hash=make_password(code)
        pref.app_lock_enabled=True
        pref.app_lock_timeout_minutes=timeout
        pref.app_lock_lock_on_start=lock_on_start
        pref.save(update_fields=["app_lock_code_hash","app_lock_enabled","app_lock_timeout_minutes","app_lock_lock_on_start","updated_at"])
        unlock_session(request)
        action="security.app_lock_enable"
    else:
        pref.app_lock_enabled=False
        pref.app_lock_code_hash=""
        pref.app_lock_timeout_minutes=5
        pref.app_lock_lock_on_start=True
        pref.save(update_fields=["app_lock_code_hash","app_lock_enabled","app_lock_timeout_minutes","app_lock_lock_on_start","updated_at"])
        clear_lock_session(request)
        action="security.app_lock_disable"

    audit(request,action,"UserPreference",str(pref.pk),{
        "enabled":pref.app_lock_enabled,
        "timeout_minutes":pref.app_lock_timeout_minutes,
        "lock_on_start":pref.app_lock_lock_on_start,
    })
    return JsonResponse({
        "ok":True,
        "enabled":pref.app_lock_enabled,
        "timeout_minutes":pref.app_lock_timeout_minutes,
        "lock_on_start":pref.app_lock_lock_on_start,
    })

@login_required
def app_lock_desktop_start(request):
    pref=preference_for(request.user)
    if pref.app_lock_enabled and pref.app_lock_code_hash and pref.app_lock_lock_on_start:
        lock_session(request)
        return redirect("accounts:app_lock")
    return redirect("chat:home")


@login_required
@require_POST
def push_token_api(request):
    import json
    try:data=json.loads(request.body.decode("utf-8")) if request.content_type=="application/json" else request.POST
    except Exception:data=request.POST
    token=str(data.get("token") or "").strip()[:512];provider=str(data.get("provider") or "").strip().lower()[:16]
    if not token or provider not in {"fcm","apns"}:return JsonResponse({"detail":"Некорректный push token."},status=400)
    from .middleware import DEVICE_COOKIE
    device_id=(request.COOKIES.get(DEVICE_COOKIE) or "")[:80]
    qs=DeviceSession.objects.filter(user=request.user,revoked_at__isnull=True)
    device=(qs.filter(device_id=device_id).order_by("-last_seen_at").first() if device_id else None) or qs.filter(session_key=request.session.session_key).order_by("-last_seen_at").first()
    if not device:return JsonResponse({"detail":"Устройство ещё не зарегистрировано. Повторите через секунду."},status=409)
    device.push_token=token;device.push_provider=provider;device.save(update_fields=["push_token","push_provider"])
    audit(request,"security.push_token_update","DeviceSession",str(device.pk),{"provider":provider})
    return JsonResponse({"ok":True,"device_id":device.pk,"provider":provider})
