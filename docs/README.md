# School Management System

Multi-tenant school management platform. The backend (`backend/`) is API-driven — see the
endpoint tables below. Two UIs consume it: a session-authenticated, server-rendered Django UI
under `/app/` (`backend/django_app/apps/web`, see `UI_MIGRATION_PLAN.md`) and a separate Next.js
app (`frontend/`, see `frontend/README.md`). See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the
full system design, module breakdown, database catalogue, and milestone roadmap.

**Status:** Milestone 10 (assignments, communication, notifications, documents) complete.
Milestone 9 (library, inventory, transport, hostel), Milestone 8 (fees, invoices, payments,
receipts, finance reports), Milestone 7 (examinations, assessments, results, report cards),
Milestone 6 (attendance, timetable), Milestone 5 (classes, sections, subjects, enrollment),
Milestone 4 (students, parents/guardians, staff, teachers), Milestone 3 (schools, campuses,
academic years, terms, departments), Milestone 2 (auth, RBAC, multi-tenancy), and Milestone 1
(repo skeleton, Docker, env config, health/readiness) complete.

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

## Auth (Milestone 2)

All under `/api/v1/auth/`:

| Endpoint | Method | Notes |
|---|---|---|
| `/auth/login` | POST | `{email, password, totp_code?}` → JWT access + refresh. Locks out after `LOGIN_LOCKOUT_THRESHOLD` failed attempts within `LOGIN_LOCKOUT_WINDOW_MIN`. |
| `/auth/refresh` | POST | `{refresh}` → rotated pair. Replaying an already-rotated refresh token revokes the whole token family (reuse detection). |
| `/auth/logout` | POST | `{refresh}` → revokes that token's family. |
| `/auth/mfa/enroll` | POST | Authenticated. Returns a TOTP secret + `otpauth://` URI for an authenticator app. |
| `/auth/mfa/verify` | POST | `{code}` → enables MFA on the account; required at login from then on. |
| `/auth/me` | GET | Authenticated. Current user + role names. |

RBAC: permissions are `module.action` strings resolved from `Role`/`Permission` grants, cached
per-(user, org) in Redis. Protect a view with `apps.accounts.permissions.require_permission("students.view")`
in its `permission_classes`.

Multi-tenancy: every tenant-owned model uses `objects = TenantManager()` (app-layer scoping,
works on any DB) plus, on Postgres only, a Row-Level Security policy keyed on the
`app.current_org` session variable (defence-in-depth — see §7 `ARCHITECTURE.md`). Both layers
are exercised in `backend/tests/api/test_tenancy.py`; the RLS-specific tests skip automatically
on SQLite.

## Domain APIs (Milestones 3-10)

All under `/api/v1/`, all authenticated, all gated by `module.action` RBAC permissions and
tenant-scoped per the multi-tenancy rules above. List endpoints are paginated
(`?page=1&page_size=25`); create/update/delete return the standard envelope (§9
`ARCHITECTURE.md`), with a 409 on a uniqueness conflict rather than a raw 500.

