import os
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY не задан. Укажите его в backend/.env (минимум 32 символа)."
    )

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    # ВАЖНО: daphne должен быть выше django.contrib.staticfiles, чтобы перехватить runserver.
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
    # Local apps
    "accounts",
    "collectibles",
    "news",
    "search",
    "notifications",
    "chats",
    "support",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "collectit.security.ApiOriginProtectionMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "collectit.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "collectit.wsgi.application"
ASGI_APPLICATION = "collectit.asgi.application"

# --- Database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "collectit_db"),
        "USER": os.getenv("DB_USER", "collectit_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "collectit_pass"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# --- Auth ---
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.auth.CookieJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Throttling: ограничиваем brute-force на login/register и злоупотребления платежами.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "200/hour",
        "user": "2000/hour",
        "login": "10/minute",
        "register": "5/hour",
        "payment": "10/hour",
        "support": "30/hour",
        "chat_message": "120/minute",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Гарантируем минимум 32 байта для HMAC-SHA256
    "SIGNING_KEY": SECRET_KEY.ljust(32, "k"),
}

ENABLE_LEGACY_JWT_ENDPOINTS = os.getenv("ENABLE_LEGACY_JWT_ENDPOINTS", "False").lower() in ("true", "1")
ENABLE_BEARER_JWT_AUTH = os.getenv("ENABLE_BEARER_JWT_AUTH", "False").lower() in ("true", "1")
ALLOW_WEBSOCKET_QUERY_TOKEN = os.getenv("ALLOW_WEBSOCKET_QUERY_TOKEN", "False").lower() in ("true", "1")

# --- CORS ---
_cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
if _cors_env:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    # Дефолт для локального dev — фронт на :3000
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
# Нужно для httpOnly-cookie auth: браузер пошлёт куки только если разрешены credentials.
CORS_ALLOW_CREDENTIALS = True

# --- JWT cookies ---
JWT_COOKIE_NAME         = os.getenv("JWT_COOKIE_NAME", "access_token")
JWT_REFRESH_COOKIE_NAME = os.getenv("JWT_REFRESH_COOKIE_NAME", "refresh_token")
# В DEBUG (http://localhost) кука без Secure; на проде с https — Secure=True.
JWT_COOKIE_SECURE       = os.getenv("JWT_COOKIE_SECURE", "False" if os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1") else "True").lower() in ("true", "1")
JWT_COOKIE_SAMESITE     = os.getenv("JWT_COOKIE_SAMESITE", "Lax")
JWT_COOKIE_DOMAIN       = os.getenv("JWT_COOKIE_DOMAIN", "") or None

# --- Upload limits ---
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(12 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))
USER_IMAGE_MAX_BYTES = int(os.getenv("USER_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)))
USER_IMAGE_MAX_COUNT = int(os.getenv("USER_IMAGE_MAX_COUNT", "12"))
USER_IMAGE_ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
CHAT_MESSAGE_RATE_LIMIT_PER_MINUTE = int(os.getenv("CHAT_MESSAGE_RATE_LIMIT_PER_MINUTE", "120"))

# --- Security headers (активны когда DEBUG=False) ---
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 дней
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "True").lower() in ("true", "1")
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "True").lower() in ("true", "1")
    CSRF_COOKIE_HTTPONLY = os.getenv("CSRF_COOKIE_HTTPONLY", "False").lower() in ("true", "1")
    CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")

# --- i18n ---
LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# --- Static & Media ---
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- CDEK ---
CDEK_BASE_URL = os.getenv("CDEK_BASE_URL", "https://api.edu.cdek.ru/v2")  # prod: https://api.cdek.ru/v2
CDEK_CLIENT_ID = os.getenv("CDEK_CLIENT_ID", "")
CDEK_CLIENT_SECRET = os.getenv("CDEK_CLIENT_SECRET", "")

# --- ЮKassa ---
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:3000")
ENABLE_DEMO_DEPOSIT = os.getenv("ENABLE_DEMO_DEPOSIT", "False").lower() in ("true", "1")

# --- Email verification ---
EMAIL_VERIFICATION_EXPIRE_HOURS = int(os.getenv("EMAIL_VERIFICATION_EXPIRE_HOURS", "24"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "CollectIT <no-reply@collectit.local>")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "False").lower() in ("true", "1")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ("true", "1")
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
EMAIL_NOTIFICATIONS_ENABLED = os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "True").lower() in ("true", "1", "yes")

# --- Telegram admin notifications ---
TELEGRAM_NOTIFICATIONS_ENABLED = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "True").lower() in ("true", "1", "yes")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_ADMIN_CHAT_IDS = [
    chat_id.strip()
    for chat_id in os.getenv("TELEGRAM_ADMIN_CHAT_IDS", "").replace(";", ",").split(",")
    if chat_id.strip()
]
TELEGRAM_REQUEST_TIMEOUT = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "10"))

# --- AI news import ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash").strip()
NEWS_IMPORT_SOURCE_URL = os.getenv("NEWS_IMPORT_SOURCE_URL", "https://www.numizmatik.ru/news").strip()
NEWS_IMPORT_USER_AGENT = os.getenv(
    "NEWS_IMPORT_USER_AGENT",
    "CollectITBot/1.0 (+https://localhost) Mozilla/5.0",
).strip()
NEWS_IMPORT_ENABLED = os.getenv("NEWS_IMPORT_ENABLED", "False").lower() in ("true", "1", "yes")
NEWS_IMPORT_INTERVAL_MINUTES = int(os.getenv("NEWS_IMPORT_INTERVAL_MINUTES", "360"))
NEWS_IMPORT_LIMIT = int(os.getenv("NEWS_IMPORT_LIMIT", "5"))
NEWS_IMPORT_MAX_IMAGES = int(os.getenv("NEWS_IMPORT_MAX_IMAGES", "5"))
NEWS_IMPORT_REQUEST_TIMEOUT = int(os.getenv("NEWS_IMPORT_REQUEST_TIMEOUT", "20"))
NEWS_IMPORT_IMAGE_MAX_BYTES = int(os.getenv("NEWS_IMPORT_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)))

# --- Redis / Channels / Celery ---
# Если REDIS_URL не задан, channels работают через InMemory layer (без масштабирования),
# а Celery — в eager-режиме (задачи выполняются синхронно). Это позволяет фронту работать
# одинаково и в dev без Redis, и на проде с реальным брокером.
REDIS_URL = os.getenv("REDIS_URL", "").strip()

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [{
                    "address": REDIS_URL,
                    # channels_redis waits up to 5s in BZPOPMIN. Keep the
                    # socket timeout longer so redis-py does not turn normal
                    # empty waits into websocket-disconnect exceptions.
                    "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "10")),
                }],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }

# Celery (через namespace CELERY_ читает свои настройки из этого же файла).
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL or "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = os.getenv(
    "CELERY_TASK_ALWAYS_EAGER",
    "True" if not REDIS_URL else "False",
).lower() in ("true", "1")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {}
if NEWS_IMPORT_ENABLED:
    CELERY_BEAT_SCHEDULE["import-numizmatik-news"] = {
        "task": "news.tasks.import_numizmatik_news_task",
        "schedule": max(NEWS_IMPORT_INTERVAL_MINUTES, 1) * 60,
        "kwargs": {"limit": NEWS_IMPORT_LIMIT},
    }

# --- Sentry ---
# Пустой DSN = отключено. Задаётся через SENTRY_DSN в .env.
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,
        environment=os.getenv("SENTRY_ENV", "development" if DEBUG else "production"),
    )
