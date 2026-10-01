import os, json
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def env(name, default=""):
    return os.getenv(name, default)
def env_bool(name, default=False):
    return env(name, "1" if default else "0").lower() in {"1","true","yes","on"}
def env_list(name, default=""):
    return [x.strip() for x in env(name, default).split(",") if x.strip()]

SECRET_KEY = env("SECRET_KEY", "dev-change-me")
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# R-Mes web UI switch. Native clients identify themselves with R-Mes headers/UA.
# Legacy R-Mes headers remain accepted during the migration window.
WEB_ACCESS_ENABLED = env_bool("WEB_ACCESS_ENABLED", True)
WEB_ACCESS_MESSAGE = env("WEB_ACCESS_MESSAGE", "Для работы используйте приложение R-Messanger.")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",
    "channels",
    "apps.accounts",
    "apps.audit",
    "apps.chat",
    "apps.moderation",
    "apps.securitycenter",
    "apps.operations",
    "apps.controlpanel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.UserLanguageMiddleware",
    "apps.accounts.middleware.WebAccessMiddleware",
    "apps.accounts.middleware.DeviceTrackingMiddleware",
    "apps.operations.middleware.RequestMetricsMiddleware",
    "apps.operations.middleware.RateLimitMiddleware",
    "apps.audit.middleware.RequestContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.AccessControlMiddleware",
    "apps.accounts.middleware.AppLockMiddleware",
]

ROOT_URLCONF = "localgram.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.accounts.context_processors.app_context",
    ]},
}]
WSGI_APPLICATION = "localgram.wsgi.application"
ASGI_APPLICATION = "localgram.asgi.application"

if env("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB","localgram"),
        "USER": env("POSTGRES_USER","localgram"),
        "PASSWORD": env("POSTGRES_PASSWORD",""),
        "HOST": env("POSTGRES_HOST","localhost"),
        "PORT": env("POSTGRES_PORT","5432"),
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE","60")),
    }}
