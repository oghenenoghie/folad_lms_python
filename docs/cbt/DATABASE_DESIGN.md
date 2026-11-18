# FOLAD CBT — Database Design

**Status:** Design proposal; not a migration specification  
**Baseline:** `baf8248bf1301fb8d93947444b04ca30dd93b2e6`

## 1. Design rules

- PostgreSQL is the central system of record; Django ORM owns central schema and migrations.
- Reuse existing identity, tenancy, school, student, enrollment, exam, attempt and result relationships.
- Every tenant-owned CBT record has direct organization scope compatible with TenantManager and PostgreSQL RLS.
- Derive organization/school scope from trusted parent records; never accept client values as authority.
- Use existing public UUID conventions for external identifiers.
- Enforce uniqueness and referential integrity in the database as well as services.
- Keep answer keys private and published snapshots immutable.
- Offline data remains untrusted until centrally validated and accepted.

## 2. Existing CBT model inventory

The audited baseline contains these principal concepts in `apps.cbt`:

| Existing model | Responsibility |
|---|---|
| `Topic` | Curriculum topic taxonomy |
| `Question` | Question bank record and metadata |
| `QuestionBlock` | Structured/rich question content |
| `QuestionOption` | Options and answer-key representation |
| `QuestionVersion` | Question history |
| `CBTMedia` | Question-associated media |
| `CBTExam` | CBT exam configuration |
| `ExamSection` | Exam sections and section rules |
| `ExamQuestion` | Exam-question association and frozen snapshot |
| `ExamCandidate` | Candidate allocation/eligibility |
| `ExamAttempt` | Candidate attempt lifecycle |
| `StudentAnswer` | Response, marks and grading state |
| `ExamAttemptEvent` | Attempt/proctoring event history |

The repository also has existing examinations and academic results domains. Integrate with them; do not duplicate them. Confirm exact fields, constraints and related names against source before implementation.

## 3. Proposed offline/LAN entities

These are logical additions only. Final names, fields, types, indexes and relationships require code-level review.

### CBTDevice
Organization FK; optional validated school/centre FK; public UUID; device type (workstation/centre-server/standalone); public-key fingerprint and public key; display/inventory name; status (pending/active/suspended/revoked); registration/last-seen/revocation timestamps; actor references where policy requires. Unique public UUID and appropriately scoped key fingerprint. Never store private signing keys.

### CBTExamPackage
Organization FK; exam FK; package UUID/version; centre/device audience scope; private encrypted artifact key; versioned manifest; content hash; signature algorithm/key ID/signature; issued/not-before/expiry/revocation timestamps; status and generator version. Unique organization/exam/version/audience. Immutable after ready; revocation is a separate transition. No candidate-readable answer keys.

### CBTOfflineSession
Organization FK; existing ExamCandidate FK; existing ExamAttempt FK when centrally provisioned (otherwise a provisional reference pending acceptance); CBTDevice FK; CBTExamPackage FK; session UUID/status; policy window; last accepted sequence; final event-chain hash and timestamps. Must not create a second canonical attempt for one allocation unless existing exam policy explicitly permits it. Validate all parents resolve to same organization, exam and candidate.

### CBTOfflineEvent
Organization FK; session FK; sequence number; event UUID; type; schema-versioned bounded JSON payload; untrusted client timestamp; previous/event hashes; central receipt timestamp; validation status/reason. Unique session+sequence and session+event UUID. Append-only. Index session/sequence, validation state and receipt time. No keys or private credentials in payloads.

### CBTSyncBatch
Organization FK; session FK; idempotency key; payload hash; first/last sequence; event count; untrusted client submission time; server receipt time; status; validation/conflict summary; accepted time and correlation ID. Unique organization+idempotency key. Conflicting sequence ranges are rejected; retain rejected batches according to examination-record policy.

## 4. Proposed ingestion and AI entities

| Proposed entity | Responsibility | Requirements |
|---|---|---|
| `CBTSourceDocument` | Uploaded source material | Tenant scope, private object key, MIME/size checks, checksum, uploader and retention |
| `CBTContentExtraction` | Extracted text/structure | Parser version, page/section anchors, status and error metadata |
| `CBTImportJob` | CSV/XLSX/DOCX/PDF import | Idempotency, mapping, dry-run, row/page errors and commit status |
| `CBTQuestionGenerationJob` | Asynchronous grounded generation | Source IDs, model/prompt version, requested formats, status and usage |
| `CBTGeneratedQuestionDraft` | Reviewable draft | Payload, evidence anchors, validation, reviewer and approval state |

Generated drafts must be promoted into existing Question/QuestionBlock/QuestionOption records through existing authoring services. No parallel published question table.

## 5. Integrity constraints

1. Every tenant-owned CBT table has organization scope and matching RLS policy.
2. Cross-table organization consistency is checked; FK existence alone is insufficient.
3. ExamQuestion snapshot is frozen at publish.
4. Answer references an ExamQuestion belonging to that attempt's exam.
5. One answer per attempt/exam-question; concurrent upserts are deterministic.
6. Attempt transitions use transaction plus row lock or equivalent compare-and-set.
7. Submission and scoring are idempotent.
8. Offline event sequence is unique and monotonic per session.
9. Device/package revocation is enforced at launch and sync.
10. Retention/deletion honors examination-record obligations and audit requirements.

## 6. Indexing and migration plan

Expected query patterns: tenant+exam+status; tenant+candidate allocation; attempt+exam-question answer; attempt+event time/type; tenant+question topic/status/type; import job status/created time; device status/last seen; session sequence; sync batch status/receipt time. Verify query plans and cardinality before adding indexes.

When approved: re-inspect maintained branch; plan migration dependencies; add only missing entities; add constraints/indexes using deployment-safe methods; verify RLS and TenantManager coverage; add cross-tenant negative tests and migration forward/backward tests. Do not rewrite existing CBT records or snapshots without a separately reviewed data migration.

No schema changes or migrations are included in this documentation PR.
