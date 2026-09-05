# Deploying the Django app to Railway (with existing Neon Postgres)

This document is specific to this repository. It covers the **Django web
service only** (`backend/django_app`) — the FastAPI edge service, Celery
worker/beat, and the (not-yet-built) Next.js frontend described in
`docs/ARCHITECTURE.md` are out of scope for this deployment.

```
GitHub  →  Railway  →  Django web service  →  Gunicorn  →  Django  →  Neon Postgres (existing)
```

There is **no Railway Postgres service** in this setup. The database is the
existing Neon project `plain-cell-22374610` / database `neondb`
(https://console.neon.tech/app/projects/plain-cell-22374610?database=neondb).
Railway hosts only the application.

---

## 0. Repository facts this doc relies on

- Django project root: `backend/django_app`; app package: `config`
  (`config.wsgi:application`, `config.settings.{base,dev,prod,test}`).
- Dependencies are declared in `backend/pyproject.toml` (no `requirements.txt`
  — this is a `pip install .` / PEP 517 project).
- A shared Docker image already builds this correctly for
  docker-compose: `infrastructure/docker/backend.Dockerfile`. Railway is
  configured (`railway.toml` at the repo root) to build from that same
  Dockerfile rather than re-deriving a build pipeline.
- Health endpoint: **`/health/`** (also available at `/api/v1/health`, the
  pre-existing DRF endpoint). `/api/v1/ready` additionally checks DB + cache
  connectivity — useful for manual verification, not used as the Railway
  healthcheck (it would fail the deploy if Redis isn't up yet).
- **Redis is a hard requirement of the existing code**, not an optional
  cache: `apps/accounts/jwt.py` stores refresh-token records only in Redis
  (login/refresh/logout depend on it), and `apps/accounts/permissions.py`
  caches RBAC checks there too. Since this deployment adds only a Django
  web service and Neon is Postgres-only, **you must provision Redis
  separately** (Railway's Redis plugin, or an external Redis such as
  Upstash) and set `REDIS_URL`. Without it, `/health/` still returns 200,
  but login and every permission-gated API call will fail.

---

## 1. Neon connection: pooled vs. direct (important, repo-specific)

Neon gives you two connection strings for the same database: a pooled one
(host ending in `-pooler`, PgBouncer in **transaction-pooling** mode) and a
direct one.

**This application must use the DIRECT (non-pooled) connection string**,
not the pooled one. Reason, found by inspection of
`backend/django_app/apps/tenancy/`:

- Tenant isolation has a defence-in-depth Postgres layer: Row-Level
  Security policies keyed on a session GUC, `app.current_org`.
- `apps/tenancy/context.py`'s `activate_organization()` sets that GUC with
  `set_config(..., is_local=false)` — i.e. **session-scoped**, not
  transaction-scoped — once per authenticated request
  (`apps/accounts/authentication.py`), and relies on it staying set on that
  physical connection for subsequent queries in the same and later
  requests (see `apps/tenancy/apps.py`, which resets it to a safe sentinel
  only when a genuinely new physical connection opens).
- Neon's pooled endpoint does not guarantee that two transactions on the
  same client connection land on the same backend server process. A `SET`
  from one transaction can be invisible to the very next query, which
  would silently defeat RLS.

This was verified locally: with the app's own `tests/api/test_tenancy.py`
suite run against a real Postgres 16 instance via `DATABASE_URL` (direct
connection), all 5 RLS tests pass — see §Verification below.

Practical instruction: in Railway's Variables tab, set `DATABASE_URL` to
Neon's **direct** connection string (the one *without* `-pooler` in the
hostname), in the form:

```
postgresql://USER:PASSWORD@ep-xxxxxxxx.REGION.aws.neon.tech/neondb?sslmode=require
```

Get the exact string from the Neon console linked above → **Connection
Details** → toggle "Pooled connection" **off**.

`DIRECT_DATABASE_URL` is also read (and takes priority if both are set) as
an explicit alias for the same value, matching the naming convention the
repo's own `.github/workflows/neon_workflow.yml` already uses
(`db_url` vs. `db_url_with_pooler`). You only need to set one of the two.

**Two roles, two variables.** `DATABASE_URL` is what the live app (gunicorn)
connects as — a least-privilege Neon role (`sms_app` in this project) with
plain DML grants (`SELECT`/`INSERT`/`UPDATE`/`DELETE`) and no `BYPASSRLS`,
so RLS actually protects it. Schema migrations need DDL rights
(`CREATE TABLE`, `ALTER TABLE`, `CREATE POLICY`) that role deliberately
doesn't have, so `railway.toml`'s start command runs `migrate --noinput`
under a *second* variable, `MIGRATE_DATABASE_URL` — Neon's table-owning
`neondb_owner` role — via a one-command env override
(`DATABASE_URL=$MIGRATE_DATABASE_URL python manage.py migrate ...`); gunicorn
afterward still sees the service's own `DATABASE_URL`. Set both as direct
(non-pooler) connection strings, same as above. See `docs/ARCHITECTURE.md`
§7 for why one role can't do both under `FORCE ROW LEVEL SECURITY`.

---

## 2. Railway project setup

1. **Railway account**: sign in at https://railway.app (GitHub login is
   simplest since the repo is already on GitHub).
