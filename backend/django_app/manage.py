#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

# backend/ (this file's grandparent) so `import shared` (backend/shared/,
# the Money value object) resolves the same way it does in Docker, where
# the image's PYTHONPATH includes /app (== backend/) explicitly. Without
# this, any local (non-Docker) `manage.py` invocation can't import shared.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
