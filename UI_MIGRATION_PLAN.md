# UI Migration Plan — School Management System

Phase 1 deliverable: an audit of what actually exists in this codebase today, and a
prioritized plan for building a modern SaaS-style Django UI on top of it **without
touching any existing business logic**. Nothing in this document has been built yet —
per instructions, Phase 1 is audit + plan only.

## 1. Audit method

Read-only checks run against a clean venv (Python 3.12, project deps installed from
`backend/pyproject.toml`):

```
$ python manage.py --version          # 5.0.14
$ python manage.py check              # System check identified no issues (0 silenced)
$ git status --branch                 # clean, on main, up to date with origin/main
```

Followed by a full read of every app's `models.py`, `views.py`, `urls.py`,
`serializers.py`, `admin.py`, `services/*.py`, `permissions.py`, settings, and a
filesystem search for any template/static assets.

## 2. Current architecture (confirmed, not assumed)

- **Django 5.0.14**, **DRF 3.15**, **Python 3.12**, Postgres 16 (Neon, direct
  connection — see `railway.toml`/`RAILWAY_DEPLOYMENT.md`), Redis (cache + Celery
  broker), Argon2 password hashing.
- **This is a headless JSON API.** `django.contrib.admin` is the only server-rendered
  surface that exists. There is no template directory, no static CSS/JS asset, and no
  frontend framework anywhere in the repo (`find … -iname templates -o -iname static
  -o -iname "*.html"` returns nothing outside `django.contrib.admin`'s own bundled
  templates). `TEMPLATES` in `config/settings/base.py` is configured (`APP_DIRS=True`)
  but no app has ever populated a `templates/` directory. No `package.json`, no
  `node_modules`, no Tailwind config anywhere — confirmed via filesystem search.
