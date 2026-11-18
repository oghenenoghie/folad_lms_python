# CBT M4 — Question Content and Import Gap Analysis

**Status:** Baseline audit; implementation not yet started  
**Branch baseline:** `main` at the M4 audit  
**Scope:** Question authoring, media, structured imports and document extraction

## 1. Executive finding

FOLAD CBT already has a working synchronous CSV/XLSX question importer, a question-authoring service, rich-content blocks, media records, question version snapshots and a human approval workflow. M4 must extend these capabilities rather than replace them.

The current importer is a bounded spreadsheet importer, not a durable document-ingestion pipeline. DOCX/PDF extraction, import-job persistence, retry, idempotency, duplicate detection, column mapping, provenance and review of extracted source material are not implemented in the audited code.

## 2. Verified existing capabilities

### 2.1 Question authoring and lifecycle

- Questions are created and updated through the CBT question service.
- Rich content is represented by `QuestionBlock` records.
- Supported block types include paragraph, heading, image, SVG, equation, chemical equation, table, graph, audio, video, document, diagram, callout and divider.
- Choice options are stored separately from content blocks.
- Published-question edits snapshot the previous question state into `QuestionVersion`.
- Questions have a draft/submitted/review/approved/published/archived lifecycle.
- Approval and publication are separate transitions; imports must not bypass them.

### 2.2 Media

- CBT media metadata and upload endpoints exist.
- Upload validation delegates to the shared core storage validator.
- The current media service documents image/document support; audio/video/SVG upload support is not yet enabled through the shared allow-list.
- Rich blocks reference media by identifier; importer must not accept arbitrary external storage paths.

### 2.3 Existing spreadsheet importer

Source locations:
- `backend/django_app/apps/cbt/views.py` — `QuestionBulkImportView`
- `backend/django_app/apps/cbt/services/question_service.py` — `bulk_import_questions`
- `backend/django_app/apps/cbt/urls.py` — `cbt/questions/bulk-import`
- `backend/tests/api/test_cbt_bulk_import.py`

Verified behavior:
- CSV uses UTF-8/UTF-8-BOM decoding.
- XLSX is read using openpyxl in read-only/data-only mode.
- Upload size is limited to 10 MiB.
- XLSX archive entries and expanded size are bounded.
- A maximum of 5,000 data rows is enforced.
- Column names are normalized and duplicate/empty headers rejected.
- Required headers are `text` and `correct`.
- Supported question types are single-choice, multiple-choice and true/false.
- Row-level validation errors are returned.
- Dry-run produces a preview without creating question records.
- Successful imports create questions through the existing question service.

Current limitations:
- Import is synchronous within the HTTP request.
- No persistent job or status/progress resource exists.
- No explicit idempotency key or content fingerprint prevents duplicate submission.
- No import-level duplicate detection exists.
- No configurable column mapping exists.
- No DOCX/PDF parser or source page/section provenance exists.
- Dry-run and commit are a single endpoint mode rather than a persisted reviewable job lifecycle.
- The existing service permits partial success: valid rows can be created while other rows fail. A future commit workflow must make this behavior explicit and configurable or require an all-valid commit policy.
- The current flat importer is not a complete representation for rich blocks, equations, diagrams or media.

## 3. M4 scope and boundaries

### In scope

1. Harden and test the existing CSV/XLSX path.
2. Introduce a persisted import-job lifecycle and durable error records.
3. Add mapping, validation, preview and explicit commit.
4. Add DOCX/PDF extraction into a reviewable intermediate representation.
5. Preserve source filename, file hash, page/section and source text references for extracted questions.
6. Add idempotency and duplicate detection.
7. Keep imported questions in draft/unpublished state until the existing approval process is completed.
8. Validate tenant ownership, permissions, file size/type/signature and parser resource limits.
9. Add accessibility and validation rules for rich-content blocks and media references.

### Out of scope for the first M4 slice

- AI-generated questions or automatic answer-key inference.
- Automatic publication or approval.
- Arbitrary remote URL imports.
- Browser-side parsing of untrusted documents.
- Offline/LAN package ingestion.
- Expanding media upload types without a separate security review.

## 4. Proposed import lifecycle

1. **Upload:** authenticate, authorize, validate size and file signature, calculate SHA-256, persist to private tenant-scoped storage.
2. **Create job:** record owner, organization, file metadata, parser version, idempotency key and initial state.
3. **Extract:** parse in a bounded worker process with memory/time/row/page limits.
4. **Map:** apply a saved or request-supplied mapping into a canonical question schema.
5. **Validate:** validate every candidate question and report row/page/section-specific errors.
6. **Preview:** return counts, warnings, source provenance and a bounded sample; no question records are written.
7. **Commit:** require an explicit authorized action; revalidate the job and commit through the existing question service in a transaction with deterministic duplicate handling.
8. **Review:** create draft questions only; existing question submission/approval/publication permissions remain authoritative.
9. **Retry:** retry transient extraction failures safely; never duplicate already committed questions.

