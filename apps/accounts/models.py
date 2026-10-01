import hashlib, secrets, uuid
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from .managers import UserManager

def avatar_path(instance, filename):
    ext=Path(filename).suffix.lower()[:10] or ".jpg"
    return f"avatars/{instance.pk or 'new'}/{uuid.uuid4().hex}{ext}"

class User(AbstractUser):
    class Role(models.TextChoices):
        DEVELOPER="developer","Разработчик"
        SUPERADMIN="superadmin","Суперадминистратор"
        INFRA_ADMIN="infra_admin","Администратор инфраструктуры"
        MODERATOR="moderator","Модератор"
        AUDITOR="auditor","Аудитор"
        USER="user","Пользователь"

    email=models.EmailField(unique=True)
    handle=models.CharField(max_length=32,unique=True,null=True,blank=True)
    display_name=models.CharField(max_length=150,blank=True)
    bio=models.CharField(max_length=220,blank=True)
    avatar=models.ImageField(upload_to=avatar_path,blank=True)
    role=models.CharField(max_length=20,choices=Role.choices,default=Role.USER)
    custom_role=models.ForeignKey("RoleProfile",null=True,blank=True,on_delete=models.SET_NULL,related_name="users")
    is_suspended=models.BooleanField(default=False)
    suspend_reason=models.CharField(max_length=255,blank=True)
    can_login=models.BooleanField(default=True)
    can_send_messages=models.BooleanField(default=True)
    can_create_groups=models.BooleanField(default=True)
    can_upload_files=models.BooleanField(default=True)
    can_start_direct_chats=models.BooleanField(default=True)
    can_make_calls=models.BooleanField(default=True)
    email_verified=models.BooleanField(default=False)
    last_seen_at=models.DateTimeField(null=True,blank=True)
    # Durable fallback for presence when Redis is unavailable. Redis still keeps
    # the per-window leases; this flag prevents a broken cache from freezing the
    # old "last seen" value forever.
    presence_active=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD="email"
    REQUIRED_FIELDS=[]
    objects=UserManager()

    def save(self,*args,**kwargs):
        self.email=(self.email or "").lower().strip()
        self.username=self.email
        if self.handle:
            self.handle=self.handle.lower().strip().lstrip("@")
        if not self.display_name and self.email:
            self.display_name=self.email.split("@")[0]
        super().save(*args,**kwargs)

    @property
    def initials(self):
        parts=(self.display_name or self.email).split()
        return "".join(x[0] for x in parts[:2]).upper() or "U"

    @property
    def avatar_url(self):
        if not self.avatar:
            return ""
        try:
            from django.urls import reverse
            version=(self.avatar.name or "").rsplit("/",1)[-1].split(".",1)[0][-12:]
            return f"{reverse('accounts:avatar_image',args=[self.pk])}?v={version}"
        except Exception:
            try:
                return self.avatar.url
            except Exception:
                return ""

    @property
    def is_developer(self):
        return self.role==self.Role.DEVELOPER

    def has_capability(self,capability):
        from .rbac import capabilities_for
        return capability in capabilities_for(self)

    @property
    def is_control_admin(self):
        return self.has_capability("control.view")

    @property
    def can_modify_system(self):
        return self.has_capability("control.write")

    @property
    def can_view_backups(self):
        return self.has_capability("backup.view")

    @property
    def can_manage_security(self):
        return self.has_capability("security.manage")

    @property
    def can_view_users(self):
        return self.has_capability("users.view")

    @property
    def can_manage_users(self):
        return self.has_capability("users.manage")

    @property
    def can_manage_policies(self):
        return self.has_capability("policies.manage")

    @property
    def can_view_security(self):
        return self.has_capability("security.view")

    @property
    def can_view_audit(self):
        return self.has_capability("audit.view")

    @property
    def can_view_chat_audit(self):
        return self.has_capability("chat.audit")

    @property
    def is_online(self):
        try:
            from .presence import is_online
            return is_online(self.pk)
        except Exception:
            return bool(self.presence_active and self.last_seen_at and (timezone.now()-self.last_seen_at).total_seconds()<90)

    def __str__(self): return self.display_name or self.email

