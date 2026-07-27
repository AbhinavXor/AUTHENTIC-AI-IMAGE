export type ArtifactFormat =
  | 'pdf'
  | 'docx'
  | 'pptx'

export interface ArtifactGenerateRequest {
  content: string
  format: ArtifactFormat
  title?: string
  subtitle?: string
  author?: string
  filename?: string
}

export interface ArtifactRecord {
  artifact_id: string
  filename: string
  format: ArtifactFormat
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
  expires_at: string
  download_url: string
}

export interface ArtifactDeleteResponse {
  artifact_id: string
  deleted: boolean
}