Suggested job states: `uploaded`, `queued`, `extracting`, `needs_mapping`, `validating`, `ready_to_commit`, `committing`, `completed`, `completed_with_errors`, `failed`, `cancelled`.

## 5. Canonical intermediate question record

The parser should emit an intermediate record rather than create database objects directly. At minimum:

- question type and difficulty
- stem as structured blocks, not trusted raw HTML
- options and answer-key references where explicitly present in source
- marks and negative marks
- subject/class/topic mapping references
- source file SHA-256 and original filename
- source page number or DOCX section/paragraph locator
- extraction warnings and parser version
- stable per-source item fingerprint

The importer must never invent a correct answer. Missing or ambiguous answer keys become validation errors or explicit review warnings.

## 6. Security and resilience requirements

- Enforce request and reverse-proxy upload limits; do not rely only on application-level checks.
- Check extension, declared MIME type, file signature and parser-recognized structure.
- Reject encrypted, malformed, unsupported or oversized documents with safe errors.
- For ZIP-based formats, cap member count, total expanded bytes, per-member size and compression ratio; reject path traversal and unexpected members.
- Disable external entity/network resolution in XML/document parsers.
- Run DOCX/PDF extraction in a worker with hard time, memory and page limits; use no shell execution and no network access.
- Store source files privately and scope every job, file and resulting question to the authenticated organization.
- Do not expose storage keys or local filesystem paths in API responses.
- Use a unique constraint for organization + idempotency key and a stable source-item fingerprint for duplicate detection.
- Make commit atomic or explicitly report a deterministic partial-commit outcome; retries must not duplicate records.
- Keep answer keys hidden from candidate-facing serializers and do not auto-publish imported content.
- Audit upload, validation, commit, cancellation and reviewer actions.

## 7. Proposed API evolution

The existing `POST /cbt/questions/bulk-import` remains supported for backward compatibility while the job API is introduced.

Proposed routes:
- `POST /cbt/imports` — upload/create job
- `GET /cbt/imports/{job_id}` — status and counts
- `GET /cbt/imports/{job_id}/preview` — bounded preview and provenance
- `GET /cbt/imports/{job_id}/errors` — validation/extraction errors
- `PATCH /cbt/imports/{job_id}/mapping` — set/confirm column mapping
- `POST /cbt/imports/{job_id}/validate` — run or rerun validation
- `POST /cbt/imports/{job_id}/commit` — explicit commit
- `POST /cbt/imports/{job_id}/cancel` — cancel if not committed

Exact request/response schemas and permission codes must be designed before implementation. Job endpoints must use the existing authentication, tenant managers/RLS and centralized permission registry.

## 8. Implementation sequence

### M4-A — Harden existing CSV/XLSX import
- Add regression tests for malformed CSV/XLSX, formula cells, oversized archives, excessive rows, duplicate headers, missing headers and tenant mismatch.
- Verify subject and class-level ownership against the authenticated organization.
- Ensure XLSX workbooks close on every exit path.
- Make transaction/partial-success semantics explicit.
- Preserve the existing endpoint contract.

### M4-B — Import job domain and API
- Design model/migration and unique idempotency constraints.
- Add job/error/provenance serializers and permission entries.
- Add upload, status, preview, validation, commit and cancellation routes.
- Add durable worker dispatch and retry policy.

### M4-C — DOCX/PDF extraction
- Select maintained parsers and isolate execution.
- Extract text and structural provenance only; do not publish questions.
- Add representative, malformed and adversarial fixtures.
- Document supported PDF/DOCX features and limitations.

### M4-D — Rich content, accessibility and release gate
- Map supported source structures into validated blocks.
- Add media-reference validation, accessible alt text/captions and equation/diagram fallback requirements.
- Run tenant/RBAC, idempotency, duplicate, retry, parser-limit and candidate answer-key secrecy tests.

## 9. Acceptance criteria

- Existing CSV/XLSX API tests remain green.
- Repeating an upload with the same idempotency key returns the same job and does not create duplicates.
- Preview and validation never create question records.
- Commit is explicit, permission-gated, tenant-scoped and retry-safe.
- DOCX/PDF extraction records page/section provenance and never invents answers.
- Malformed, encrypted, oversized and hostile files fail safely within resource limits.
- Imported questions remain drafts and pass through existing review/approval.
- Cross-tenant access to jobs, source files, errors and imported questions is denied.
- Full PostgreSQL CI, migration checks, lint and security tests pass.

## 10. Decision log

- Preserve the current synchronous CSV/XLSX endpoint during migration to the job API.
- Use the existing question service as the only question creation path.
- Keep extraction separate from question creation and publication.
- Require explicit human review for extracted content and all uncertain answer keys.
- Do not add a new question schema until the canonical intermediate record and source provenance requirements are reviewed.
