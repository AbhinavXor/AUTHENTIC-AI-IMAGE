import type {
  ArtifactDeleteResponse,
  ArtifactGenerateRequest,
  ArtifactRecord,
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
    // Use fallback message below.
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

async function requestJson<T>(
  url: string,
  init: RequestInit,
  connectionMessage: string,
): Promise<T> {
  let response: Response

  try {
    response = await fetch(
      url,
      init,
    )
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
  artifactId: string,
  signal?: AbortSignal,
): Promise<ArtifactRecord> {
  return requestJson<ArtifactRecord>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(artifactId)
    ),
    {
      method: 'GET',
      signal,
    },
    (
      'Authentic AI could not load '
      + 'the artifact metadata.'
    ),
  )
}

export async function deleteArtifact(
  artifactId: string,
  signal?: AbortSignal,
): Promise<ArtifactDeleteResponse> {
  return requestJson<ArtifactDeleteResponse>(
    (
      `${apiBaseUrl}/artifacts/`
      + encodeURIComponent(artifactId)
    ),
    {
      method: 'DELETE',
      signal,
    },
    (
      'Authentic AI could not delete '
      + 'the generated artifact.'
    ),
  )
}

export async function downloadArtifact(
  artifact: ArtifactRecord,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response

  try {
    response = await fetch(
      resolveDownloadUrl(
        artifact.download_url,
      ),
      {
        method: 'GET',
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
    1_000,
  )
}