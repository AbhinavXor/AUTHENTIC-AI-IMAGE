import type {
  ArtifactComposeRequest,
  ArtifactComposeResponse,
} from '../types/artifact-composer'
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
     * The backend did not return
     * a readable JSON error body.
     */
  }

  return (
    'The AI artifact request '
    + 'could not be completed.'
  )
}

export async function composeArtifact(
  request: ArtifactComposeRequest,
  signal?: AbortSignal,
): Promise<ArtifactComposeResponse> {
  let response: Response

  try {
    response = await fetch(
      `${apiBaseUrl}/artifacts/compose`,
      {
        method: 'POST',
        headers: {
          'Content-Type':
            'application/json',
        },
        body: JSON.stringify(request),
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
        + 'to the AI artifact service.'
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

  return (
    await response.json()
  ) as ArtifactComposeResponse
}