from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES["default"]["NAME"] = "test_sms"  # noqa: F405

PASSWORD_HASHERS = [  # noqa: F405
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