2. **Create a new Railway project** → "Deploy from GitHub repo" →
   select `oghenenoghie/folad_lms_python`.
3. Railway creates one service from the repo. Rename it to something like
   `django-web` in the service settings. **Do not add a Postgres plugin/
   service to this project** — Neon remains the database.
4. Confirm the service picks up `railway.toml` at the repo root (Railway
   auto-detects it; the build/start/healthcheck settings below come from
   that file, not the dashboard, but you can view them under Settings →
   Deploy). Also set the service's **Config-as-code file path** to
   `railway.toml` explicitly if Railway doesn't pick it up on its own —
   otherwise it defaults to auto-detected Nixpacks/Railpack, which
   mis-detects this monorepo's Django app.
5. Add a **Redis** service to the same Railway project (Railway's own Redis
   plugin is the simplest option: "+ New" → "Database" → "Add Redis").
   This is required per §0 above. It is not a violation of "only Neon for
   Postgres" — it's a different datastore the existing code already
   depends on.

## 3. Configure environment variables (Railway → your service → Variables)

Set these on the **Django web service** (not on the Redis service):

| Variable | Value | Notes |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` | Selects `prod.py` (HTTPS redirect, secure cookies, HSTS). |
| `DJANGO_SECRET_KEY` | a long random value | Generate with `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Never reuse the repo's dev default. |
| `DJANGO_DEBUG` | `False` | |
| `DJANGO_ALLOWED_HOSTS` | `your-app.up.railway.app,healthcheck.railway.app` (add your custom domain later, comma-separated) | **Must include `healthcheck.railway.app`.** Railway's internal healthcheck prober sends that as the `Host` header — not your service's real domain — when hitting `/health/` before marking a deploy healthy. Without it, Django's `DisallowedHost` check rejects the probe and the deploy fails its healthcheck even though the app is otherwise working. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://your-app.up.railway.app` (add custom domain later) | Full origin incl. scheme, comma-separated, no trailing slash. |
| `DATABASE_URL` | Neon **direct** connection string, least-privilege app role (`sms_app`) | See §1. This is what the live app serves traffic as — no `BYPASSRLS`. |
| `MIGRATE_DATABASE_URL` | Neon **direct** connection string, table-owning role (`neondb_owner`) | See §1. Used only for the `migrate --noinput` step in `railway.toml`'s start command — never by the running app. |
| `REDIS_URL` | your Railway Redis service's connection URL | Railway exposes this as a variable on the Redis service (`REDIS_URL` or similar) — reference it via Railway's variable-reference syntax (`${{Redis.REDIS_URL}}`) or copy it in manually. |
| `DJANGO_TIME_ZONE` | `UTC` | Matches repo default; change if desired. |
| `DJANGO_LOG_LEVEL` | `INFO` | |
| `JWT_ACCESS_TOKEN_TTL_MIN` | `15` | Matches repo default; only set if you want to change it. |
| `JWT_REFRESH_TOKEN_TTL_DAYS` | `7` | Same. |
| `LOGIN_LOCKOUT_THRESHOLD` | `5` | Same. |
| `LOGIN_LOCKOUT_WINDOW_MIN` | `15` | Same. |
| `MFA_REQUIRED_ROLES` | `SUPER_ADMIN,SCHOOL_ADMIN` | Same. |
| `STORAGE_BACKEND` | `s3` | Defaults to `s3` even if unset — see below, this is why the rest of this row group is required, not optional. |
| `STORAGE_BUCKET_NAME` | `sms-documents` | Already provisioned — see below. |
| `STORAGE_ACCESS_KEY` | a Neon Object Storage credential's `token_id` | See below for how to mint one. |
| `STORAGE_SECRET_KEY` | that same credential's `s3_secret_access_key` | Shown once at creation — copy it immediately. |
| `STORAGE_REGION` | `us-east-2` | Matches the Neon project's region. |
| `STORAGE_ENDPOINT_URL` | `https://<branch-id>.storage.c-5.us-east-2.aws.neon.tech` | The branch-scoped endpoint from `get_storage` / the Console's Object Storage page — see below. |

