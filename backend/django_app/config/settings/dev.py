from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Local desktop dev without Docker: SQLite, no Postgres server required.
# Opt-in via USE_SQLITE=true in backend/.env — Docker Compose (which
# provisions real Postgres) leaves it unset and gets the normal Postgres
# config from base.py. RLS (Milestone 2) only ever runs against Postgres,
# so USE_SQLITE trades that specific defence-in-depth layer for zero
# local setup; the app-layer TenantManager still applies either way.
if env.bool("USE_SQLITE", default=False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
