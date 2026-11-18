# FOLAD CBT — API Specification

**Status:** Existing route inventory plus proposed contracts  
**Baseline:** `baf8248bf1301fb8d93947444b04ca30dd93b2e6`  
**Central API root:** `/api/v1/` (Django + DRF)

This is not an OpenAPI schema. It distinguishes routes observed in the baseline from proposed routes that do not yet exist.

## 1. API conventions

- Use existing JWT authentication, centralized RBAC and tenant-scoped query patterns.
- Use public UUIDs where the repository convention requires them.
- Derive organization, school and candidate ownership from trusted context/relationships.
- Follow the existing response envelope, pagination and validation conventions.
- Candidate responses must not disclose answer keys, internal scoring snapshots or other candidates' data.
- Use idempotency for retryable mutations, especially offline sync.
- Object-level ownership checks apply to every attempt endpoint, not only list endpoints.

## 2. Existing CBT route families

Verify exact serializers and method details in source before generating clients.

### Topics and question bank

| Route | Observed operations | Purpose |
|---|---|---|
| `/cbt/topics` | GET, POST | List/create topics |
| `/cbt/questions` | GET, POST | List/create questions |
| `/cbt/questions/{id}` | GET, PATCH | Retrieve/update question |
| `/cbt/questions/bulk-import` | POST | Existing CSV bulk import |
| `/cbt/questions/{id}/submit` | POST | Submit for review |
| `/cbt/questions/{id}/approve` | POST | Approve |
| `/cbt/questions/{id}/reject` | POST | Reject |
| `/cbt/questions/{id}/versions` | GET | Version history |
| `/cbt/questions/{id}/blocks` | GET, POST | Rich content |
| `/cbt/questions/{id}/options` | GET, POST | Options |

### Exam administration

| Route | Observed operations | Purpose |
|---|---|---|
| `/cbt/exams` | GET, POST | List/create |
| `/cbt/exams/{id}` | GET, PATCH | Retrieve/update |
| `/cbt/exams/{id}/publish` | POST | Publish |
| `/cbt/exams/{id}/archive` | POST | Archive |
| `/cbt/exams/{id}/generate-questions` | POST | Generate/select questions |
| `/cbt/exams/{id}/analytics` | GET | Analytics |
| `/cbt/exams/{id}/live` | GET | Live status |
| `/cbt/exams/{id}/sections` | GET/POST family | Sections |
| `/cbt/exams/{id}/questions` | GET/POST family | Exam questions |
| `/cbt/exams/{id}/candidates` | GET/POST family | Candidate allocation |
| `/cbt/exams/{id}/attempts` | GET | Attempts |

### Candidate and attempt routes

| Route | Observed operation | Purpose |
|---|---|---|
| `/cbt/my/candidates` | GET | Own available allocations |
| `/cbt/my/candidates/{id}/start-attempt` | POST | Start attempt |
| `/cbt/my/attempts/{id}` | GET | Retrieve own attempt |
| `/cbt/my/attempts/{id}/heartbeat` | POST | Heartbeat |
| `/cbt/my/attempts/{id}/answers` | POST | Save answer |
| `/cbt/my/attempts/{id}/flag` | POST | Flag question |
| `/cbt/my/attempts/{id}/events` | POST | Record event |
| `/cbt/my/attempts/{id}/submit` | POST | Submit |

The source also contains attempt services for expiry, scoring, subjective grading and finalization. Route details must be kept synchronized with source.

### Proctoring event write contract

`POST /cbt/my/attempts/{id}/events` accepts:
- `event_type`: one of the declared CBT event types.
- `client_event_id`: optional client-generated UUID. Clients should generate it once per event and reuse it for every retry.
- `metadata`: JSON object limited to 4 KiB.

A repeated `client_event_id` with the same event type and metadata returns the original event (HTTP 200) and does not increase suspicious-event counts. Reusing the key with a different payload is rejected. Requests without the key remain backward-compatible but are not retry-deduplicated. PostgreSQL enforces append-only event rows with a database trigger; client-reported events remain evidence signals, not proof of misconduct.

## 3. Authorization