else:
    DATABASES = {"default": {"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}

REDIS_URL = env("REDIS_URL","")
if REDIS_URL:
    CHANNEL_LAYERS = {"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[REDIS_URL]}}}
    CACHES = {"default":{"BACKEND":"django.core.cache.backends.redis.RedisCache","LOCATION":REDIS_URL}}
else:
    CHANNEL_LAYERS = {"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}}
    CACHES = {"default":{"BACKEND":"django.core.cache.backends.locmem.LocMemCache"}}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "chat:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator","OPTIONS":{"min_length":10}},
    {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru"
LANGUAGES = (
    ("ru", "Русский"),
    ("en", "English"),
    ("uz", "O‘zbekcha"),
)
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "rmes_language"
LANGUAGE_COOKIE_AGE = 365 * 24 * 60 * 60
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
USE_S3_STORAGE = env_bool("USE_S3_STORAGE", False)
if USE_S3_STORAGE:
    STORAGES = {
        "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
        "default":{"BACKEND":"localgram.storage.MinioStorage"},
    }
    AWS_ACCESS_KEY_ID=env("MINIO_ROOT_USER","localgram")
    AWS_SECRET_ACCESS_KEY=env("MINIO_ROOT_PASSWORD","")
    AWS_STORAGE_BUCKET_NAME=env("MINIO_BUCKET","localgram-media")
    AWS_S3_ENDPOINT_URL=env("MINIO_ENDPOINT","http://minio:9000")
    MINIO_PUBLIC_ENDPOINT=env("MINIO_PUBLIC_ENDPOINT","")
    AWS_S3_REGION_NAME=env("MINIO_REGION","us-east-1")
    AWS_S3_ADDRESSING_STYLE="path"
    AWS_QUERYSTRING_AUTH=True
    AWS_QUERYSTRING_EXPIRE=int(env("MINIO_URL_EXPIRE_SECONDS","3600"))
    AWS_DEFAULT_ACL=None
    AWS_S3_FILE_OVERWRITE=False
else:
    STORAGES = {
        "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
        "default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
    }
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO","https")
USE_X_FORWARDED_HOST = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)

CORP_EMAIL_DOMAINS = [x.lower() for x in env_list("CORP_EMAIL_DOMAINS","")]
LOGIN_EMAIL_2FA = env_bool("LOGIN_EMAIL_2FA", False)
OTP_TTL_MINUTES = int(env("OTP_TTL_MINUTES","10"))
OTP_RESEND_SECONDS = int(env("OTP_RESEND_SECONDS","60"))
OTP_MAX_ATTEMPTS = int(env("OTP_MAX_ATTEMPTS","5"))
MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB","100"))
try:
    RTC_ICE_SERVERS=json.loads(env("RTC_ICE_SERVERS_JSON","[]"))
except Exception:
    RTC_ICE_SERVERS=[]
if not RTC_ICE_SERVERS and env_bool("TURN_ENABLED", True):
    _turn_host=env("TURN_HOST","").strip()
    if not _turn_host:
        try:_turn_host=urlparse(env("R_MES_URL","http://127.0.0.1:8000")).hostname or "127.0.0.1"
        except Exception:_turn_host="127.0.0.1"
    _turn_user=env("TURN_USERNAME","rmes")
    _turn_password=env("TURN_PASSWORD","RMes-Turn-ChangeMe")
    RTC_ICE_SERVERS=[{
        "urls":[f"turn:{_turn_host}:3478?transport=udp",f"turn:{_turn_host}:3478?transport=tcp"],
        "username":_turn_user,"credential":_turn_password,
    }]
MESSAGE_RETENTION_DAYS = int(env("MESSAGE_RETENTION_DAYS","3650"))
MONITORING_NOTICE = env("MONITORING_NOTICE","Корпоративный мессенджер. Коммуникации могут сохраняться и проверяться.")

# Corporate 18+ control is mandatory in this build. Old production .env files
# sometimes contained disabled flags, which left uploads forever outside review.
CONTENT_MODERATION_ENABLED = True
CONTENT_MODERATION_TEXT_ENABLED = True
CONTENT_MODERATION_MEDIA_ENABLED = True
# High-recall thresholds: every hit still requires a developer decision, so the
# strict detector may intentionally produce more false-positive review cases.
CONTENT_MODERATION_THRESHOLD = min(float(env("CONTENT_MODERATION_THRESHOLD","0.20")),0.20)
CONTENT_MODERATION_COVERED_THRESHOLD = min(float(env("CONTENT_MODERATION_COVERED_THRESHOLD","0.40")),0.40)
CONTENT_MODERATION_VIDEO_FRAMES = int(env("CONTENT_MODERATION_VIDEO_FRAMES","10"))
CONTENT_MODERATION_WORKER_SLEEP = min(float(env("CONTENT_MODERATION_WORKER_SLEEP","0.25")),0.25)
CONTENT_MODERATION_POLICY_NOTICE = env("CONTENT_MODERATION_POLICY_NOTICE","Отправленный контент может автоматически анализироваться средствами корпоративной модерации и сохраняться для проверки уполномоченными администраторами.")

EMAIL_BACKEND = env("EMAIL_BACKEND","django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST","")
EMAIL_PORT = int(env("EMAIL_PORT","587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER","")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD","")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL","R-Messanger <rmes@localhost>")
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT","15"))

LOG_DIR = BASE_DIR/"logs"
LOG_DIR.mkdir(exist_ok=True)
LOGGING = {
    "version":1,
    "disable_existing_loggers":False,
    "formatters":{"verbose":{"format":"{asctime} {levelname} {name} {message}","style":"{"}},
    "handlers":{
        "console":{"class":"logging.StreamHandler","formatter":"verbose"},
        "file":{"class":"logging.handlers.RotatingFileHandler","filename":LOG_DIR/"rmes.log","maxBytes":10*1024*1024,"backupCount":10,"formatter":"verbose"},
    },
    "root":{"handlers":["console","file"],"level":"INFO"},
}

CLAMAV_HOST=env("CLAMAV_HOST","clamav")
CLAMAV_PORT=int(env("CLAMAV_PORT","3310"))
SECURITY_WORKER_SLEEP=float(env("SECURITY_WORKER_SLEEP","1.0"))
DLP_ENABLED=env_bool("DLP_ENABLED",True)
ACCESS_TOKEN_MINUTES=int(env("ACCESS_TOKEN_MINUTES","30"))
REFRESH_TOKEN_DAYS=int(env("REFRESH_TOKEN_DAYS","30"))


CONTENT_MODERATION_OCR_ENABLED=env_bool("CONTENT_MODERATION_OCR_ENABLED",True)
CONTENT_MODERATION_OCR_LANG=env("CONTENT_MODERATION_OCR_LANG","eng+rus")

DLP_MAX_PARSE_MB=int(env("DLP_MAX_PARSE_MB","25"))

CONTENT_MODERATION_VIDEO_OCR_FRAMES=int(env("CONTENT_MODERATION_VIDEO_OCR_FRAMES","4"))

# Localgram v7 reliability / operations
METRICS_ENABLED=env_bool("METRICS_ENABLED",True)
METRICS_TOKEN=env("METRICS_TOKEN","")
RATE_LIMIT_ENABLED=env_bool("RATE_LIMIT_ENABLED",True)
RATE_LIMIT_LOGIN=int(env("RATE_LIMIT_LOGIN","10"))
RATE_LIMIT_SEARCH=int(env("RATE_LIMIT_SEARCH","120"))
RATE_LIMIT_UPLOAD=int(env("RATE_LIMIT_UPLOAD","30"))
RATE_LIMIT_MESSAGES=int(env("RATE_LIMIT_MESSAGES","80"))
ANTI_SPAM_ENABLED=env_bool("ANTI_SPAM_ENABLED",True)
ANTI_SPAM_DUPLICATE_LIMIT=int(env("ANTI_SPAM_DUPLICATE_LIMIT","8"))
ANTI_SPAM_WINDOW_SECONDS=int(env("ANTI_SPAM_WINDOW_SECONDS","60"))
FILE_PREVIEW_MAX_MB=int(env("FILE_PREVIEW_MAX_MB","25"))
SCHEDULED_POST_WORKER_SLEEP=float(env("SCHEDULED_POST_WORKER_SLEEP","2.0"))
CLIENT_UPDATE_API_PUBLIC=env_bool("CLIENT_UPDATE_API_PUBLIC",True)

# R-Mes client release channel. Native artifacts can be copied here on the server.
try:
    APP_VERSION=(BASE_DIR/"VERSION").read_text(encoding="utf-8").strip() or "15.1.1"
except Exception:
    APP_VERSION="15.1.1"
CLIENT_UPDATE_DIR=Path(env("CLIENT_UPDATE_DIR",str(BASE_DIR/"client_updates")))
CLIENT_UPDATE_DIR.mkdir(parents=True,exist_ok=True)

# Native mobile push (optional). Chat delivery never depends on these providers.
PUSH_ENABLED = env_bool("PUSH_ENABLED", False)
FCM_PROJECT_ID = env("FCM_PROJECT_ID", "")
FCM_SERVICE_ACCOUNT_FILE = env("FCM_SERVICE_ACCOUNT_FILE", "")
APNS_KEY_FILE = env("APNS_KEY_FILE", "")
APNS_KEY_ID = env("APNS_KEY_ID", "")
APNS_TEAM_ID = env("APNS_TEAM_ID", "")
APNS_BUNDLE_ID = env("APNS_BUNDLE_ID", "uz.rmes.ios")
APNS_USE_SANDBOX = env_bool("APNS_USE_SANDBOX", True)
CALL_AUDIO_RECORDING_ENABLED = env_bool("CALL_AUDIO_RECORDING_ENABLED", False)
CALL_RECORDING_MAX_MB = int(env("CALL_RECORDING_MAX_MB", "250"))
ADMIN_EMAIL_2FA_REQUIRED = env_bool("ADMIN_EMAIL_2FA_REQUIRED", not DEBUG)