**`STORAGE_*` is required, not optional**, despite what an earlier version
of this doc said (written before any upload feature existed). Several
apps upload real files today: student photos (`apps.students`), report-
card PDFs (`apps.report_cards`), documents and assignment submissions
(`apps.documents`/`apps.assignments`), and exam question images
(`apps.examinations`). `STORAGE_BACKEND` defaults to `"s3"` — see
`config.settings.base` — so leaving these unset doesn't fall back to local
disk storage, it sends every upload to S3 with an empty access key,
which fails immediately with botocore's `AuthorizationHeaderMalformed`
(confirmed live: `/admin/students/student/<id>/change/`'s photo upload,
2026-09-04).

**This project uses Neon Object Storage** (the same Neon project as
`DATABASE_URL`, `plain-cell-22374610` / `folad_lms_db`, region
`us-east-2`) rather than a separate AWS S3/R2/Spaces account — one fewer
provider to manage, and it branches alongside the database. The bucket
(`sms-documents`, private) is already created on the project's default
branch. To finish setup:

1. In the [Neon Console](https://console.neon.tech/app/projects/plain-cell-22374610), select the branch, then **Credentials** under **Branch** in the sidebar.
2. **Create credential** → check `storage:write` (includes read) → name it (e.g. `railway-prod`).
3. Copy the four values shown (shown once only — they can't be retrieved again):
   ```
   AWS_ENDPOINT_URL_S3=https://<branch-id>.storage.c-5.us-east-2.aws.neon.tech
   AWS_ACCESS_KEY_ID=nak_live_...
   AWS_SECRET_ACCESS_KEY=nsk_live_...
   AWS_REGION=us-east-2
   ```
4. Map them onto Railway's `STORAGE_*` variables: `AWS_ACCESS_KEY_ID` → `STORAGE_ACCESS_KEY`, `AWS_SECRET_ACCESS_KEY` → `STORAGE_SECRET_KEY`, `AWS_ENDPOINT_URL_S3` → `STORAGE_ENDPOINT_URL`, `AWS_REGION` → `STORAGE_REGION`. Set `STORAGE_BUCKET_NAME=sms-documents` and `STORAGE_BACKEND=s3` directly.

If you'd rather use a different provider (AWS S3, Cloudflare R2, DigitalOcean Spaces), any S3-compatible bucket works the same way — just fill in the same five variables from that provider's console instead.

Path-style S3 addressing is required for a custom endpoint like Neon's
(bucket in the URL path, not a subdomain) — `apps/core/storage.py`'s
`_s3_client()` already sets `Config(s3={"addressing_style": "path"})`
whenever `STORAGE_ENDPOINT_URL` is set, so no extra configuration is
needed here.

`CORS_ALLOWED_ORIGINS` is still genuinely not needed: the Next.js
frontend's server-only fetchers (`djangoFetch`/`authorizedDjangoFetch`)
call this API from the Next.js server, not from the browser, so there is
no cross-origin browser request to allow.

Do **not** put any of these values into the repository. `backend/.env.example`
documents the names only, with placeholder/example values.

## 4. Build and start commands

These are already defined in `railway.toml` at the repo root — you don't
need to re-enter them in the dashboard, but they're listed here for
reference:

- **Build**: Docker build from `infrastructure/docker/backend.Dockerfile`
  (`pip install .` against `backend/pyproject.toml`, plus a `collectstatic
  --noinput` baked into the image).
- **Start** (runs `migrate --noinput` then Gunicorn):
  ```
  sh -c 'cd django_app && python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3'
  ```
- **Healthcheck path**: `/health/`

Two things about this command are load-bearing, both discovered the hard
way while getting this deployment working:

1. **The explicit `sh -c '...'` wrapper is required.** Railway invokes
   `startCommand`/`preDeployCommand` directly (exec form), not through a
   shell. `cd` is a shell builtin, not an executable, so a bare
   `cd django_app && ...` command fails immediately at the
   `CREATE_CONTAINER` stage with `The executable \`cd\` could not be
   found` — and `&&` chaining needs a shell too. This was the root cause
   of every deployment failure hit while setting this up, including ones
   that looked like database or infrastructure problems (see below).
2. **`migrate` runs as part of the start command, not a separate
   Railway "Pre-deploy command" step.** It was originally a
   `preDeployCommand` (the more common pattern — runs once before the
   new version takes traffic), but that step type produced zero captured
   output on every attempt (build logs, deploy logs, and Railway's own
   deployment Diagnosis all came back empty) even though the underlying
   cause was the same shell issue above — Railway just didn't surface an
   error for that step type the way it eventually did for
   `CREATE_CONTAINER`. `migrate --noinput` is idempotent (Django tracks
   applied migrations in `django_migrations`), so running it on every
   container start is safe — a no-op once the schema is current. If you
   want to move it back to `preDeployCommand` (with the same `sh -c`
   wrapper), that's a one-line change in `railway.toml`.

None of these run `flush`, `makemigrations`, or anything else destructive.

## 5. Deploy

Push to the branch Railway is tracking (or trigger a deploy from the
dashboard). Railway will build the image, then run `migrate` followed by
Gunicorn as the start command.

## 6. Check Railway logs

Service → **Deployments** → open the active deployment → **Deploy Logs**
(not just "Details" — the Details tab summarizes step pass/fail but the
actual log text lives under the Deploy tab). Watch for the `migrate`
output at the top, then the Gunicorn startup line. Uncaught Django
exceptions are logged to stdout (see `LOGGING` in
`config/settings/base.py`) and will appear here with a timestamp, level,
and logger name — no passwords, tokens, or credentials are logged by any
code path in this app.

If a deployment fails with zero log lines anywhere (build, deploy, and
Railway's own **Diagnosis** panel on the deployment's Details tab all
come back empty), don't assume it's a Railway platform/account issue —
that's what it looked like here at first (checked: no active incidents
on Railway's status page, no maintenance notices, container resource
metrics flat at zero), but the actual cause was the `cd`/shell problem
above. A `CREATE_CONTAINER`-stage failure with an error like `The
executable ... could not be found` is Railway telling you the exact
problem; it just doesn't always show up in the Diagnosis panel or the
Deploy Logs tab the first time — retry Diagnosis, and if that's still
empty, use the Railway MCP `railway-agent` tool (or `railway logs` /
`railway status` via the CLI) to pull the deployment's `failureStage`
and `failureError` directly.

## 7. Test `/health/`

```
curl https://your-app.up.railway.app/health/
```
Expect `{"success":true,"data":{"status":"ok"},"message":"healthy","errors":[]}`
with HTTP 200. For a deeper check (DB + Redis reachability), use
`/api/v1/ready` — it returns 503 if either dependency is unreachable, so
don't wire it as the platform healthcheck (a slow Neon cold-start or Redis
hiccup would then fail the whole deploy).

