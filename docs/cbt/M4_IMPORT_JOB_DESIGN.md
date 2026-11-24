# CBT M4-B — Import Job Domain and API Design

**Status:** Design proposal for review; no runtime behavior or schema changes.
**Scope:** Durable, tenant-scoped import jobs for CSV/XLSX first, with DOCX/PDF extraction added in M4-C.

## 1. Goals and non-goals

M4-B converts the existing request-scoped import operation into a durable workflow without replacing the question service or breaking `POST /cbt/questions/bulk-import`.

Goals:
- Persist upload metadata, job state, validation results and source provenance.
- Make preview read-only and commit explicit.
- Make upload retries idempotent and question creation retry-safe.
- Keep every job, item, error and source object tenant-scoped.
- Keep imported questions in `draft`; existing review/approval remains mandatory.

Non-goals:
- Choosing or introducing a background-worker framework before the repository's deployment/runtime topology is verified.
- Parsing PDF/DOCX in this slice.
- AI question generation, answer inference, automatic approval or publication.
- Arbitrary remote URL ingestion.

## 2. Domain model proposal

All models extend `BaseModel`, carry a literal `organization` foreign key, and use `TenantManager` plus `all_tenants`, matching existing CBT and domain-model conventions. RLS policies must be added through the repository's established migration mechanism.

### 2.1 `CBTImportJob`

| Field | Type / rule | Purpose |
|---|---|---|
| organization | FK, required | Tenant boundary |
| created_by | FK user, PROTECT | Initiating actor |
| source_name | CharField(255) | Sanitized original filename; never a path |
| source_format | choice: csv, xlsx, docx, pdf | Validated format |
| storage_key | CharField(500) | Private storage key; never expose in API |
| source_sha256 | CharField(64) | Integrity and content identity |
| source_size_bytes | PositiveBigIntegerField | Enforced upload size |
| idempotency_key | CharField(128) | Client retry token |
| parser_version | CharField(40) | Reproducible extraction |
| status | choice | Durable workflow state |
| subject | FK Subject | Server-validated curriculum target |
| class_level | FK ClassLevel | Server-validated curriculum target |
| mapping | JSONField | Confirmed source-to-question mapping |
| summary | JSONField | Counts and safe aggregate diagnostics |
| started_at / completed_at | nullable timestamps | Operational lifecycle |
| failure_code | nullable short string | Stable machine-readable failure |
| failure_message | nullable text | Safe, non-sensitive message |

Required database constraint: unique `(organization, idempotency_key)`. A repeated request with the same key and same source hash returns the existing job. Reuse of the key with a different hash returns HTTP 409. Do not use a global unique key because tenants must not collide.

Indexes: `(organization, status, created_at)` and `(organization, source_sha256)`. A source hash is an audit/deduplication signal, not a reason to silently reuse a previous job: identical content submitted under a different idempotency key may be a deliberate new import and should produce a duplicate warning/preview.

### 2.2 `CBTImportItem`

One candidate question emitted by a parser or spreadsheet row.

| Field | Type / rule | Purpose |
|---|---|---|
| organization | FK, required | Direct RLS key |
| job | FK, CASCADE | Parent import |
| sequence | PositiveIntegerField | Stable item ordering |
| source_locator | JSONField | CSV row, worksheet/cell range, PDF page or DOCX paragraph |
| source_fingerprint | CharField(64) | Stable per-source candidate identity |
| payload | JSONField | Canonical intermediate question representation |
| validation_status | choice: pending, valid, invalid, warning | Item review state |
| committed_question | nullable FK Question, PROTECT | Idempotent commit association |

Constraint: unique `(job, sequence)`; unique `(job, source_fingerprint)`. Add an index on `(organization, job, validation_status)`.

The canonical payload must represent structured blocks and options, not arbitrary HTML. It may include an answer key only when the source explicitly contains one. The parser must never infer or invent correct answers.

### 2.3 `CBTImportIssue`

Durable row/item/job diagnostics:
- organization and job, with optional item FK
- severity: error, warning, info
- stable code, safe message
- source locator (row/page/section)
- created timestamp

Do not persist stack traces, raw secrets, full answer keys or storage credentials in user-visible diagnostics. A deterministic unique key on job + item (nullable) + code + locator should prevent duplicate issues when validation is reruns; if nullable uniqueness is awkward on the supported database, enforce it in the service transaction and document the database-specific constraint.

## 3. State machine

Allowed transitions:

- uploaded -> queued | cancelled
- queued -> extracting | failed | cancelled
- extracting -> needs_mapping | validating | failed | cancelled
- needs_mapping -> validating | cancelled
- validating -> ready_to_commit | completed_with_errors | failed | cancelled
- ready_to_commit -> committing | cancelled
- committing -> completed | completed_with_errors | failed
- completed, completed_with_errors, failed, cancelled -> terminal

A retry is an explicit operation with an audit record and a transition back to queued only for retryable failures. Never reset a job that has committed questions. A commit retry resumes from item associations and skips items already linked to a committed question.

Use a centralized transition service with row locking; do not allow clients to PATCH arbitrary status values.

## 4. Canonical intermediate item schema

