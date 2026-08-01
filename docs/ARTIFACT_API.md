# Authentic AI Artifact API

Base URL: `/api/v1`

## Authentication model

This local implementation uses capability tokens:

- Artifact operations: `X-Artifact-Token`
- Background job operations: `X-Artifact-Job-Token`

Tokens are returned only at creation. Treat them as secrets. Mutation endpoints also accept `Idempotency-Key`; the body `idempotency_key` remains supported. If both are supplied they must match.

## Create from supplied content

`POST /artifacts/generate`

Creates and validates a PDF, DOCX, or PPTX from supplied Markdown-like content.

## Compose from a natural-language request

`POST /artifacts/compose`

The request may include `source_snapshot`, document type, purpose, audience, tone, length, language, and output preferences.

## Background generation

- `POST /artifacts/jobs`
- `GET /artifacts/jobs/{job_id}`
- `POST /artifacts/jobs/{job_id}/cancel`
- `DELETE /artifacts/jobs/{job_id}`

The status response is one of `queued`, `running`, `succeeded`, `failed`, or `cancelled`.

## Artifact lifecycle

- `GET /artifacts/{artifact_id}` — metadata.
- `PATCH /artifacts/{artifact_id}` — rename display/download filename.
- `POST /artifacts/{artifact_id}/revisions` — create a revised version.
- `POST /artifacts/{artifact_id}/exports` — create a new version in another format.
- `POST /artifacts/{artifact_id}/duplicate` — create a new logical artifact.
- `POST /artifacts/{artifact_id}/restore` — select an earlier immutable version as current.
- `GET /artifacts/{artifact_id}/versions` — version history.
- `GET /artifacts/{artifact_id}/audit` — lifecycle activity.
- `GET /artifacts/{artifact_id}/download?version=N` — current or historical download.
- `DELETE /artifacts/{artifact_id}` — delete all logical metadata and physical versions.

## Concurrency

Mutation requests may include `expected_version`. A stale version returns HTTP 409 instead of overwriting a newer artifact state.

## Idempotency

Use a unique idempotency key per user operation. A retry with the same key and same payload returns the original result. The same key with a different operation or payload returns HTTP 409.

## Error model

- `401`: capability token missing.
- `403`: capability token invalid.
- `404`: artifact or version not found.
- `409`: stale version or idempotency conflict.
- `410`: artifact expired.
- `422`: invalid content, source, or quality validation.
- `429`: rate limit.
- `502/503/504`: provider availability, configuration, rate, or timeout failures.