class RoleProfile(models.Model):
    name=models.CharField(max_length=80,unique=True)
    slug=models.SlugField(max_length=80,unique=True)
    permissions=models.JSONField(default=list,blank=True)
    description=models.CharField(max_length=255,blank=True)
    active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="role_profiles_updated")
    class Meta:ordering=["name"]
    def save(self,*args,**kwargs):
        from .rbac import CAPABILITIES
        self.permissions=sorted({x for x in (self.permissions or []) if x in CAPABILITIES and x!="rbac.manage"})
        super().save(*args,**kwargs)
    def __str__(self):return self.name

class UserPreference(models.Model):
    class Language(models.TextChoices):
        RU="ru","Русский"
        EN="en","English"
        UZ="uz","O‘zbekcha"
    class Theme(models.TextChoices):
        DARK="dark","Ночная"
        LIGHT="light","Дневная"
        TINTED="tinted","Цветная"
        SYSTEM="system","Системная"
    class Accent(models.TextChoices):
        BLUE="blue","Синий"
        CYAN="cyan","Голубой"
        VIOLET="violet","Фиолетовый"
        PINK="pink","Розовый"
        ORANGE="orange","Оранжевый"
        RED="red","Красный"
        SLATE="slate","Графитовый"
    class ChatBackground(models.TextChoices):
        RMES="rmes","R-Mes Blue"
        CLEAN="clean","Чистый"
        GRADIENT="gradient","Градиент"
        DOTS="dots","Точки"
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="preferences")
    language=models.CharField(max_length=5,choices=Language.choices,default=Language.RU)
    theme=models.CharField(max_length=10,choices=Theme.choices,default=Theme.DARK)
    class LastSeenPrivacy(models.TextChoices):
        EVERYBODY="everybody","Точное время"
        RECENTLY="recently","Недавно"
        NOBODY="nobody","Скрыто"

    accent_color=models.CharField(max_length=12,choices=Accent.choices,default=Accent.BLUE)
    chat_background=models.CharField(max_length=12,choices=ChatBackground.choices,default=ChatBackground.RMES)
    last_seen_privacy=models.CharField(max_length=12,choices=LastSeenPrivacy.choices,default=LastSeenPrivacy.EVERYBODY)
    font_scale=models.PositiveSmallIntegerField(default=100)
    animations_enabled=models.BooleanField(default=True)
    desktop_notifications=models.BooleanField(default=True)
    notification_sound=models.BooleanField(default=True)
    show_message_preview=models.BooleanField(default=True)
    show_sender_name=models.BooleanField(default=True)
    notify_direct_chats=models.BooleanField(default=True)
    notify_groups=models.BooleanField(default=True)
    notify_channels=models.BooleanField(default=True)
    suppress_active_chat_notifications=models.BooleanField(default=True)
    enter_to_send=models.BooleanField(default=True)
    compact_mode=models.BooleanField(default=False)
    animated_emoji=models.BooleanField(default=True)
    auto_download_images=models.BooleanField(default=True)
    auto_download_files=models.BooleanField(default=False)
    # Separate UI passcode. The value is always stored as a Django password hash.
    app_lock_enabled=models.BooleanField(default=False)
    app_lock_code_hash=models.CharField(max_length=256,blank=True)
    app_lock_timeout_minutes=models.PositiveSmallIntegerField(default=5)
    app_lock_lock_on_start=models.BooleanField(default=True)
    updated_at=models.DateTimeField(auto_now=True)

class PresencePrivacyException(models.Model):
    class Mode(models.TextChoices):
        ALWAYS="always","Всегда показывать"
        EXCEPT="except","Не показывать точное время"

    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="presence_privacy_rules")
    target=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="presence_visibility_rules")
    mode=models.CharField(max_length=12,choices=Mode.choices)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        constraints=[
            models.UniqueConstraint(fields=["owner","target"],name="unique_presence_privacy_exception"),
            models.CheckConstraint(condition=~models.Q(owner=models.F("target")),name="prevent_self_presence_exception"),
        ]
        ordering=["target__display_name","target__email"]


class UserBlock(models.Model):
    blocker=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="blocked_users")
    blocked=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="blocked_by_users")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[
            models.UniqueConstraint(fields=["blocker","blocked"],name="unique_user_block"),
            models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")),name="prevent_self_block"),
        ]
        ordering=["-created_at"]