## 8. Test Django admin

Visit `https://your-app.up.railway.app/admin/`. You'll need a superuser —
Railway doesn't create one automatically (and this deployment intentionally
never runs interactive commands during deploy). Run it once, on demand,
from Railway's shell for the service (Deployments → the running deployment
→ "Shell", or `railway run` locally with the service's environment linked):

```
cd django_app && python manage.py createsuperuser
```

## 9. Test database connectivity

`/api/v1/ready`'s `checks.database` field confirms Django can open a
cursor against Neon. For a stronger check that RLS/tenant isolation itself
is intact end-to-end, log into `/admin/`, create an Organization + a user
in it, and confirm a second Organization's admin/staff cannot see the
first's data through the API.

## 10. Test static files

`GET /static/admin/css/base.css` (or any other admin asset) should return
200 with a hashed, cache-friendly filename in the `Cache-Control` header —
WhiteNoise serves these directly from the image, no separate static host
needed. Static files are baked into the image at build time
(`collectstatic` runs in the Dockerfile), so they exist even before the
container has handled its first request.

## 11. Test authentication

```
curl -X POST https://your-app.up.railway.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "..."}'
```
(check `apps/accounts/urls.py` for the exact path if this has moved). A
successful login proves both Neon (user lookup) and Redis (refresh-token
issuance) are correctly wired — this endpoint fails if either is
misconfigured.

