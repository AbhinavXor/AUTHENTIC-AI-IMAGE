import type {
  ArtifactJobCreateRequest,
  ArtifactJobStatus,
  ArtifactJobStatusResponse,
} from '../types/artifact-jobs'

import type {
  ArtifactComposeResponse,
} from '../types/artifact-composer'

import {
  ArtifactApiError,
} from './artifacts'

import {
  createArtifactJob,
  getArtifactJobStatus,
} from './artifact-jobs'


export interface ChatArtifactJobUpdate {
  status: ArtifactJobStatus
  progressPercent: number
  stage: string

  artifact:
    | ArtifactComposeResponse
    | null

  error: string | null
}


interface RunChatArtifactJobOptions {
  signal?: AbortSignal

  onCreated?: (job: {
    jobId: string
    accessToken: string
  }) => void

  onUpdate: (
    update: ChatArtifactJobUpdate,
  ) => void
}


function wait(
  milliseconds: number,
  signal?: AbortSignal,
): Promise<void> {
  return new Promise(
    (resolve, reject) => {
      if (signal?.aborted) {
        reject(
          new DOMException(
            'The request was cancelled.',
            'AbortError',
          ),
        )

        return
      }

      const timeoutId =
        window.setTimeout(
          () => {
            cleanup()
            resolve()
          },
          milliseconds,
        )

      const handleAbort = () => {
        window.clearTimeout(
          timeoutId,
        )

        cleanup()

        reject(
          new DOMException(
            'The request was cancelled.',
            'AbortError',
          ),
        )
      }

      const cleanup = () => {
        signal?.removeEventListener(
          'abort',
          handleAbort,
        )
      }

      signal?.addEventListener(
        'abort',
        handleAbort,
        {
          once: true,
        },
      )
    },
  )
}


function emitStatus(
  status:
    ArtifactJobStatusResponse,
  onUpdate:
    RunChatArtifactJobOptions[
      'onUpdate'
    ],
) {
  onUpdate({
    status: status.status,

    progressPercent:
      status.progress_percent,

    stage: status.stage,

    artifact:
      status.artifact,

    error:
      status.error,
  })
}


export async function runChatArtifactJob(
  request: ArtifactJobCreateRequest,
  options:
    RunChatArtifactJobOptions,
): Promise<ArtifactJobStatusResponse> {
  const created =
    await createArtifactJob(
      request,
      options.signal,
    )

  options.onCreated?.({
    jobId: created.job_id,
    accessToken: created.access_token,
  })

  options.onUpdate({
    status: created.status,
    progressPercent: 0,

    stage:
      created.message
      || 'Artifact generation queued',

    artifact: null,
    error: null,
  })

  const promptCharacters =
    request.prompt.length +
    (request.source_snapshot?.content?.length ?? 0)

  const maximumPollAttempts =
    request.source_ref
      ? 3_600
      : promptCharacters > 250_000
      ? 3_600
      : promptCharacters > 50_000
        ? 1_800
        : 600

  for (
    let attempt = 0;
    attempt < maximumPollAttempts;
    attempt += 1
  ) {
    await wait(
      attempt < 3
        ? 600
        : 1_000,
      options.signal,
    )

    const status =
      await getArtifactJobStatus(
        created.job_id,
        created.access_token,
        options.signal,
      )

    emitStatus(
      status,
      options.onUpdate,
    )

    if (
      status.status ===
        'succeeded'
      || status.status ===
        'failed'
      || status.status ===
        'cancelled'
    ) {
      return status
    }
  }

  throw new ArtifactApiError(
    (
      'Artifact generation is taking '
      + 'longer than expected. '
      + 'Please try again.'
    ),
    408,
  )
}
