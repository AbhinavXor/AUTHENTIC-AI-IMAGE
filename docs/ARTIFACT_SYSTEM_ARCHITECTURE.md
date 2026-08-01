# Authentic AI Artifact System Architecture

## 1. Purpose

The artifact system turns a conversational request into a governed, source-aware, versioned professional document. PDF is treated as an export format, not as the source of truth. The canonical source is the structured document content and its stored specification, source snapshot, validation report, and version history.

## 2. End-to-end flow

```text
Chat request
  -> Artifact Command Router
  -> Artifact Reference Resolver
  -> Artifact Source Resolver
  -> Artifact Specification Planner
  -> AI Composer or deterministic revision/export path
  -> Markdown normalizer
  -> Structured Artifact Document IR
  -> Structural quality gate
  -> Format renderer
  -> Rendered-file quality gate
  -> Binary storage
  -> Logical artifact repository and audit trail
  -> Inline chat artifact card
```

## 3. Phase implementation

### Phase 1 — Command and source intelligence

Frontend modules:

- `artifactCommandRouter.ts`: classifies create, rename, revise, convert, duplicate, delete, restore, and history commands in English and Hinglish.
- `artifactReferenceResolver.ts`: selects the correct artifact by filename, title, format, or recency.
- `artifactSourceResolver.ts`: applies source precedence and asks a clarification when no reliable source exists.

Source precedence:

1. Explicit source named in the request.
2. Uploaded file analysis associated with the request.
3. Explicit previous/above answer reference.
4. Latest meaningful Serenya response.
5. Recent conversation context.
6. Explicit topic in the current prompt.
7. Clarification.

The resolver never substitutes generic Authentic AI company content for a different source topic.

### Phase 2 — Durable artifact domain

The logical repository stores:

- Artifact ID and capability-token hash.
- Display filename and title.
- Current version and all immutable versions.
- Physical binary IDs and checksums.
- Canonical source content.
- Artifact specification.
- Source snapshot.
- Validation report.
- Provider/model metadata.
- Idempotency receipts.
- Audit events.

Mutations use optimistic concurrency through `expected_version`. Replayed requests use idempotency keys. Reuse of the same key for a different payload returns a conflict.

### Phase 3 — Professional composition

The planner derives topic, title, filename, purpose, document type, and a section blueprint. The composer is constrained by source policy and cannot invent citations, statistics, facts, or unrelated subjects.

The structured document IR supports:

- Paragraphs.
- Ordered and unordered lists.
- Tables.
- Charts.
- Quotes.
- Callouts.
- Code.
- Equations.
- Structured process diagrams.
- Page breaks.

PDF, DOCX, and PPTX are rendered from the same canonical document model.

### Phase 4 — Quality and rendering

Pre-render checks include:

- Missing or duplicate headings.
- Empty sections.
- Invalid tables.
- Oversized paragraphs, lists, tables, equations, or diagrams.
- Raw Markdown or HTML leakage.
- Placeholder content.
- Insufficient content.
- Source-topic mismatch.

Post-render checks reopen each file and validate:

- File readability.
- Page or slide count.
- Blank or sparse PDF pages.
- PPTX density risk.
- Raw formatting markers.
- Placeholder content.

An artifact that fails an error-level quality gate is deleted and is not published.

### Phase 5 — Professional UX

The primary chat composer has no large artifact configuration form. Natural language initiates generation. The inline card provides:

- Generation progress and cancellation.
- Open and download.
- Rename.
- Edit/revise.
- Export to another format.
- Duplicate.
- Version history and restore.
- Activity history.
- Delete.

### Phase 6 — Production hardening

Implemented controls:

- Private capability tokens; plaintext tokens are not stored.
- SHA-256 verification when reading stored binaries.
- Path traversal prevention and filename sanitization.
- Maximum request, content, and output size limits.
- Rate limiting for generation and lifecycle operations.
- Idempotency for create and mutation operations.
- Optimistic concurrency.
- Background job cancellation and interrupted-job recovery.
- Periodic expiry cleanup.
- Correlation IDs and no-store response headers.
- CORS allowlists.
- Repository and storage adapter contracts.

## 4. Deployment boundaries

The current implementation uses private local filesystem storage and is appropriate for local development or a controlled single-node deployment. For multi-instance production deployment:

- Replace artifact metadata with PostgreSQL or another transactional database.
- Replace binary files with S3-compatible object storage.
- Replace in-process background tasks with a durable queue.
- Store capability-token signing secrets in a managed secret service.
- Run cleanup as a scheduled worker.
- Export metrics and structured logs to the platform observability stack.

These changes can be implemented behind `artifacts/contracts.py` and the runtime factory without changing the public API or frontend behavior.

## 5. Authority and safety

Artifact creation is a content-generation operation. It does not authorize external side effects. Any future connector or real-world action must pass through the governed OpsPilot execution boundary.
