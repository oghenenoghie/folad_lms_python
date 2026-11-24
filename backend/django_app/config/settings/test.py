from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES["default"]["NAME"] = "test_sms"  # noqa: F405

PASSWORD_HASHERS = [  # noqa: F405
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# No real S3/MinIO credentials in CI — apps.core.storage falls back to
# Django's own FileSystemStorage for anything other than "s3".
STORAGE_BACKEND = "local"
MEDIA_ROOT = BASE_DIR / "test-media"  # noqa: F405
MEDIA_URL = "/test-media/"