## 12. Test file uploads

Not applicable yet — no model in this codebase defines a `FileField` or
`ImageField` as of this deployment (Milestone 3 of `docs/ARCHITECTURE.md`).
When that lands, wire up the `STORAGE_*` variables already declared in
`backend/.env.example` to an S3/R2/MinIO-compatible bucket per the
`StorageBackend` abstraction described in `docs/ARCHITECTURE.md` §14 —
don't write uploads to the container's local disk, since Railway's
filesystem is not persistent across deploys.

## 13. Configure a custom domain

Service → Settings → **Networking** → **Custom Domain** → add your domain
and create the CNAME record it gives you.

## 14. Configure DNS

At your DNS provider, add the CNAME Railway shows you, pointing to the
Railway-provided target host. Propagation is usually minutes, occasionally
longer.

## 15. HTTPS verification

Railway issues and renews the TLS certificate automatically once DNS
resolves. Then add the new domain to both `DJANGO_ALLOWED_HOSTS` and
`DJANGO_CSRF_TRUSTED_ORIGINS` (with `https://` scheme) and redeploy —
until you do, requests to the new domain will fail Django's `ALLOWED_HOSTS`
check even though TLS itself is fine.

## 16. Future deployment workflow

Every push to the tracked branch triggers: build → start (`migrate` then
Gunicorn). New migrations you commit run automatically on the next deploy;
nothing else is automatic. If you add a genuinely new required env var,
add it to `backend/.env.example` in the same PR and set it in Railway
before/at deploy time — the app will fail fast (via `env(...)`, no silent
default) if a var without a safe default is missing at runtime for a
setting you've made required.

## 17. Rollback procedure

Railway keeps previous deployments. Service → **Deployments** → find the
last known-good deployment → **Redeploy**. This rolls back application
code and static assets; it does **not** revert Postgres migrations. If the
bad deploy included a schema migration, plan the rollback with that in
mind (see §19) — Django doesn't auto-revert migrations on redeploy, and
you should treat `migrate` as forward-only in production. If a migration
truly needs to be undone, run `python manage.py migrate <app>
<previous_migration_name>` deliberately from the Railway shell — never as
part of automated pre-deploy.

## 18. Neon backup / recovery considerations

