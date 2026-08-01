# Artifact Operations Runbook

## Health

`GET /api/v1/health` reports provider status and artifact repository, storage, and job counts.

## Required configuration

Copy `backend/.env.example` to `backend/.env` and configure at least one model provider for prompt-to-artifact composition. Direct Markdown rendering does not require an AI provider.

## Local storage

Default binary and metadata root:

`backend/data/generated_artifacts`

Permissions are restricted when supported by the host operating system. Do not expose this directory through a static web server.

## Retention and cleanup

Artifacts and jobs expire according to the configured retention period. The API process runs a best-effort cleanup loop. A production deployment should run cleanup in a durable scheduled worker.

## Incident handling

### Generation is stuck

1. Check `/api/v1/health`.
2. Inspect the job status and provider configuration.
3. Cancel the job through the cancel endpoint.
4. Restarting the API marks interrupted active jobs as failed.

### Download fails checksum validation

1. Remove the corrupted physical artifact.
2. Preserve the logical audit record for incident review.
3. Regenerate from the stored canonical source/version.
4. Investigate filesystem or object-storage integrity.

### Token exposure

Capability tokens cannot currently be rotated independently. Delete the artifact and duplicate/regenerate it to issue a new token. Production identity-based authorization should replace capability-only access.

### Disk pressure

1. Inspect artifact storage and repository counts from health.
2. Run expiry cleanup.
3. Shorten retention if policy permits.
4. Move to object storage for multi-user production workloads.

## Backup

Back up logical metadata and binaries together. A metadata record without its referenced physical versions is invalid. Never back up `.env` or token-signing secrets into source-control archives.

## Observability

Every response receives `X-Request-ID`. Preserve this value across frontend, API gateway, worker, and provider logs. Do not log source documents, prompts, capability tokens, or generated document bodies.