| Resource | Endpoints | Notes |
|---|---|---|
| Schools | `/schools`, `/schools/<public_id>` | Tenant hierarchy root. |
| Campuses | `/campuses`, `/campuses/<public_id>` | Filter list by `?school_id=`. |
| Academic years | `/academic-years`, `/academic-years/<public_id>`, `.../activate` | `activate` atomically unsets the school's previous current year. |
| Terms | `/terms`, `/terms/<public_id>`, `.../activate` | Filter list by `?academic_year_id=`; `activate` unsets the year's previous current term. |
| Departments | `/departments`, `/departments/<public_id>` | Filter list by `?school_id=`. |
| Guardians | `/guardians`, `/guardians/<public_id>` | Standalone person record, optionally linked to a login `User`. |
| Students | `/students`, `/students/<public_id>` | Filter list by `?school_id=`; unique `admission_number` per school. |
| Guardian-student links | `/guardian-students`, `/guardian-students/<public_id>` | Filter list by `?student_id=` or `?guardian_id=`; carries `relationship_type` + `is_primary`. |
| Staff | `/staff`, `/staff/<public_id>` | Filter list by `?school_id=` or `?department_id=`; unique `employee_number` per school. |
| Teachers | `/teachers`, `/teachers/<public_id>` | One-to-one specialization of an existing Staff record; filter list by `?staff_id=` or `?school_id=`. |
| Class levels | `/class-levels`, `/class-levels/<public_id>` | Grade under a campus; filter list by `?campus_id=`. |
| Class arms | `/class-arms`, `/class-arms/<public_id>` | Section/stream under a class level; filter list by `?class_level_id=`. |
| Subjects | `/subjects`, `/subjects/<public_id>` | Filter list by `?school_id=`; unique `code` per school. |
| Class subjects | `/class-subjects`, `/class-subjects/<public_id>` | Arm x subject x teacher assignment; filter list by `?class_arm_id=`, `?subject_id=`, or `?teacher_id=`. |
| Enrollments | `/enrollments`, `/enrollments/<public_id>` | Filter list by `?student_id=`, `?class_arm_id=`, or `?academic_year_id=`; one enrollment per student per academic year. |
| Attendance | `/attendance`, `/attendance/<public_id>` | Filter list by `?enrollment_id=` or `?date=`; unique per enrollment per day. Every mark/correction writes an audit entry (see below). |
| Attendance audit | `/attendance-audit` (read-only) | Filter by `?attendance_id=`; append-only at the DB level — a Postgres trigger rejects UPDATE/DELETE on this table entirely, not just at the API layer. |
| Rooms | `/rooms`, `/rooms/<public_id>` | Filter list by `?campus_id=`. |
| Periods | `/periods`, `/periods/<public_id>` | Filter list by `?school_id=`; unique `sequence` and `name` per school. |
| Timetable slots | `/timetable-slots`, `/timetable-slots/<public_id>` | Filter list by `?class_arm_id=`, `?teacher_id=`, or `?room_id=`. `class_arm`/`teacher` are read-only, derived server-side from `class_subject`. Teacher/class-arm/room double-booking on the same day+period are real database constraints (409, not a soft check). |
| Grading schemes | `/grading-schemes`, `/grading-schemes/<public_id>` | Filter list by `?school_id=`; one scheme per school flagged `is_default`. |
| Grade bands | `/grade-bands`, `/grade-bands/<public_id>` | Filter list by `?grading_scheme_id=`; score range that maps to a letter grade + remark. |
| Exams | `/exams`, `/exams/<public_id>` | Filter list by `?term_id=`; `school`/`academic_year` are read-only, derived server-side from `term`. |
| Exam schedules | `/exam-schedules`, `/exam-schedules/<public_id>` | Filter list by `?exam_id=`; one schedule per exam per class subject. |
| Invigilators | `/invigilators`, `/invigilators/<public_id>` (create/delete only) | Filter list by `?exam_schedule_id=`; reassigning is unassign-then-assign, not an in-place edit. |
| Assessments | `/assessments`, `/assessments/<public_id>` | Filter list by `?class_subject_id=` or `?term_id=`; a gradable item (test/quiz/assignment/project/practical/exam) on a class subject, optionally tied to an `Exam` header. |
| Results | `/results`, `/results/<public_id>`, `.../submit`, `.../review`, `.../verify`, `.../publish` | Filter list by `?assessment_id=` or `?student_id=`. `score`/`grade`/`remark` are only editable while `status="entered"`; `grade`/`remark` auto-resolve from the school's default grading scheme. The four transition endpoints enforce strict sequential ordering (409 on a skip or out-of-order call) and each has its own permission code so duties can be separated across roles. |
| Result workflow states | `/result-workflow-states` (read-only) | Filter by `?result_id=`; append-only at the DB level, same as attendance audit — every transition writes an immutable row here. |
| Report cards | `/report-cards`, `/report-cards/<public_id>` (create + read-only) | Filter list by `?student_id=` or `?term_id=`; POST enqueues async PDF generation via Celery (`apps.examinations.tasks.reports.generate_report_card_pdf`) covering the student's published results for the term, storing the file through the provider-agnostic `apps.core.storage` abstraction (S3 in production, local filesystem in dev/CI). `status` moves `pending` -> `generating` -> `ready`/`failed`; no client-facing update — only the task writes `status`/`file_url`/`generated_at`/`error_message`. |
| Fee structures | `/fee-structures`, `/fee-structures/<public_id>` | Filter list by `?term_id=`; `school`/`academic_year` are read-only, derived server-side from `term`. |
| Fee items | `/fee-items`, `/fee-items/<public_id>` | Filter list by `?fee_structure_id=`; `currency_code` is read-only, derived from the organization. |
| Discounts | `/discounts`, `/discounts/<public_id>` | Filter list by `?school_id=`; `discount_type` is `percentage` (with `percentage`) or `fixed_amount` (with `fixed_amount_minor`) — a DB check constraint enforces exactly one is set. |
| Scholarships | `/scholarships`, `/scholarships/<public_id>` | Filter list by `?student_id=` or `?academic_year_id=`; awards an existing `Discount` to a specific student for an academic year. |
| Invoices | `/invoices`, `/invoices/<public_id>`, `.../issue`, `.../cancel` | Filter list by `?student_id=`, `?term_id=`, or `?status=`. `total_minor`/`currency_code`/`status`/`issued_at` are read-only — only editable while `status="draft"`. `issue` posts a balanced accounts_receivable/revenue ledger pair and requires at least one line; `cancel` is only allowed before any payment exists (reverses the same ledger pair if the invoice was issued). |
| Invoice lines | `/invoice-lines`, `/invoice-lines/<public_id>` | Filter list by `?invoice_id=`; mutable only while the parent invoice is `"draft"` (409 otherwise). Each add/edit recomputes `amount_minor` (quantity × unit price − discount) and the parent invoice's `total_minor` together, so the two can never drift. |
| Payments | `/payments`, `/payments/<public_id>` (create + read-only) | Filter list by `?invoice_id=`. `reference` is an idempotency key (unique per organization — a retried post is a clean 409, not a double-post); posting is wrapped in `select_for_update()` on the invoice so concurrent payments can't together overpay it (409 past the outstanding balance). Posts a cash/accounts_receivable ledger pair, moves the invoice to `partially_paid`/`paid`, and enqueues a receipt PDF via Celery after the transaction commits. No client-facing update or delete — a correction is a `Refund`. |
| Refunds | `/refunds`, `/refunds/<public_id>` (create + read-only) | Filter list by `?payment_id=`. Never edits the original `Payment` — posts the exact mirror of its ledger pair (debit/credit swapped) and recomputes the parent invoice's status from the net (paid − refunded) balance; rejects (409) a refund exceeding what's left refundable on the payment. |
| Receipts | `/receipts`, `/receipts/<public_id>` (read-only) | Filter list by `?payment_id=`; one per payment, generated automatically by `payment_service.record_payment` — same async-PDF-via-Celery shape as report cards. |
| Ledger entries | `/ledger-entries` (read-only) | Filter by `?school_id=`, `?ref_type=`, or `?ref_id=`; append-only double-entry trail — every `Invoice`/`Payment`/`Refund` posting writes exactly two balanced rows here, and a Postgres trigger rejects UPDATE/DELETE on this table entirely, same as attendance/result-workflow audit trails. |
| Library books / copies | `/library-books`, `/library-books/<public_id>`; `/library-copies`, `/library-copies/<public_id>` | Filter copies by `?book_id=`; a copy's `status` is read-only, changed only by borrowing/returning/losing it (see loans below). |
| Library members | `/library-members`, `/library-members/<public_id>` | Filter list by `?school_id=`; wraps either a `Student` or a `Staff` member — a DB check constraint enforces `member_type` matches which one is set. |
| Library loans | `/library-loans`, `/library-loans/<public_id>` (create + read-only), `.../return`, `.../mark-lost` | Filter list by `?copy_id=` or `?member_id=`. A copy can only be on one open loan at a time — a real partial-unique DB constraint, not just an app-layer check (409 on a double-borrow). |
| Library fines | `/library-fines`, `/library-fines/<public_id>` (create + read-only), `.../pay`, `.../waive` | Filter list by `?loan_id=`. |
| Inventory items | `/inventory-items`, `/inventory-items/<public_id>` | Filter list by `?school_id=`; `quantity_on_hand` is read-only — it only ever changes via a `StockMovement` (see below). |
| Suppliers | `/suppliers`, `/suppliers/<public_id>` | Filter list by `?school_id=`. |
| Purchase orders | `/purchase-orders`, `/purchase-orders/<public_id>`, `.../mark-ordered`, `.../receive`, `.../cancel` | Filter list by `?item_id=` or `?status=`. One item per order; `receive` is what actually posts a `StockMovement` and moves real stock. |
| Stock movements | `/stock-movements` (create + read-only) | Filter list by `?item_id=`; append-only at the DB level, same as the finance ledger. `quantity` carries its own sign (positive/negative), cross-checked against `movement_type` ("in"/"out"); a movement that would take stock negative is a 409. |
| Vehicles | `/vehicles`, `/vehicles/<public_id>` | Filter list by `?school_id=`. |
| Transport routes / stops | `/transport-routes`, `/transport-routes/<public_id>`; `/route-stops`, `/route-stops/<public_id>` | Filter stops by `?route_id=`. |
| Transport assignments | `/transport-assignments`, `/transport-assignments/<public_id>` (create + read + unassign) | Filter list by `?student_id=` or `?vehicle_id=`. One active assignment per student per academic year is a real partial-unique DB constraint; vehicle seat capacity is enforced at the service layer with `select_for_update()` (409 past capacity). Reassigning a student is unassign-then-assign. |
| Vehicle maintenance | `/vehicle-maintenance`, `/vehicle-maintenance/<public_id>` | Filter list by `?vehicle_id=`. |
| Hostels / buildings / rooms / beds | `/hostels`, `/hostel-buildings`, `/hostel-rooms`, `/hostel-beds` (each with `<public_id>` detail) | Filter buildings by `?hostel_id=`, rooms by `?building_id=`, beds by `?room_id=`. A bed's `status` is read-only, changed only by allocating/vacating it. |
| Hostel allocations | `/hostel-allocations`, `/hostel-allocations/<public_id>` (create + read-only), `.../vacate` | Filter list by `?student_id=` or `?bed_id=`. One active occupant per bed and one active allocation per student per academic year are both real partial-unique DB constraints (409 on a double-booking); reallocating a student is vacate-then-allocate. |
| Hostel incidents | `/hostel-incidents`, `/hostel-incidents/<public_id>`, `.../resolve` | Filter list by `?hostel_id=` or `?status=`. |
| Assignments | `/assignments`, `/assignments/<public_id>` | Filter list by `?class_subject_id=` or `?term_id=`. |
| Assignment submissions | `/assignment-submissions`, `/assignment-submissions/<public_id>` (create + read-only), `/assignment-submissions/upload` (multipart), `.../download`, `.../grade` | Filter list by `?assignment_id=` or `?student_id=`. A submission is text (plain create) or a file (the `/upload` multipart endpoint) — never both. One submission per student per assignment; `status` auto-derives to `late` if submitted past the due date. Grading is a dedicated transition, not a plain PATCH. |
| Announcements | `/announcements`, `/announcements/<public_id>`, `.../publish` | Filter list by `?school_id=`. Publishing fans out a `Notification` to every user in the announcement's audience (students/staff/parents/all) — the notification center's concrete write path. |
| Notifications | `/notifications` (read-only), `.../read`, `/notifications/mark-all-read` | Always scoped to the requesting user's own notifications — no RBAC permission needed, just `IsAuthenticated`. Filter by `?is_read=`. |
| Notification preferences | `/notification-preferences` (GET/PATCH, singular — no `<public_id>`) | Per-user channel toggles (email/SMS/push/in-app); get-or-creates on first access. |
| Messages | `/messages`, `/messages/<public_id>/read` | Direct user-to-user messages; list is scoped to messages the requesting user sent or received. |
| Documents | `/documents` (read-only), `/documents/upload` (multipart), `/documents/<public_id>`, `.../download` | Filter list by `?student_id=` or `?staff_id=`. Upload validates content-type + magic bytes + size limit (§14) and stores under a tenant-scoped key; owned by exactly one of a `Student` or `Staff` (DB check constraint). Download never returns a stored URL — a fresh short-lived presigned one is computed at request time, after the same auth + tenant-scoping check every other endpoint goes through. |