Neon takes continuous backups and supports **point-in-time restore** and
**branching from a past point in time** directly in the console
(https://console.neon.tech/app/projects/plain-cell-22374610). Before any
risky manual operation against production data:

1. Create a Neon branch from the current tip (or from a specific
   timestamp) as a safety snapshot.
2. Never run `python manage.py flush`, drop tables, or hand-edit
   production data without first doing (1).
3. This repo's `.github/workflows/neon_workflow.yml` already creates a
   throwaway Neon branch per pull request for CI/preview use — the same
   `neondatabase/create-branch-action` mechanism can be used ad hoc from
   the Neon console for a manual pre-change snapshot.

## 19. Scheduled tasks (fee reminders, etc.)

`apps.finance.tasks.notifications.send_fee_reminders` is scheduled daily
via `config/celery.py`'s `beat_schedule` — but as noted at the top of
this doc, **no Celery worker or beat process is deployed on Railway
yet**, so a beat-scheduled task alone will not actually fire in this
environment. Until a worker/beat service is added:

- Run `python manage.py send_fee_reminders` — it executes the same logic
  synchronously, in-process, no broker/worker needed.
- Wire that command into whatever scheduling this deployment already has
  (Railway's own cron/scheduled-job feature, or an external scheduler
  hitting a protected endpoint) to actually get daily reminders, rather
  than relying on Celery Beat.
- Once a real worker + beat process is deployed, `beat_schedule` takes
  over on its own and the manual command becomes redundant (safe to keep
  running either way — the cooldown in `reminder_service` prevents
  double-sending).

---

## Verification performed before writing this document

Run locally in this session (Python 3.12, a temporary local Postgres 16
instance simulating Neon's direct-connection wire protocol, and a
temporary local Redis) — not against the real Neon database, since no
Neon credentials were available or invented for this task:

| Check | Result |
|---|---|
| `pip install -e backend[dev]` (from `backend/pyproject.toml`, incl. new `dj-database-url`/`whitenoise` deps) | ✅ succeeds on Python 3.12 |
| `python manage.py check` (dev settings, SQLite) | ✅ no issues |
| `python manage.py check --deploy` (prod settings, `DATABASE_URL` set) | ✅ only the expected "test SECRET_KEY looks auto-generated" warning, using a deliberately weak test key |
| `python manage.py migrate --plan` | ✅ clean plan, no conflicts |
| `python manage.py migrate --noinput` against a real Postgres via `DATABASE_URL` | ✅ all migrations apply, including the RLS-enabling ones (`accounts.0003_enable_rls`, `schools.0003_enable_rls`) |
| `python manage.py collectstatic --noinput` (prod settings, WhiteNoise) | ✅ 162 files copied, 466 post-processed, no DB/network access needed |
| Gunicorn boot + `GET /health/` and `GET /api/v1/health` behind a simulated Railway proxy (`X-Forwarded-Proto: https`) | ✅ HTTP 200 |
| `GET /api/v1/ready` (checks DB + cache) | ✅ HTTP 200 once both Postgres and Redis were reachable; correctly returns 503 with Redis down, confirming the check is meaningful |
| Static asset served via WhiteNoise (`/static/admin/css/...`) | ✅ HTTP 200 |
| Full `pytest` suite (`backend/tests/`), including `tests/api/test_tenancy.py` (RLS/tenant isolation), against the real Postgres instance via `DATABASE_URL` | ✅ 52/53 pass — the 1 failure is a FastAPI test unrelated to this Django deployment (it reads separate `POSTGRES_*` vars not set in this run) |

Not verified (could not be, without real credentials or a Railway
account): an actual connection to the Neon database at
`plain-cell-22374610`, and an actual Railway deploy. Do the checks in
§7–§11 above after your first real deploy.

**One thing worth confirming once, against the real Neon role**: the RLS
test above only passes with a non-superuser Postgres role — Postgres
superusers bypass Row-Level Security unconditionally, even with `FORCE ROW
LEVEL SECURITY` set (which the app's migrations do set). Neon's default
role is not a literal `SUPERUSER`, but double-check this the first time
you point production at Neon: create two organizations, two users, and
confirm cross-tenant reads are actually blocked (§9 above), not just that
the app boots.
