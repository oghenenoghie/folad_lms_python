# CBT M4-B — Worker and Source Storage Deployment Decision

**Status:** Repository audit complete; deployment decision for M4-B implementation.
**Baseline:** `main` at `021927afac087a0bf2d6a065d58c77248933ad01`.
**Scope:** Deployment readiness only. No runtime behavior, dependencies, or infrastructure are changed by this document.

## 1. Verified repository capabilities

### Background execution

The project already has the required task stack:

- `celery>=5.4,<5.5` and `redis>=5.0,<5.1` are declared in `backend/pyproject.toml`.
- `config/celery.py` creates the Celery application, loads Django settings, autodiscovers tasks, and routes `apps.*.tasks.imports.*` to the `imports` queue.
- `config/settings/base.py` sets `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` to `REDIS_URL`, with JSON serialization and a `default` queue.
- `docker-compose.yml` already defines a `celery-worker` service consuming `default,reports,imports,email_notify` and a separate `celery-beat` service.
- `infrastructure/docker/backend.Dockerfile` is explicitly shared by Django, FastAPI, Celery worker and Celery beat processes.

**Decision:** Reuse the existing Celery + Redis stack. Do not add Dramatiq, RQ, a second broker, or in-process threads. M4-B import tasks should be routed to the existing dedicated `imports` queue.

### Production deployment gap

The current root `railway.toml` explicitly configures only the Django web service. `RAILWAY_DEPLOYMENT.md` also states that the FastAPI edge service and Celery worker/beat are outside the current Railway deployment. Therefore, the existence of the Docker Compose worker does **not** mean a production Celery worker is running.

**Decision:** Before enabling asynchronous import dispatch in production, create a separate Railway service for the same repository and shared Dockerfile, with its start command set to:

```sh
celery -A config worker -l info -Q imports --concurrency=2
```

The worker service must receive the same runtime settings needed by Django: `DJANGO_SETTINGS_MODULE=config.settings.prod`, `DJANGO_SECRET_KEY`, direct `DATABASE_URL` using the application role, `REDIS_URL`, and the `STORAGE_*` variables. It must not run schema migrations; migrations remain the web/deployment release responsibility. Do not give the worker `MIGRATE_DATABASE_URL` unless a separately justified operational task requires it.

The web service must not enqueue import jobs until the worker service is deployed and verified healthy. Until then, keep the import-job feature unavailable or explicitly report that processing is not configured; never fall back to a request-process thread.

### Source file storage

The project already has a provider-agnostic storage implementation in `apps/core/storage.py`:

- `save_document()` writes bytes and returns an opaque storage key, not a URL.
- `get_file_bytes()` reads a stored object for parsers.
- `get_presigned_download_url()` generates a fresh URL on demand after the caller has performed authorization and tenant ownership checks.
- Production defaults to `STORAGE_BACKEND=s3`; the implementation uses boto3 and supports S3-compatible endpoints.
- Local Docker Compose provides MinIO; production deployment documentation specifies the existing private Neon Object Storage bucket `sms-documents`.

**Decision:** Reuse `save_document()`, `get_file_bytes()`, and `get_presigned_download_url()`. Store only an opaque key in `CBTImportJob.storage_key`. Use a tenant-prefixed key such as `cbt-imports/<organization-public-id>/<random-object-id>/<sanitized-filename>`. Do not store permanent public URLs or expose raw storage keys in API responses.

The existing generic `validate_upload()` allowlist is limited to PDF, PNG, JPEG and plain text; it is not an appropriate CSV/XLSX validator. The CBT importer must retain its own format-specific validation (including ZIP/XLSX archive limits and CSV encoding checks) before writing the source object.

## 2. M4-B implementation defaults

Use the following v1 defaults unless a later product decision explicitly changes them:

1. One import job targets exactly one organization, school, subject and class level.
2. Commit is all-valid-only: no commit while any item is invalid or unresolved.
3. Preview and validation do not create `Question`, `QuestionBlock`, or `QuestionOption` records.
4. Explicit commit creates draft questions only and uses the existing CBT question service.
5. Each item stores its committed question association so retries cannot create duplicates.
6. A worker crash leaves the persisted job recoverable; retry is an explicit state transition, not an automatic reset of a partially committed job.
7. Original source files are private and retained for a bounded period. The initial retention default is 30 days after a terminal job state; cleanup must be implemented as an auditable scheduled task and must never delete a source while its job is active.

## 3. Operational acceptance gate

Before the import upload endpoint is exposed in production:

- A dedicated Railway imports worker is deployed from the shared Dockerfile.
- Worker logs show successful broker connection and consumption of the `imports` queue.
- A staging smoke test enqueues one harmless import task and observes it complete.
- The worker can read a private source object using the stored key.
- Restarting the worker does not lose queued jobs.
- Redis and database connectivity are monitored independently.
- Worker concurrency, memory and task time limits are bounded.
- The worker runs with the application database role, not the schema-owner migration role.

## 4. Out of scope

This decision does not provision Railway services, change Railway variables, create storage buckets, or alter production infrastructure. Those operations require deployment-owner access and must be performed/verified in the Railway and Neon consoles.

It also does not implement models, migrations, API endpoints, parsers or tasks. Those are the next code milestone after this deployment decision is reviewed.