- **API auth is 100% stateless JWT bearer tokens** (`apps/accounts/authentication.py`
  `JWTAuthentication`), issued/rotated by `apps/accounts/views.py` (`LoginView`,
  `RefreshView`) via `auth_service.login()`, with TOTP MFA and login-lockout support.
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` is JWT-only — there is no
  SessionAuthentication on the API surface at all.
- Django Admin, separately, uses **session-cookie auth** through a purpose-built
  `TenantAwareModelBackend` (`apps/accounts/backends.py`), added earlier this project
  specifically to make `/admin/` login work against the tenant-scoped `User` model.
- **Multi-tenancy**: every tenant-owned table carries a denormalized `organization_id`
  and is protected by Postgres Row-Level Security, keyed on the session GUC
  `app.current_org`. That GUC is set by exactly two code paths today:
  `JWTAuthentication.authenticate()` (every authenticated API request) and the login
  service. **Nothing else activates it.** This is the single most important fact for
  the UI plan — see §5.
- **Pattern conventions used consistently across every app** (must be followed, not
  reinvented, for every new piece of UI code):
  - "Thin views, fat services": all mutation logic lives in `apps/<app>/services/*.py`.
  - Response envelope `{"success", "data", "message", "errors"}` via
    `apps/core/responses.py`, and shared `Tenant*APIView` / `Envelope*Mixin` generics
    in `apps/core/generics.py`.
  - `apps/core/models.py`'s `BaseModel` (bigint PK + `public_id` UUID + soft-delete
    `deleted_at` + audit columns) — every domain model inherits it.
  - `PublicIdRelatedField` — FKs are exposed externally only by `public_id`, never PK.
  - Data-driven RBAC: `Permission` (`module.action` codes, e.g. `students.view`) →
    `Role` → `RolePermission` → `UserRole`, checked via
    `require_permission(code)` / `HasPermission`, cached in Redis per (user, org).
    **No system roles are seeded anywhere in migrations** — `Role` starts empty.
    "Administrator / Teacher / Accountant / Parent / Student" are not concrete,
    guaranteed-to-exist rows; they're names the org itself would create via the API.
    This directly affects §7's role-dashboards approach.

## 3. School-management modules that actually exist

| App | Models | What it does |
|---|---|---|
| `apps.tenancy` | `Organization` | Tenant root |
| `apps.accounts` | `User`, `Permission`, `Role`, `RolePermission`, `UserRole`, `LoginHistory`, `FailedLoginAttempt` | Auth, MFA, RBAC, audit |
| `apps.schools` | `School`, `Campus`, `AcademicYear`, `Term`, `Department` | Org's academic structure |
| `apps.students` | `Student` | Admissions/enrollment profile |
| `apps.staff` | `Staff`, `Teacher` | HR profile + teacher specialization |
| `apps.parents` | `Guardian`, `GuardianStudent` | Guardian↔student links |

That's the entire schema. **Confirmed absent** (no models, no migrations, no
endpoints): attendance, timetable/scheduling, assignments/homework, examinations,
results/gradebook, report cards, fees/finance/payments, library, transport, hostel,
communication/announcements. The master-prompt's module list names all of these — per
its own "only build what's real" instruction, this plan builds UI **only** for the six
apps above. Everything else is called out explicitly, below, as not-yet-buildable
rather than silently skipped or invented.

## 4. UI problems identified

There is no existing UI to have incremental problems — the "problem" is that the
product currently has **zero human-usable interface** beyond Django Admin (which is
explicitly scoped as the superuser ops console, not the app, and has a known RLS
visibility gap already documented in `RAILWAY_DEPLOYMENT.md`/prior session notes).
Every screen listed in the master prompt (dashboards, students, staff, parents,
academics, auth) has to be built from nothing, against real service-layer calls.

## 5. Architectural decision this plan depends on: how the new UI authenticates

Adding Django Templates/HTMX pages that call the *existing* service-layer functions
directly (not by round-tripping through the JSON API) is the right approach — it's
consistent with "thin views, fat services" and avoids inventing a second copy of any
business rule. But those new views run under session auth, and **nothing today calls
`activate_organization()` for a session-authenticated request** — only
`JWTAuthentication` does. A template view that queries `Student.objects` (the
tenant-scoped manager) under a bare Django session would silently get RLS-empty
results, exactly like the already-documented Admin RLS gap.

**Recommended fix (Phase 3, app-shell work, not done yet):** a small new middleware,
scoped to the new UI's URL namespace only (never touching `/api/`, `/admin/`, or
`/health/`), that — for an authenticated session request — resolves
`request.user.organization_id` and calls `activate_organization()` once per request,
mirroring exactly what `JWTAuthentication.authenticate()` already does. Login itself
should call `auth_service.login()` (reusing the real credential/MFA/lockout logic,
`LoginHistory` recording — nothing duplicated) to validate the user, then
`django.contrib.auth.login(request, user)` to establish the session via
`TenantAwareModelBackend` (already exists, already tested). This keeps 100% of the
auth business logic in the one place it already lives.

This is a new *infrastructure* addition (~1 middleware + 1 login view), not a change
to any existing view, model, or business rule — flagging it now because every
module's dashboard in §7 depends on it existing before real tenant data can render.

## 6. Frontend stack decision

Master prompt's preferred stack (Tailwind CSS, HTMX, Alpine.js, Lucide icons,
Chart.js) is adopted as specified. There is no Node/npm toolchain in this repo today
and none is being introduced: Tailwind will be compiled via the **standalone Tailwind
CLI binary** (no Node/npm dependency), added as a `collectstatic`-adjacent build step
in `infrastructure/docker/backend.Dockerfile`, mirroring the pattern the Dockerfile
already uses for `manage.py collectstatic`. HTMX, Alpine.js, and Lucide ship as single
vendored JS files under a new app's `static/` (no CDN dependency at runtime, consistent
with WhiteNoise already serving all static assets). Chart.js only where a real,
non-fake metric exists to plot.

## 7. Role-based dashboards — caveat

Since no `Role` rows are seeded (§2), dashboards cannot key off a fixed
`role.name in {"Administrator", "Teacher", ...}` check without inventing data that
doesn't exist. Two honest options, to confirm before Phase 4:

- **(a)** Key dashboard variants off the permission codes the signed-in user actually
  holds (`get_user_permission_codes()` — already exists, already correct) — e.g. a
  user with `students.*` and `staff.*` sees an admin-shaped dashboard; a user with only
  `students.view` on their own linked record sees a narrow one. Works today, zero new
  data.
- **(b)** Additionally seed a small set of baseline system `Role` rows (Administrator,
  Teacher, Accountant, Parent, Student) with sensible default permission bundles, as a
  new migration — this is new seed data, not a business-logic change, but it is new
  and should be a deliberate choice, not assumed.

This plan proceeds with **(a)** as the default (no schema/data changes required) and
will only add (b) if asked.

## 8. Prioritized phase plan (adapted from the master prompt's 18 phases to what's real)

1. ~~Audit~~ — this document. **Done.**
2. Design system: `templates/base.html` + reusable components (nav, buttons, forms,
   tables, cards, modals, alerts, badges, pagination, breadcrumbs, empty/loading/error
   states), Tailwind CLI build wired into the Dockerfile, HTMX/Alpine/Lucide vendored.
3. App shell + the session-auth/tenant-context bridge from §5 (sidebar, top nav, user
   menu, login page).
4. Dashboard (permission-driven per §7a, real counts only — e.g. active student count
   via `Student.objects.filter(enrollment_status="active").count()`, never placeholder
   numbers).
5. Authentication screens (login, MFA enroll/verify — wrapping the existing
   `auth_service`/`MFAEnrollView` logic, not reimplementing it).
6. Schools/academic structure (School, Campus, AcademicYear, Term, Department) — CRUD
   screens over the existing `apps.schools` services.
7. Students module.
8. Staff & Teachers module.
9. Parents/Guardians module (incl. guardian↔student linking UI).
10. Administration: Users, Roles, Permissions (thin UI over existing RBAC models).
11. Responsive/mobile pass.
12. Accessibility, performance (N+1 review — `select_related`/`prefetch_related` on
    every new queryset), and security review (CSRF on every form, permission checks
    mirrored in templates *and* still enforced server-side, no new endpoints that skip
    `require_permission`).

Modules explicitly **not** built in this plan because the backend has no data/API for
them yet: attendance, timetable, assignments, examinations/results/gradebook/report
cards, fees/finance, library, transport, hostel, communications/announcements. Adding
UI for any of these would require new models/migrations/services first, which is out
of scope for a UI-only migration and would need its own explicit go-ahead.

## 9. Non-negotiables carried into every phase

No deletion/reset of migrations or data, no changes to grading/financial calculations
(none exist yet to change), no bypassing `require_permission` server-side checks (UI
only hides actions it can't perform), every new queryset paginated and
`select_related`/`prefetch_related`'d, every destructive action confirmed client-side,
`manage.py check` / `manage.py test` / `collectstatic` run after each phase before
moving on, git status checked before each phase's changes, one commit per phase.
