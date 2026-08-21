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

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
