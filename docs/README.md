# School Management System

Multi-tenant school management platform. API-driven — no frontend ships in this repo; any UI
(web, mobile) is a separate client consuming the HTTP APIs below. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full system design, module breakdown, database
catalogue, and milestone roadmap.

**Status:** Milestone 1 (repo skeleton, env config, health/readiness) complete. Docker packaging
is deferred for now — run locally per below.

## Stack

- **Django + DRF** (`backend/django_app`) — system of record: models, migrations, RBAC, auth,
  every write.
- **FastAPI** (`backend/fastapi_app`) — async edge service: reporting reads, webhooks,
  notifications, public API. Never writes domain state directly.
- **PostgreSQL, Redis, Celery** — cross-cutting infrastructure, run directly on the host for now.

## Quickstart (local, no Docker)

Prerequisites: Python 3.12+, PostgreSQL 16 running locally, Redis running locally.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # defaults assume Postgres/Redis on localhost; adjust as needed
createdb sms            # or: psql -c "CREATE DATABASE sms;"

cd django_app
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

In a second shell, run the FastAPI edge service:

```bash
cd backend/fastapi_app
uvicorn main:app --reload --port 8001
```

Health/readiness:

```bash
curl http://localhost:8000/api/v1/health   # Django liveness
curl http://localhost:8000/api/v1/ready    # Django readiness (DB + cache)
curl http://localhost:8001/edge/v1/health  # FastAPI liveness
curl http://localhost:8001/edge/v1/ready   # FastAPI readiness (DB + cache)
```

Django Admin: http://localhost:8000/admin/ · FastAPI docs: http://localhost:8001/docs

Tests:

```bash
cd backend
pytest
```

## Repository structure

See §20 of `ARCHITECTURE.md` for the full layout and rationale (Docker/nginx pieces described
there aren't present yet — they'll return when we package this for deployment).

```
backend/django_app/    # Django project: config/ (settings, urls, celery), apps/ (one per module)
backend/fastapi_app/   # FastAPI edge service: api/, services/, schemas/, dependencies/, core/
backend/shared/        # Money value object + shared enums, used by Django, Celery, and FastAPI
backend/tests/         # pytest: unit, api
docs/                  # This file, ARCHITECTURE.md, and future module docs
```

## Next milestone

M2 — auth, users, roles, permissions, multi-tenancy (tenant-scoped managers + PostgreSQL RLS).