class ReservedUsername(models.Model):
    class Category(models.TextChoices):
        SYSTEM="system","Системные"
        OFFICIAL="official","Официальные / бренд"
        ROLES="roles","Должности и подразделения"
        SECURITY="security","Безопасность"
        SERVICE="service","Сервисы и инфраструктура"
        CHANNELS="channels","Служебные каналы"
        POPULAR="popular","Популярные никнеймы"
        PRESTIGE="prestige","Короткие / статусные"
        CUSTOM="custom","Пользовательские"

    class Source(models.TextChoices):
        BUILTIN="builtin","Встроенный каталог"
        CUSTOM="custom","Добавлен администратором"

    username=models.CharField(max_length=32,unique=True,db_index=True)
    category=models.CharField(max_length=16,choices=Category.choices,default=Category.CUSTOM,db_index=True)
    source=models.CharField(max_length=10,choices=Source.choices,default=Source.CUSTOM)
    active=models.BooleanField(default=True,db_index=True)
    note=models.CharField(max_length=255,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reserved_usernames_created")
    assigned_to=models.OneToOneField(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reserved_username_assignment")
    assigned_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reserved_usernames_assigned")
    assigned_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        ordering=["username"]

    @staticmethod
    def normalize(value):
        import re
        value=(value or "").lower().strip().lstrip("@")
        value=re.sub(r"[^a-z0-9_]+","_",value)
        value=re.sub(r"_+","_",value).strip("_")
        return value[:32]

    def save(self,*args,**kwargs):
        self.username=self.normalize(self.username)
        super().save(*args,**kwargs)

    def __str__(self):
        return f"@{self.username}"

class CorporateDomain(models.Model):
    domain=models.CharField(max_length=190,unique=True)
    active=models.BooleanField(default=True)
    registration_enabled=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        self.domain=self.domain.lower().strip().lstrip("@")
        super().save(*args,**kwargs)
    def __str__(self): return self.domain

class EmailOTP(models.Model):
    class Purpose(models.TextChoices):
        REGISTER="register","Регистрация"
        LOGIN="login","Вход"
        SECURITY="security","Безопасность"
    email=models.EmailField(db_index=True)
    purpose=models.CharField(max_length=20,choices=Purpose.choices)
    code_hash=models.CharField(max_length=64)
    expires_at=models.DateTimeField()
    attempts=models.PositiveSmallIntegerField(default=0)
    used_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls,email,purpose,ttl_minutes=10):
        code=f"{secrets.randbelow(1000000):06d}"
        cls.objects.filter(email=email.lower(),purpose=purpose,used_at__isnull=True).update(used_at=timezone.now())
        obj=cls.objects.create(
            email=email.lower(),purpose=purpose,
            code_hash=hashlib.sha256(code.encode()).hexdigest(),
            expires_at=timezone.now()+timedelta(minutes=ttl_minutes),
        )
        return obj,code

    def verify_code(self,code,max_attempts=5):
        if self.used_at or timezone.now()>self.expires_at or self.attempts>=max_attempts:
            return False
        self.attempts+=1
        ok=secrets.compare_digest(self.code_hash,hashlib.sha256((code or "").encode()).hexdigest())
        if ok:self.used_at=timezone.now()
        self.save(update_fields=["attempts","used_at"])
        return ok

class LoginEvent(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    email=models.EmailField(blank=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True)
    user_agent=models.TextField(blank=True)
    successful=models.BooleanField(default=False)
    reason=models.CharField(max_length=255,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=["-created_at"]
        indexes=[models.Index(fields=["email","created_at"])]

class IPAccessRule(models.Model):
    class Action(models.TextChoices):
        ALLOW="allow","Разрешить"
        DENY="deny","Запретить"
    network=models.CharField(max_length=64,unique=True,help_text="IP или CIDR, например 10.10.0.0/16")
    action=models.CharField(max_length=10,choices=Action.choices,default=Action.DENY)
    note=models.CharField(max_length=255,blank=True)
    active=models.BooleanField(default=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)

class ApiToken(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="api_tokens")
    name=models.CharField(max_length=100,default="device")
    token_hash=models.CharField(max_length=64,unique=True)
    prefix=models.CharField(max_length=12,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)
    last_used_at=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    @classmethod
    def issue(cls,user,name="device"):
        raw=secrets.token_urlsafe(36)
        obj=cls.objects.create(user=user,name=name,token_hash=hashlib.sha256(raw.encode()).hexdigest(),prefix=raw[:12])
        return obj,raw
    @classmethod
    def authenticate(cls,raw):
        obj=cls.objects.select_related("user").filter(token_hash=hashlib.sha256(raw.encode()).hexdigest(),revoked_at__isnull=True).first()
        if obj:
            obj.last_used_at=timezone.now();obj.save(update_fields=["last_used_at"])
        return obj


class DeviceSession(models.Model):
    class Trust(models.TextChoices):
        NEW="new","Новое"
        TRUSTED="trusted","Доверенное"
        SUSPICIOUS="suspicious","Подозрительное"
        BLOCKED="blocked","Заблокированное"
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="device_sessions")
    session_key=models.CharField(max_length=64,blank=True,db_index=True)
    device_id=models.CharField(max_length=80,blank=True,db_index=True)
    device_name=models.CharField(max_length=120,blank=True)
    platform=models.CharField(max_length=40,blank=True)
    browser=models.CharField(max_length=80,blank=True)
    ip_address=models.GenericIPAddressField(null=True,blank=True)
    user_agent=models.TextField(blank=True)
    push_token=models.CharField(max_length=512,blank=True)
    push_provider=models.CharField(max_length=16,blank=True)
    last_seen_at=models.DateTimeField(default=timezone.now,db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)
    revoked_at=models.DateTimeField(null=True,blank=True)
    is_current=models.BooleanField(default=False)
    trust_status=models.CharField(max_length=16,choices=Trust.choices,default=Trust.NEW,db_index=True)
    trust_reason=models.CharField(max_length=255,blank=True)
    class Meta:
        ordering=["-last_seen_at"]
        indexes=[models.Index(fields=["user","last_seen_at"])]

    @property
    def active(self):
        return self.revoked_at is None

class DeviceToken(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="device_tokens")
    device=models.ForeignKey(DeviceSession,null=True,blank=True,on_delete=models.CASCADE,related_name="tokens")
    access_hash=models.CharField(max_length=64,unique=True,db_index=True)
    refresh_hash=models.CharField(max_length=64,unique=True,db_index=True)
    access_prefix=models.CharField(max_length=12,db_index=True)
    refresh_prefix=models.CharField(max_length=12,db_index=True)
    access_expires_at=models.DateTimeField(db_index=True)
    refresh_expires_at=models.DateTimeField(db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)
    last_used_at=models.DateTimeField(null=True,blank=True)
    revoked_at=models.DateTimeField(null=True,blank=True)

    @classmethod
    def issue(cls,user,device=None,access_minutes=30,refresh_days=30):
        access=secrets.token_urlsafe(36);refresh=secrets.token_urlsafe(48);now=timezone.now()
        obj=cls.objects.create(
            user=user,device=device,access_hash=hashlib.sha256(access.encode()).hexdigest(),
            refresh_hash=hashlib.sha256(refresh.encode()).hexdigest(),access_prefix=access[:12],refresh_prefix=refresh[:12],
            access_expires_at=now+timedelta(minutes=access_minutes),refresh_expires_at=now+timedelta(days=refresh_days),
        )
        return obj,access,refresh

    @classmethod
    def authenticate_access(cls,raw):
        if not raw:return None
        h=hashlib.sha256(raw.encode()).hexdigest();now=timezone.now()
        obj=(cls.objects.select_related("user","device")
             .filter(access_hash=h,revoked_at__isnull=True,access_expires_at__gt=now)
             .filter(models.Q(device__isnull=True)|models.Q(device__revoked_at__isnull=True))
             .exclude(device__trust_status=DeviceSession.Trust.BLOCKED)
             .first())
        if obj:
            obj.last_used_at=now;obj.save(update_fields=["last_used_at"]);return obj
        return None

    @classmethod
    def refresh(cls,raw):
        if not raw:return None,None,None
        h=hashlib.sha256(raw.encode()).hexdigest();now=timezone.now()
        obj=(cls.objects.select_related("user","device")
             .filter(refresh_hash=h,revoked_at__isnull=True,refresh_expires_at__gt=now)
             .filter(models.Q(device__isnull=True)|models.Q(device__revoked_at__isnull=True))
             .exclude(device__trust_status=DeviceSession.Trust.BLOCKED)
             .first())
        if not obj:return None,None,None
        obj.revoked_at=now;obj.save(update_fields=["revoked_at"] )
        return cls.issue(obj.user,obj.device)

class AppSetting(models.Model):
    key=models.CharField(max_length=120,unique=True)
    value=models.TextField(blank=True)
    description=models.CharField(max_length=255,blank=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):return self.key
