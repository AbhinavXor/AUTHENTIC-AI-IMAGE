import type {
  ArtifactAuditResponse,
  ArtifactDeleteResponse,
  ArtifactDuplicateRequest,
  ArtifactExportRequest,
  ArtifactGenerateRequest,
  ArtifactRecord,
  ArtifactRenameRequest,
  ArtifactRestoreRequest,
  ArtifactRevisionRequest,
  ArtifactSourceResponse,
  ArtifactVersionListResponse,
} from '../types/artifacts'

interface ApiErrorPayload {
  detail?:
    | string
    | Array<{
        msg?: string
      }>
}

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '')

const artifactTokenHeader =
  'X-Artifact-Token'

const idempotencyKeyHeader =
  'Idempotency-Key'

export class ArtifactApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)
    this.name = 'ArtifactApiError'
    this.status = status
  }
}

async function readApiError(
  response: Response,
): Promise<string> {
  try {
    const payload =
      (await response.json()) as ApiErrorPayload

    if (
      typeof payload.detail === 'string' &&
      payload.detail
    ) {
      return payload.detail
    }

    if (
      Array.isArray(payload.detail) &&
      payload.detail.length > 0
    ) {
      const firstMessage =
        payload.detail[0]?.msg

      if (
        typeof firstMessage === 'string' &&
        firstMessage
      ) {
        return firstMessage
      }
    }
  } catch {
    // Use fallback below.
  }

  return 'The artifact request could not be completed.'
}

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof DOMException &&
    error.name === 'AbortError'
  )
}

function resolveDownloadUrl(
  downloadUrl: string,
): string {
  if (
    downloadUrl.startsWith('http://') ||
    downloadUrl.startsWith('https://')
  ) {
    return downloadUrl
  }

  const base = new URL(
    apiBaseUrl,
    window.location.origin,
  )

  return new URL(
    downloadUrl,
    `${base.origin}/`,
  ).toString()
}

function artifactHeaders(
  artifact: Pick<
    ArtifactRecord,
    'access_token'
  >,
  includeJson = false,
  idempotencyKey?: string | null,
): HeadersInit {
  return {
    ...(includeJson
      ? {
          'Content-Type':
            'application/json',
        }
      : {}),
    [artifactTokenHeader]:
      artifact.access_token,
    ...(idempotencyKey
      ? {
          [idempotencyKeyHeader]:
            idempotencyKey,
        }
      : {}),
  }
}

async function requestJson<T>(
  url: string,
  init: RequestInit,
  connectionMessage: string,
): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, init)
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ArtifactApiError(
      connectionMessage,
      0,
    )
  }

  if (!response.ok) {
    throw new ArtifactApiError(
      await readApiError(response),
      response.status,
    )
  }

  return (await response.json()) as T
}

export async function generateArtifact(
  request: ArtifactGenerateRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    `${apiBaseUrl}/artifacts/generate`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          'application/json',
        ...(request.idempotency_key
          ? {
              [idempotencyKeyHeader]:
                request.idempotency_key,
            }
          : {}),
      },
      body: JSON.stringify(request),
      signal,
    },
    (
      'Authentic AI could not connect to '
      + 'the artifact-generation service.'
    ),
  )
}

export async function getArtifactMetadata(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
    ),
    {
      method: 'GET',
      headers: artifactHeaders(artifact),
      cache: 'no-store',
      signal,
    },
    (
      'Authentic AI could not load '
      + 'the artifact metadata.'
    ),
  )
}

export async function getArtifactSource(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactSourceResponse> {
  return requestJson<ArtifactSourceResponse>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/source'
    ),
    {
      method: 'GET',
      headers: artifactHeaders(artifact),
      cache: 'no-store',
      signal,
    },
    (
      'Authentic AI could not recover '
      + 'the original artifact source.'
    ),
  )
}


export async function renameArtifact(
  artifact: ArtifactRecord,
  request: ArtifactRenameRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
    ),
    {
      method: 'PATCH',
      headers: artifactHeaders(
        artifact,
        true,
        request.idempotency_key,
      ),
      body: JSON.stringify(request),
      signal,
    },
    'Authentic AI could not rename the artifact.',
  )
}

export async function reviseArtifact(
  artifact: ArtifactRecord,
  request: ArtifactRevisionRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/revisions'
    ),
    {
      method: 'POST',
      headers: artifactHeaders(
        artifact,
        true,
        request.idempotency_key,
      ),
      body: JSON.stringify(request),
      signal,
    },
    'Authentic AI could not revise the artifact.',
  )
}

export async function exportArtifact(
  artifact: ArtifactRecord,
  request: ArtifactExportRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/exports'
    ),
    {
      method: 'POST',
      headers: artifactHeaders(
        artifact,
        true,
        request.idempotency_key,
      ),
      body: JSON.stringify(request),
      signal,
    },
    'Authentic AI could not export the artifact.',
  )
}