Minimum shape:
- `question_type`, `difficulty`, `marks`, `negative_marks`
- `blocks[]`: validated block type + structured content
- `options[]`: label, structured content, explicit correctness flag when supplied
- `topic_reference`: source value to map, not a trusted database ID
- `source`: source hash, filename, format, locator and parser version
- `warnings[]`: machine-readable warning codes

Validation resolves subject/class/topic within the authenticated organization and same school. Do not accept organization IDs or arbitrary storage keys from client payloads.

## 5. API proposal

All routes are under `/api/v1/cbt/imports` and use existing authentication, tenant middleware, permission registry and response envelopes.

| Method and route | Permission | Behavior |
|---|---|---|
| POST `/imports` | `cbt_imports.create` | Upload and create/retrieve idempotent job |
| GET `/imports` | `cbt_imports.read` | Paginated tenant-scoped jobs |
| GET `/imports/{public_id}` | `cbt_imports.read` | Status and aggregate counts |
| GET `/imports/{public_id}/items` | `cbt_imports.read` | Paginated safe preview |
| GET `/imports/{public_id}/issues` | `cbt_imports.read` | Paginated validation/extraction issues |
| PATCH `/imports/{public_id}/mapping` | `cbt_imports.update` | Set mapping while job is needs_mapping |
| POST `/imports/{public_id}/validate` | `cbt_imports.validate` | Validate/revalidate without creating questions |
| POST `/imports/{public_id}/commit` | `cbt_imports.commit` | Explicitly create draft questions |
| POST `/imports/{public_id}/cancel` | `cbt_imports.cancel` | Cancel before commit starts |

Commit policy for v1: reject commit if any item is invalid or unresolved; require the caller to correct mapping/data and validate again. A later explicit partial-commit mode can be introduced only with a clear UI and audit semantics. Commit must be transactional per job where practical; if a job is too large for one transaction, use deterministic per-item transactions and report exact committed/skipped/failed counts.

The existing `POST /cbt/questions/bulk-import` remains backward-compatible and is not silently redirected until the job API is proven and a deprecation plan is approved.

## 6. Idempotency and duplicate handling

- Require an `Idempotency-Key` header on job creation.
- Scope uniqueness to organization.
- Compare request source hash and normalized target references on key reuse.
- Compute per-item fingerprints from canonicalized source content + source locator + parser version.
- During commit, lock the job and each eligible item; create via the existing question service; save `committed_question` in the same transaction.
- On retry, never create a second question for an item already associated with one.
- Report likely duplicate question content as a warning for human review; do not auto-merge or discard content.

## 7. Security, storage and operations

- Store source documents in private tenant-scoped storage using the existing storage abstraction; database rows store opaque keys only.
- Verify file signature, extension, MIME, size, archive member count, expanded size and compression ratio before parsing.
- Keep source downloads behind an authorized API that generates short-lived access, or stream through the API; never return a permanent public URL.
- Ensure job/item/issue queries are scoped by tenant manager and RLS.
- Revalidate that subject and class level belong to the same organization and school at upload and commit.
- Audit upload, mapping changes, validation, commit, retry and cancellation.
- Apply per-tenant upload quotas, job retention and bounded preview pagination.
- Worker execution must have time, memory and concurrency limits. No shell execution or outbound network access for document parsers.

### Worker decision gate

The inspected CBT settings and app files establish PostgreSQL/RLS and Redis use in the project, but do not by themselves establish a configured durable task queue. Before adding worker dependencies or deployment services, inspect all runtime manifests, Docker/Procfile/Railway/Vercel configuration and existing scheduled-task patterns. Choose a worker only after confirming how the Django API is deployed and how a long-running worker can be operated. Do not pretend an in-process background thread is durable.

## 8. Migration and implementation order

1. Add models and migration, including organization columns, indexes, uniqueness and RLS policies.
2. Add centralized permissions and tests for permission seeding/role grants.
3. Add serializers and read-only list/detail/items/issues endpoints.
4. Add upload validation, private storage and idempotent job creation.
5. Add transition service and dispatch adapter, then integrate a verified worker.
6. Add parser adapters that produce canonical items; CSV/XLSX first.
7. Add validation and preview; prove preview writes no questions.
8. Add explicit commit with per-item idempotency through `question_service`.
9. Add PostgreSQL tests for tenant isolation, duplicate keys, retries, cancellation and commit races.

## 9. Release acceptance criteria

- Migration applies cleanly on PostgreSQL and migration drift check is clean.
- RLS denies cross-tenant access to jobs, items, issues and source objects.
- Same idempotency key + same request returns one job; same key + different content returns 409.
- Preview/validation create zero Question records.
- Commit is explicit, permission-gated, school-scoped and retry-safe.
- A repeated commit cannot duplicate questions.
- Imported questions remain draft.
- Worker failure/restart does not lose jobs or duplicate committed questions.
- API pagination and quotas prevent unbounded result/file exposure.
- Existing bulk-import endpoint tests remain green.

## 10. Decisions still required before implementation

- Confirm supported storage backend and retention policy for original source files.
- Confirm worker runtime and deployment topology.
- Confirm whether one job can target exactly one subject/class level (recommended for v1).
- Confirm v1 commit is all-valid-only (recommended) or allows partial commit.
- Confirm maximum source retention and maximum active jobs per tenant.
