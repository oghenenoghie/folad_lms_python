# School Management System

Multi-tenant school management platform. API-driven — no frontend ships in this repo; any UI
(web, mobile) is a separate client consuming the HTTP APIs below. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full system design, module breakdown, database
catalogue, and milestone roadmap.

**Status:** Milestone 1 (repo skeleton, Docker, env config, health/readiness) complete.

## Stack

- **Django + DRF** (`backend/django_app`) — system of record: models, migrations, RBAC, auth,
  every write.
- **FastAPI** (`backend/fastapi_app`) — async edge service: reporting reads, webhooks,
  notifications, public API. Never writes domain state directly.
- **PostgreSQL, Redis, Celery, S3-compatible storage (MinIO locally)** — cross-cutting
  infrastructure, wired together in `docker-compose.yml`.

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
```

- Django API: http://localhost:8080/api/v1/
- Django Admin: http://localhost:8080/admin/
- FastAPI edge API + docs: http://localhost:8080/edge/v1/, http://localhost:8080/docs (direct
  container port also exposes `/docs`, `/redoc`)
- MinIO console: http://localhost:9001

Health/readiness:

```bash
curl http://localhost:8080/health          # nginx
curl http://localhost:8080/api/v1/health   # Django liveness
curl http://localhost:8080/api/v1/ready    # Django readiness (DB + cache)
curl http://localhost:8080/edge/v1/health  # FastAPI liveness
curl http://localhost:8080/edge/v1/ready   # FastAPI readiness (DB + cache)
```

## Local development (without Docker)

Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # localhost hostnames; requires Postgres + Redis running locally
cd django_app && python manage.py migrate && python manage.py runserver
# in another shell:
cd backend/fastapi_app && uvicorn main:app --reload --port 8001
```

Tests:

```bash
cd backend
pytest
```

### Windows, without WSL/Docker

If Docker Desktop's WSL2 backend won't start (`HCS_E_SERVICE_NOT_AVAILABLE`, a conflicting
hypervisor like VirtualBox already claiming VT-x, or the machine is too RAM-constrained for
Docker Desktop's own VM overhead — it wants 4GB+ before any containers even run), skip Docker
entirely and run everything as native Windows processes instead:

1. Install Python 3.12+ from python.org (check "Add python.exe to PATH").
2. Install PostgreSQL 16 from postgresql.org (EDB installer) — note the `postgres` superuser
   password you set during install.
3. Install [Memurai Developer](https://www.memurai.com/get-memurai) (free, Redis-compatible,
   runs as a Windows service on port 6379) — Redis has no official Windows build.
4. Create the database: open "SQL Shell (psql)" from the Start menu and run
   `CREATE DATABASE sms;`
5. In Git Bash:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/Scripts/activate   # Scripts, not bin, on Windows
   pip install -e ".[dev]"
   cp .env.example .env
   ```
   Edit `.env`: set `POSTGRES_USER=postgres` and `POSTGRES_PASSWORD=<password from step 2>`
   (reuses the superuser instead of creating a separate `sms` role).
6. `cd django_app && python manage.py migrate && python manage.py runserver 0.0.0.0:8000`
7. In a second Git Bash window: `cd backend/fastapi_app && uvicorn main:app --reload --port 8001`
   (activate the same `.venv` first).

## Repository structure

See §20 of `ARCHITECTURE.md` for the full layout and rationale.

```
backend/django_app/    # Django project: config/ (settings, urls, celery), apps/ (one per module)
backend/fastapi_app/   # FastAPI edge service: api/, services/, schemas/, dependencies/, core/
backend/shared/        # Money value object + shared enums, used by Django, Celery, and FastAPI
backend/tests/         # pytest: unit, api
infrastructure/        # Dockerfiles, nginx config, scripts
docs/                  # This file, ARCHITECTURE.md, and future module docs
```

## Next milestone

M2 — auth, users, roles, permissions, multi-tenancy (tenant-scoped managers + PostgreSQL RLS).
