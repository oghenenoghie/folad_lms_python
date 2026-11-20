# FOLAD CBT — Security and Test Plan

**Status:** Proposed verification plan and audit findings  
**Baseline:** `baf8248bf1301fb8d93947444b04ca30dd93b2e6`  
**Scope:** No application or test files are modified by this document.

## 1. Security objectives

- Strict organization/school isolation.
- Candidate access only to own allocations, attempts and answers.
- No answer-key disclosure or mutation of published snapshots.
- Server-enforced timing and legal state transitions.
- Durable, idempotent answer writes and submission.
- Complete auditability for high-stakes operations.
- Offline clients/devices/timestamps/telemetry treated as untrusted.
- Safe document parsing and controlled AI publication.

## 2. Findings to reproduce and remediate

These are source-inspection observations. Reproduce them on the selected maintained branch before treating them as confirmed defects.

| ID | Observation | Risk | Required action |
|---|---|---|---|
| CBT-SEC-01 | Inspected `submit_attempt()` checks in-progress status but does not itself compare current time with `expires_at`; expiry is handled in other lifecycle paths | Late submission/inconsistent expiry | Enforce expiry in domain transition under transaction/lock; define deadline boundary behavior |
| CBT-SCORE-01 | The original scorer ignored the exam switch and per-question penalty | Incorrect result | Resolved in M3-B: apply frozen per-question penalties only when the exam enables negative marking; see policy below |
| CBT-CONC-01 | Attempt creation, answer upsert, submission and scoring need race/idempotency review | Lost/duplicate work or invalid transitions | Add transaction/row-lock or compare-and-set and concurrent tests |
| CBT-SEC-02 | Proctoring events are client-reported signals | False positive/tampering | Treat as evidence metadata; require human review, not automatic punishment |
| CBT-SEC-03 | Proctoring event retries and direct database mutation | Duplicate evidence or evidence tampering | Require stable client event UUIDs for retry deduplication, bound metadata size, enforce PostgreSQL append-only trigger and test mutation rejection |
| CBT-OPS-01 | Historical test count came from merged PR report, not a new audit run | False confidence | Run current suite/CI on selected branch and record actual results |

Do not silently change negative-marking semantics. Product policy must define wrong-answer penalty, multiple-select partial credit, unanswered behavior, score floor, decimal precision and whether penalty applies per item or section.


## 2.1 Approved M3-B scoring policy

- Negative marking is controlled by the exam-level `negative_marking` switch. When disabled, incorrect objective answers award zero regardless of a question's configured penalty.
- When enabled, an incorrect, non-blank auto-gradable response receives the negative penalty frozen in that published question snapshot's `negative_marks` field.
- The configured penalty must be finite, non-negative and no greater than that question's marks.
- Correct objective responses receive the question's full effective marks.
- Unanswered/blank responses receive zero and are not penalized. This includes empty answer rows created when a candidate flags a question without answering it.
- Multiple-choice and other currently implemented objective types retain exact-match scoring. Partial credit is not introduced by M3-B.
- Subjective/manual marking remains bounded from zero to the question's effective marks; negative subjective marks are not introduced.
- The aggregate examination score and percentage are floored at zero. They cannot become negative.
- Penalties are applied per question using the published snapshot, so later edits to the question bank cannot change an already-published exam's scoring.
- Decimal arithmetic is retained; no floating-point scoring is introduced.

## 2.2 M3-F candidate request validation

Candidate answer and flag endpoints validate request payloads before resolving question resources or invoking domain services:

- `exam_question` must be a valid public UUID and must belong to the candidate's exam.
- `response` must be a JSON object; arrays, strings, numbers and null are rejected.
- `time_spent_seconds` must be an integer greater than or equal to zero. Malformed values are returned as client validation errors rather than leaking conversion exceptions as server errors.
- `flagged` uses serializer boolean parsing, so an explicit false value is not accidentally converted to true by Python truthiness.
- Staff manual grading parses `marks_awarded` through a bounded decimal serializer; missing values, booleans, non-numeric values, NaN/infinity, negative values and excess decimal precision are rejected before the grading service runs.
- API regression coverage includes malformed/negative time, non-object responses, false flag values and invalid manual-grading numbers.

These checks validate the transport contract; the attempt service remains responsible for domain invariants, deadline enforcement and locking.

## 3. Authentication and authorization tests

- Protected routes reject unauthenticated requests.
- Expired, revoked and malformed tokens are rejected.
- Existing refresh rotation/reuse detection remains intact.
- Every admin action checks the correct centralized permission.
- Candidate routes enforce object ownership for retrieve, answer, flag, heartbeat, events and submit.
- Candidate cannot alter organization, school, candidate, exam or attempt identity through payload.
- Custom roles cannot grant platform-only privileges.
- Permission cache invalidation follows role/grant changes.
- Device registration, package issue/revoke and manual grading require explicit permission.

## 4. Tenant and database tests

- TenantManager scopes rows and fails closed without tenant context.
- PostgreSQL RLS blocks cross-org reads/writes even if app filters are omitted.
- Every CBT model has correct organization ownership and RLS policy.
- Cross-tenant FK combinations are rejected.
- Public UUID guessing does not expose other-tenant resources.
- Celery tasks establish and clear tenant context correctly.
- Connection reuse cannot leak tenant GUC/context.
- SQLite skips are not mistaken for PostgreSQL RLS verification; run dedicated PostgreSQL integration tests.

