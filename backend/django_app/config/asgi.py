import os
import sys
from pathlib import Path

# See the matching comment in manage.py: makes `import shared` (backend/shared/)
# resolve for a local (non-Docker) ASGI server too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from django.core.asgi import get_asgi_application  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
