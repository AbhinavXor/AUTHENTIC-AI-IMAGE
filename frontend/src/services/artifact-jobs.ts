import type {
  ArtifactJobCreateRequest,
  ArtifactJobCreateResponse,
  ArtifactJobDeleteResponse,
  ArtifactJobStatusResponse,
} from '../types/artifact-jobs'
import {
  ArtifactApiError,
} from './artifacts'

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

const artifactJobTokenHeader =
  'X-Artifact-Job-Token'

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof DOMException &&
    error.name === 'AbortError'
  )
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
      const message =
        payload.detail[0]?.msg

      if (
        typeof message === 'string' &&
        message
      ) {
        return message
      }
    }
  } catch {
    /*
     * Use the safe fallback message
     * when no readable JSON body exists.
     */
  }

  return (
    'The background artifact request '
    + 'could not be completed.'
  )
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

export async function createArtifactJob(
  request: ArtifactJobCreateRequest,
  signal?: AbortSignal,
): Promise<ArtifactJobCreateResponse> {
  return requestJson<ArtifactJobCreateResponse>(
    `${apiBaseUrl}/artifacts/jobs`,
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
      'Authentic AI could not connect '
      + 'to the background artifact service.'
    ),
  )
}

export async function getArtifactJobStatus(
  jobId: string,
  accessToken: string,
  signal?: AbortSignal,
): Promise<ArtifactJobStatusResponse> {
  return requestJson<ArtifactJobStatusResponse>(
    (
      `${apiBaseUrl}/artifacts/jobs/`
      + encodeURIComponent(jobId)
    ),
    {
      method: 'GET',
      headers: {
        [artifactJobTokenHeader]:
          accessToken,
      },
      cache: 'no-store',
      signal,
    },
    (
      'Authentic AI could not load '
      + 'the artifact job status.'
    ),
  )
}

export async function deleteArtifactJob(
  jobId: string,
  accessToken: string,
  signal?: AbortSignal,
): Promise<ArtifactJobDeleteResponse> {
  return requestJson<ArtifactJobDeleteResponse>(
    (
      `${apiBaseUrl}/artifacts/jobs/`
      + encodeURIComponent(jobId)
    ),
    {
      method: 'DELETE',
      headers: {
        [artifactJobTokenHeader]:
          accessToken,
      },
      cache: 'no-store',
      signal,
    },
    (
      'Authentic AI could not delete '
      + 'the artifact job record.'
    ),
  )
}