The baseline uses centralized `module.action` permissions grouped around CBT questions, exams and attempts (including viewing/grading/invigilation). Generate the exact permission matrix from the source registry before UI role configuration. Do not add a parallel role table or self-escalation path.

## 4. Proposed offline/LAN contracts (not implemented)

Base path proposal: `/api/v1/cbt/offline/`.

| Method | Proposed path | Purpose |
|---|---|---|
| POST | `devices/register` | Enroll device via approved provisioning |
| GET | `devices` | List authorized devices |
| POST | `devices/{device_id}/revoke` | Revoke device |
| POST | `packages` | Queue immutable exam package build |
| GET | `packages/{package_id}` | Retrieve authorized manifest/artifact metadata |
| POST | `sessions/{session_id}/sync` | Submit signed ordered event batch |
| GET | `sessions/{session_id}/sync-status` | Read accepted sequence/sync status |

### Device registration

Use one-time provisioning or administrator approval. Generate device key pair locally; server stores public key/fingerprint. Return device identity, scope, policy and credential expiry. Never issue reusable shared secrets.

### Package manifest

Include schema version, package UUID/version, exam public ID, centre/device scope, issue/not-before/expiry times, content and asset hashes, policy version, signing key ID and signature. Candidate payload excludes answer keys.

### Synchronization envelope (illustrative)

```json
{
  "schema_version": 1,
  "idempotency_key": "unique-client-value",
  "device_id": "device-public-id",
  "package_id": "package-public-id",
  "offline_session_id": "session-public-id",
  "first_sequence": 1,
  "last_sequence": 2,
  "events": [
    {
      "sequence": 1,
      "event_id": "event-public-id",
      "type": "answer_saved",
      "occurred_at": "untrusted-client-time",
      "payload": {"exam_question_id": "public-id", "response": {}},
      "previous_event_hash": "sha256:...",
      "event_hash": "sha256:..."
    }
  ],
  "signature": "device-signature"
}
```

Validate signature, device/package state, tenant/exam/candidate scope, sequence continuity, hashes, schema, size limits, replay/idempotency and state transitions. Server receipt time is authoritative. A rejected batch must not advance accepted sequence.

Response includes batch ID/status, accepted-through sequence, rejected event references, conflict summary, server receipt time and retry classification. Report accepted only after commit.

## 5. Proposed document-import contracts (not implemented)

| Method | Proposed path | Purpose |
|---|---|---|
| POST | `/cbt/imports` | Upload/enqueue CSV, XLSX, DOCX or PDF |
| GET | `/cbt/imports/{job_id}` | Status/progress |
| GET | `/cbt/imports/{job_id}/errors` | Row/page validation errors |
| POST | `/cbt/imports/{job_id}/validate` | Dry-run validation |
| POST | `/cbt/imports/{job_id}/commit` | Commit through existing question service |

Enforce size/type/signature checks, private tenant storage, malware scanning where available, parser isolation/timeouts, limits, idempotency and dry-run before commit.

## 6. Proposed AI contracts (not implemented)

| Method | Proposed path | Purpose |
|---|---|---|
| POST | `/cbt/ai/generation-jobs` | Queue grounded generation |
| GET | `/cbt/ai/generation-jobs/{job_id}` | Job state/validation |
| GET | `/cbt/ai/generation-jobs/{job_id}/drafts` | Retrieve drafts |
| POST | `/cbt/ai/drafts/{draft_id}/approve` | Human approval and promotion |
| POST | `/cbt/ai/drafts/{draft_id}/reject` | Reject with reason |

Every draft retains source/page evidence, model/prompt version, validation and reviewer decision. Approval is permission-gated and audited.

## 7. Error semantics and compatibility

Follow the parent API error envelope. Distinguish authentication (401), permission/scope (403/404), validation (400/422), invalid state/idempotency conflict (409), expired/revoked package (410 where appropriate), oversized payload (413), rate limit (429) and transient server failure (5xx). Retry 5xx only with idempotency.

Do not break existing candidate payloads. Any breaking change requires explicit versioning and compatibility for active exams. Package/event schema versions are independent of HTTP API version.
