# Shared image for backend-django, backend-fastapi, celery-worker, celery-beat.
# The concrete process is chosen by each service's `command:` in docker-compose.yml.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/pyproject.toml
RUN pip install --prefix=/install .

FROM base AS runtime
COPY --from=builder /install /usr/local

COPY backend/django_app /app/django_app
COPY backend/fastapi_app /app/fastapi_app
COPY backend/shared /app/shared

ENV PYTHONPATH="/app/django_app:/app/fastapi_app:/app"

# Compiles the design-system CSS (theme_src/) with the standalone Tailwind
# CLI — a single native binary, no Node/npm toolchain required or present
# in this image. Must run before collectstatic below so the compiled
# static/css/app.css gets picked up and hashed along with everything else.
RUN TAILWIND_ARCH=$(case "$(uname -m)" in aarch64|arm64) echo arm64 ;; *) echo x64 ;; esac) && \
    curl -sSL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.13/tailwindcss-linux-${TAILWIND_ARCH}" && \
    chmod +x /usr/local/bin/tailwindcss && \
    cd django_app && tailwindcss -i theme_src/input.css -o static/css/app.css -c theme_src/tailwind.config.js --minify

# Bakes hashed/compressed static assets into the image at build time (no
# DB/Redis/env vars needed — collectstatic only touches the filesystem).
# Runs as root before the chown below so the resulting files end up owned
# by appuser like everything else.
RUN cd django_app && DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