## Local development (without Docker)

Backend (Python 3.12+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # requires Postgres + Redis running locally — see USE_SQLITE below
cd django_app && python manage.py migrate && python manage.py runserver
# in another shell:
cd backend/fastapi_app && uvicorn main:app --reload --port 8001
```

No local Postgres? Add `USE_SQLITE=true` to `backend/.env` — `manage.py migrate`/`runserver`
then need nothing but Python. Row-Level Security (part of Milestone 2) only runs on Postgres,
so `pytest`'s RLS-specific tests will skip, but the app-layer tenant isolation still fully
applies and the rest of the suite is unaffected.

The server-rendered UI (Phase 2+, see `UI_MIGRATION_PLAN.md`) needs its CSS compiled once
before `runserver` will serve real styling — `static/css/app.css` is a build artifact (like
`staticfiles/`), not committed. No Node/npm required — it's the standalone Tailwind CLI binary:

```bash
curl -sSL -o /tmp/tailwindcss "https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.13/tailwindcss-linux-x64"  # or -arm64
chmod +x /tmp/tailwindcss
cd django_app && /tmp/tailwindcss -i theme_src/input.css -o static/css/app.css -c theme_src/tailwind.config.js --minify
```

Re-run that last command after editing `theme_src/input.css` or adding new template markup that
uses new utility classes. `infrastructure/docker/backend.Dockerfile` does this automatically at
image build time, so Docker/Railway deploys never need it done manually.

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
2. In Git Bash:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/Scripts/activate   # Scripts, not bin, on Windows
   pip install -e ".[dev]"
   cp .env.example .env
   ```
   Edit `.env` and add `USE_SQLITE=true` — this is the easiest path on Windows, since
   PostgreSQL's own Windows service setup (superuser password, `pg_hba.conf`, sometimes
   multiple installed versions fighting over port 5432) is its own significant source of
   friction, independent of anything above. Row-Level Security won't run locally with this
   option (see the `USE_SQLITE` note above) — that's fine for day-to-day API work.
