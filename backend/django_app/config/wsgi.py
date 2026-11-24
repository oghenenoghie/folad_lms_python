import os
import sys
from pathlib import Path

# See the matching comment in manage.py: makes `import shared` (backend/shared/)
# resolve for a local (non-Docker) `gunicorn config.wsgi:application` too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from django.core.wsgi import get_wsgi_application  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