## 5. Exam lifecycle and timing tests

- Draft/published/archived transitions follow state machine.
- Publish freezes exact question and answer-key snapshot.
- Bank edits cannot mutate published snapshot.
- Candidate starts only if allocated, eligible, within permitted window and attempt limit.
- Duplicate start is idempotent or returns existing active attempt according to policy.
- Server time determines start/expiry.
- Test submit just before, exactly at and after deadline.
- Heartbeat after expiry cannot extend deadline.
- Delayed heartbeat cannot authorize late answer writes.
- Concurrent submit/auto-expiry produce one legal terminal state.
- Repeated submit cannot double-grade or duplicate result integration.

## 6. Answer and scoring tests

- Answer belongs to an exam question in the attempt's exam.
- Candidate cannot set marks, correctness, key or grader identity.
- Repeated identical answer save is safe.
- Concurrent answer saves have deterministic ordering/version semantics.
- Retry after timeout following server commit does not duplicate.
- Objective question types test correct, incorrect, malformed and boundary responses.
- Subjective answers remain pending until authorized grading.
- Multiple-select partial-credit policy is explicit/tested.
- Negative marking is explicit/tested.
- Decimal precision and aggregation are deterministic.
- Regrade/manual override is audited.
- Final score uses immutable snapshot and accepted answers only.

## 7. Import and AI security tests

- Allowlist MIME/type/extension and verify file signature.
- Enforce size, page, row, decompression and time limits.
- Reject malformed, encrypted, macro-enabled or unsupported files per policy.
- Parse in isolated workers with restricted filesystem/network.
- Malware scan where available; store privately.
- Prevent path traversal, archive bombs, formula injection and unsafe HTML/SVG.
- Preserve source-page/section references.
- Treat prompt injection in uploaded material as untrusted content, not instructions.
- Generated drafts cannot publish without authorized human review.
- External model transfer requires approved data-processing policy.

## 8. Offline/LAN security tests

- Invalid package signature/hash blocks launch.
- Expired/revoked package is rejected.
- Revoked device cannot launch/sync.
- Private key never leaves device.
- Event tampering, missing/duplicate sequence and replay are detected.
- Same idempotency key with different payload is rejected.
- Identical batch retry returns original outcome.
- Cross-tenant/candidate/exam event is rejected.
- Client timestamp manipulation cannot override server policy.
- Acknowledged answer survives workstation and centre restart.
- Disk/database failure does not falsely acknowledge writes.
- Conflicting sessions are quarantined, not last-write-wins merged.
- Local encryption, key rotation and secure deletion are tested.
- Operator recovery and package revocation are exercised.

## 9. Performance and resilience

Test at 500, 1,000 and 2,000 concurrent candidates with agreed SLOs. Include login/start bursts, heartbeat/answer writes, navigation/media, synchronized submission, retries after packet loss, analytics during live exam, worker/Redis restart, database failover where supported, WAN outage/reconnect and sync backlog drain.

Measure p50/p95/p99 latency, error rate, throughput, DB CPU/IO/locks/connections, Redis latency/memory, worker queue depth, storage bandwidth and recovery/data-loss outcomes. Run soak tests to expose leaks and queue growth.

## 10. CI quality gates

1. Formatting/lint and static type checks per repository conventions.
2. Django checks and migration consistency.
3. Unit tests for scoring, transitions and serializers.
4. API tests for auth, RBAC, tenant scope and candidate ownership.
5. PostgreSQL integration suite including RLS; `.github/workflows/backend-ci.yml` provisions PostgreSQL 16 and Redis 7 for backend pull requests and pushes to `main`.
6. CI installs the committed `backend/uv.lock`, runs Django system checks, checks migration drift, then executes the complete backend pytest suite. PostgreSQL is used so RLS policies and PostgreSQL-only triggers are exercised; SQLite-only success is not an acceptable substitute.
7. Concurrency/idempotency tests.
8. Frontend typecheck/lint/unit/accessibility tests for UI changes.
9. Dependency and secret scanning.
10. Desktop/centre package verification when those components exist.
11. Publish test results and artifacts on pull requests.

## 11. Audit and incident response

Record actor, resource public IDs, permitted before/after state, reason, correlation ID, timestamp and source/device context. Audit records should be append-only and access-controlled. Never log passwords, JWTs, private keys, raw answer keys or full sensitive candidate payloads.

Runbooks cover suspected exam compromise, device theft, signing-key compromise, leaked package, cross-tenant exposure, lost centre server, sync conflict, candidate dispute and data restore. Include revocation, evidence preservation, notification and recovery.

## 12. Acceptance gate

High-stakes release requires resolved timing/scoring/concurrency findings; PostgreSQL tenant and candidate ownership tests; verified answer-key secrecy; durable/idempotent submission and sync; offline tamper/replay/recovery tests for offline release; demonstrated capacity; no unresolved critical/high security findings; and successful backup restore/operator drills.