3. `cd django_app && python manage.py migrate && python manage.py runserver 8010`
   (port `8000` commonly collides with Splunk's web UI on corporate machines — use another
   port if `8010` is also taken).
4. In a second Git Bash window: `cd backend/fastapi_app && uvicorn main:app --reload --port 8001`
   (activate the same `.venv` first).
5. Test: `http://localhost:8010/api/v1/health` in a browser — note `0.0.0.0` (what `runserver`
   prints) is not itself a browsable address; use `localhost`.

Want real Postgres on Windows instead (needed to actually exercise RLS)? Install PostgreSQL
from postgresql.org (EDB installer) and [Memurai Developer](https://www.memurai.com/get-memurai)
(free, Redis-compatible — Redis has no official Windows build) as services, create the database
(`CREATE DATABASE sms;` via "SQL Shell (psql)"), and either create a matching `sms` role or point
`backend/.env`'s `POSTGRES_USER`/`POSTGRES_PASSWORD` at the `postgres` superuser instead — don't
set `USE_SQLITE`.

## Repository structure

See §20 of `ARCHITECTURE.md` for the full layout and rationale.

```
backend/django_app/    # Django project: config/ (settings, urls, celery), apps/ (one per module)
  apps/core/            #   health/ready probes, shared abstract models, response envelope
  apps/tenancy/         #   Organization model, TenantManager, RLS migration helper, context
  apps/accounts/        #   User, RBAC (Role/Permission), JWT auth, MFA
  apps/schools/         #   School, Campus, AcademicYear, Term, Department
  apps/parents/         #   Guardian, GuardianStudent (student<->guardian link)
  apps/students/        #   Student
  apps/staff/           #   Staff, Teacher (one-to-one specialization of Staff)
  apps/academics/       #   ClassLevel, ClassArm, Subject, ClassSubject, Enrollment
  apps/attendance/      #   Attendance, AttendanceAudit (append-only via DB trigger)
  apps/timetable/       #   Room, Period, TimetableSlot (conflict detection via DB constraints)
  apps/examinations/    #   GradingScheme/GradeBand, Exam/ExamSchedule/Invigilator, Assessment,
                        #   Result (enter->submit->review->verify->publish), ReportCard (PDF via Celery)
  apps/finance/         #   FeeStructure/FeeItem, Discount/Scholarship, Invoice/InvoiceLine,
                        #   Payment, Refund (as reversal), Receipt (PDF via Celery),
                        #   LedgerEntry (double-entry, append-only via DB trigger)
  apps/library/         #   LibraryBook/Copy/Member, LibraryLoan (one open loan per copy via
                        #   partial-unique DB constraint), LibraryFine
  apps/inventory/       #   InventoryItem, Supplier, PurchaseOrder, StockMovement
                        #   (append-only via DB trigger, drives quantity_on_hand)
  apps/transport/       #   Vehicle, TransportRoute/RouteStop, TransportAssignment
                        #   (one active assignment per student/year via partial-unique constraint),
                        #   VehicleMaintenance
  apps/hostel/          #   Hostel/Building/Room/Bed, HostelAllocation (one active occupant per
                        #   bed and per student/year via partial-unique constraints), HostelIncident
  apps/assignments/     #   Assignment, AssignmentSubmission (text or file; own storage fields,
                        #   deliberately not FK'd to apps.documents.Document)
  apps/communication/   #   Announcement (publish -> fans out Notification to its audience),
                        #   Notification, NotificationPreference, Message
  apps/documents/       #   Document (owned by exactly one of Student/Staff; upload validates
                        #   MIME + magic bytes + size, downloads via a fresh presigned URL)
backend/fastapi_app/   # FastAPI edge service: api/, services/, schemas/, dependencies/, core/
backend/shared/        # Money value object + shared enums, used by Django, Celery, and FastAPI
backend/tests/         # pytest: unit, api
infrastructure/        # Dockerfiles, nginx config, scripts
docs/                  # This file, ARCHITECTURE.md, and future module docs
```

## Next milestone

See §18 of `ARCHITECTURE.md` for what comes after Milestone 10.
