"""Base Django settings shared by every environment. See dev.py / prod.py / test.py."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
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
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.tenancy.middleware.TenancyResetMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

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
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
