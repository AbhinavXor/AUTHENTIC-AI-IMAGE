import type {
  ArtifactComposeRequest,
  ArtifactComposeResponse,
} from './artifact-composer'

export type ArtifactJobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'

export interface ArtifactJobCreateRequest
  extends ArtifactComposeRequest {}

export interface ArtifactJobCreateResponse {
  job_id: string
  status: ArtifactJobStatus
  access_token: string
  created_at: string
  expires_at: string
  status_url: string
  message: string
}

export interface ArtifactJobStatusResponse {
  job_id: string
  status: ArtifactJobStatus
  progress_percent: number
  stage: string
  created_at: string
  updated_at: string
  expires_at: string
  artifact:
    | ArtifactComposeResponse
    | null
  error: string | null
}

export interface ArtifactJobDeleteResponse {
  job_id: string
  deleted: boolean
}

export interface ActiveArtifactJob {
  jobId: string
  accessToken: string
  status: ArtifactJobStatus
  progressPercent: number
  stage: string
  createdAt: string
  expiresAt: string
  artifact:
    | ArtifactComposeResponse
    | null
  error: string | null
}