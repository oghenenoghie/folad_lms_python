from .base import *  # noqa: F401,F403
from .base import BASE_DIR

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Local desktop dev: SQLite, no local Postgres server required. Tests (settings.test)
# and prod (settings.prod) still use Postgres per the architecture doc — this override
# is dev-only, to unblock development on machines without a working local Postgres.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
