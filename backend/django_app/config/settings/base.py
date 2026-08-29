"""Base Django settings shared by every environment. See dev.py / prod.py / test.py."""
from datetime import timedelta
from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
# `backend/django_app` — one level down from BASE_DIR (`backend/`). Templates
# and static source live here, not at BASE_DIR, since `backend/fastapi_app`
# is a sibling, unrelated service.
DJANGO_APP_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Railway terminates TLS at its edge proxy and forwards plain HTTP with
# X-Forwarded-Proto set, so Django needs to trust that header to know a
# request was actually HTTPS (request.is_secure(), the HSTS/SSL-redirect
# settings in prod.py, and secure-cookie flags all depend on it). Harmless
# locally: the header is simply absent from direct-to-runserver requests.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    # Must load before django.contrib.admin — it overrides admin's
    # templates/static, not the AdminSite itself, so no urls.py change.
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.tenancy",
    "apps.accounts",
    "apps.schools",
    "apps.students",
    "apps.staff",
    "apps.parents",
    "apps.academics",
    "apps.attendance",
    "apps.timetable",
    "apps.examinations",
    "apps.finance",
    "apps.library",
    "apps.inventory",
    "apps.transport",
    "apps.hostel",
    "apps.assignments",
    "apps.communication",
    "apps.documents",
    "apps.dashboards",
    "apps.reports",
    "apps.web",
]

AUTH_USER_MODEL = "accounts.User"
# See apps/accounts/backends.py: session-based auth (the admin login form,
# and now the server-rendered UI's own login — apps.web.views.WebLoginView)
# needs a backend that can reload the user across the tenant-scoped
# default manager.
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.TenantAwareModelBackend"]
LOGIN_URL = "web:login"

# --- Django Admin theme (django-unfold) ---
from apps.core.admin_nav import NAVIGATION as UNFOLD_SIDEBAR_NAVIGATION  # noqa: E402

UNFOLD = {
    "SITE_TITLE": "School Management System",
    "SITE_HEADER": "School Management System",
    "SITE_SYMBOL": "school",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "DASHBOARD_CALLBACK": "apps.core.dashboard.dashboard_callback",
    "ENVIRONMENT": "apps.core.admin.environment_badge",
    "ENVIRONMENT_TITLE_PREFIX": "apps.core.admin.environment_title_prefix",
    "SIDEBAR": {
        "show_all_applications": False,
        "show_search": True,
        "navigation": UNFOLD_SIDEBAR_NAVIGATION,
    },
    "COMMAND": {
        "search_models": True,
        "show_history": True,
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.tenancy.middleware.TenancyResetMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # See apps/web/middleware.py — activates RLS tenant context for
    # session-authenticated `/app/` requests only. Must run after
    # AuthenticationMiddleware (needs request.user resolved) and never
    # touches /api/, /admin/, or /health/.
    "apps.web.middleware.WebTenantContextMiddleware",
    # See apps/tenancy/middleware.py — the equivalent bridge for Django
    # Admin's session auth, activating RLS's cross-tenant platform-mode
    # escape hatch instead of a single organization. /admin/ only.
    "apps.tenancy.middleware.AdminPlatformModeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [DJANGO_APP_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.web.context_processors.nav_items",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# DATABASE_URL (e.g. Neon) takes priority when set — production (Railway)
# and any local dev that opts into Neon both go through this branch. With
# no DATABASE_URL, we fall back to the discrete POSTGRES_* vars that
# docker-compose and backend/.env.example already use, so local/Docker dev
# is unaffected.
#
# IMPORTANT — this must be Neon's *direct* (unpooled) connection string,
# not the "-pooler" one. apps/tenancy/context.py enforces tenant isolation
# by SET-ing the `app.current_org` Postgres session GUC (session-level,
# is_local=false) once per authenticated request, and relies on that value
# surviving for the life of the connection (see apps/tenancy/apps.py's
# connection_created reset and CONN_MAX_AGE below). Neon's pooled endpoint
# is PgBouncer in transaction-pooling mode, which does not guarantee two
# transactions on the same client connection hit the same backend session —
# a SET on one transaction can silently vanish before the next query, which
# would break RLS tenant isolation. DIRECT_DATABASE_URL is accepted as an
# explicit alias for this same requirement if you want the intent spelled
# out in your Railway variables; when both are set, DIRECT_DATABASE_URL wins.
DATABASE_URL = env("DIRECT_DATABASE_URL", default=None) or env("DATABASE_URL", default=None)

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=env.int("DB_CONN_MAX_AGE", default=60),
            conn_health_checks=True,
            ssl_require=env.bool("DB_SSL_REQUIRE", default=True),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", default="sms"),
            "USER": env("POSTGRES_USER", default="sms"),
            "PASSWORD": env("POSTGRES_PASSWORD", default="sms"),
            "HOST": env("POSTGRES_HOST", default="localhost"),
            "PORT": env("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
LANGUAGES = [("en", "English"), ("ar", "Arabic")]
TIME_ZONE = env("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [DJANGO_APP_DIR / "static"]

# Only actually used when STORAGE_BACKEND != "s3" (apps.core.storage's
# local-dev/test fallback) — production always uploads to S3 directly.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Redis: cache, Celery broker/result ---
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_DEFAULT_QUEUE = "default"

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# --- JWT access/refresh TTLs + signing key ---
JWT_ACCESS_TOKEN_TTL = timedelta(minutes=env.int("JWT_ACCESS_TOKEN_TTL_MIN", default=15))
JWT_REFRESH_TOKEN_TTL = timedelta(days=env.int("JWT_REFRESH_TOKEN_TTL_DAYS", default=7))
JWT_SECRET_KEY = env("JWT_SECRET_KEY", default=None)  # falls back to SECRET_KEY if unset

# --- Login lockout ---
LOGIN_LOCKOUT_THRESHOLD = env.int("LOGIN_LOCKOUT_THRESHOLD", default=5)
LOGIN_LOCKOUT_WINDOW = timedelta(minutes=env.int("LOGIN_LOCKOUT_WINDOW_MIN", default=15))

# Roles required to complete MFA at login, by name (accounts.Role.name).
MFA_REQUIRED_ROLES = env.list("MFA_REQUIRED_ROLES", default=["SUPER_ADMIN", "SCHOOL_ADMIN"])

# --- Object storage (S3 / R2 / MinIO), consumed by the StorageBackend protocol ---
STORAGE_BACKEND = env("STORAGE_BACKEND", default="s3")
STORAGE_BUCKET_NAME = env("STORAGE_BUCKET_NAME", default="sms-documents")
STORAGE_ENDPOINT_URL = env("STORAGE_ENDPOINT_URL", default=None)
STORAGE_REGION = env("STORAGE_REGION", default="us-east-1")
STORAGE_ACCESS_KEY = env("STORAGE_ACCESS_KEY", default="")
STORAGE_SECRET_KEY = env("STORAGE_SECRET_KEY", default="")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
