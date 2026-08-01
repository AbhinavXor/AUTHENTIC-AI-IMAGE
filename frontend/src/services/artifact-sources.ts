import type {
  ArtifactSourceCreateResponse,
  ArtifactSourceSnapshot,
} from '../types/artifacts'
import {
  ArtifactApiError,
} from './artifacts'


const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL ??
  'http://127.0.0.1:8000/api/v1'
).replace(/\/$/, '')


async function readError(
  response: Response,
): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: string
    }
    if (payload.detail) {
      return payload.detail
    }
  } catch {
    // Fall through to the private generic message.
  }
  return 'The uploaded source could not be prepared for document generation.'
}


async function sourceRequest(
  url: string,
  init: RequestInit,
): Promise<ArtifactSourceCreateResponse> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch (error) {
    if (
      error instanceof DOMException
      && error.name === 'AbortError'
    ) {
      throw error
    }
    throw new ArtifactApiError(
      'Authentic AI could not connect to the durable source service.',
      0,
    )
  }
  if (!response.ok) {
    throw new ArtifactApiError(
      await readError(response),
      response.status,
    )
  }
  return (await response.json()) as ArtifactSourceCreateResponse
}


export async function createTextArtifactSource(
  snapshot: ArtifactSourceSnapshot,
  signal?: AbortSignal,
): Promise<ArtifactSourceCreateResponse> {
  if (!snapshot.content) {
    throw new ArtifactApiError(
      'The source snapshot does not contain durable content.',
      422,
    )
  }
  return sourceRequest(
    `${apiBaseUrl}/artifact-sources/text`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(snapshot),
      signal,
    },
  )
}


export async function createUploadedArtifactSource(
  file: File,
  signal?: AbortSignal,
): Promise<ArtifactSourceCreateResponse> {
  const body = new FormData()
  body.append('file', file, file.name)
  return sourceRequest(
    `${apiBaseUrl}/artifact-sources/upload`,
    {
      method: 'POST',
      body,
      signal,
    },
  )
}