export async function duplicateArtifact(
  artifact: ArtifactRecord,
  request: ArtifactDuplicateRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/duplicate'
    ),
    {
      method: 'POST',
      headers: artifactHeaders(
        artifact,
        true,
        request.idempotency_key,
      ),
      body: JSON.stringify(request),
      signal,
    },
    'Authentic AI could not duplicate the artifact.',
  )
}

export async function restoreArtifact(
  artifact: ArtifactRecord,
  request: ArtifactRestoreRequest,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/restore'
    ),
    {
      method: 'POST',
      headers: artifactHeaders(
        artifact,
        true,
        request.idempotency_key,
      ),
      body: JSON.stringify(request),
      signal,
    },
    'Authentic AI could not restore the artifact version.',
  )
}

export async function listArtifactVersions(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactVersionListResponse> {
  return requestJson<ArtifactVersionListResponse>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/versions'
    ),
    {
      method: 'GET',
      headers: artifactHeaders(artifact),
      cache: 'no-store',
      signal,
    },
    'Authentic AI could not load artifact versions.',
  )
}

export async function listArtifactAuditEvents(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactAuditResponse> {
  return requestJson<ArtifactAuditResponse>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
      + '/audit'
    ),
    {
      method: 'GET',
      headers: artifactHeaders(artifact),
      cache: 'no-store',
      signal,
    },
    'Authentic AI could not load artifact activity.',
  )
}

function artifactForVersion(
  artifact: ArtifactRecord,
  version: number,
  downloadUrl: string,
  filename: string,
): ArtifactRecord {
  return {
    ...artifact,
    version,
    download_url: downloadUrl,
    filename,
  }
}

async function resolveCurrentArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return getArtifactMetadata(
    artifact,
    signal,
  )
}

async function downloadResolvedArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<void> {
  const blob = await fetchArtifactBlob(
    artifact,
    signal,
  )
  const objectUrl =
    URL.createObjectURL(blob)
  const link =
    document.createElement('a')

  link.href = objectUrl
  link.download = artifact.filename
  link.rel = 'noopener'
  link.style.display = 'none'

  document.body.appendChild(link)
  link.click()
  link.remove()

  window.setTimeout(
    () => URL.revokeObjectURL(objectUrl),
    5_000,
  )
}

export async function downloadArtifactVersion(
  artifact: ArtifactRecord,
  version: number,
  downloadUrl: string,
  filename: string,
  signal?: AbortSignal,
): Promise<void> {
  return downloadResolvedArtifact(
    artifactForVersion(
      artifact,
      version,
      downloadUrl,
      filename,
    ),
    signal,
  )
}

export async function deleteArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<ArtifactDeleteResponse> {
  return requestJson<ArtifactDeleteResponse>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(
        artifact.artifact_id,
      )
    ),
    {
      method: 'DELETE',
      headers: artifactHeaders(artifact),
      signal,
    },
    (
      'Authentic AI could not delete '
      + 'the generated artifact.'
    ),
  )
}

async function fetchArtifactBlob(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<Blob> {
  let response: Response

  try {
    response = await fetch(
      resolveDownloadUrl(
        artifact.download_url,
      ),
      {
        method: 'GET',
        headers: artifactHeaders(artifact),
        cache: 'no-store',
        signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }

    throw new ArtifactApiError(
      (
        'Authentic AI could not connect '
        + 'to the artifact-download service.'
      ),
      0,
    )
  }

  if (!response.ok) {
    throw new ArtifactApiError(
      await readApiError(response),
      response.status,
    )
  }

  const blob = await response.blob()

  if (blob.size <= 0) {
    throw new ArtifactApiError(
      'The artifact download was empty.',
      502,
    )
  }

  return blob
}

export async function openArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<void> {
  const previewWindow = window.open(
    'about:blank',
    '_blank',
  )

  if (!previewWindow) {
    throw new ArtifactApiError(
      'The browser blocked the preview window. Allow pop-ups for Authentic AI and try again.',
      0,
    )
  }

  previewWindow.opener = null
  previewWindow.document.title =
    'Opening artifact…'
  previewWindow.document.body.textContent =
    'Preparing your document preview…'

  try {
    const currentArtifact =
      await resolveCurrentArtifact(
        artifact,
        signal,
      )
    const blob = await fetchArtifactBlob(
      currentArtifact,
      signal,
    )
    const objectUrl =
      URL.createObjectURL(blob)

    previewWindow.location.replace(
      objectUrl,
    )

    window.setTimeout(
      () => URL.revokeObjectURL(objectUrl),
      5 * 60_000,
    )
  } catch (error) {
    previewWindow.close()
    throw error
  }
}

export async function downloadArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<void> {
  const currentArtifact =
    await resolveCurrentArtifact(
      artifact,
      signal,
    )

  return downloadResolvedArtifact(
    currentArtifact,
    signal,
  )
}
