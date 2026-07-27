import type {
  ArtifactFormat,
  ArtifactRecord,
} from './artifacts'

export type ArtifactTone =
  | 'professional'
  | 'executive'
  | 'technical'
  | 'simple'
  | 'academic'

export type ArtifactLength =
  | 'brief'
  | 'standard'
  | 'detailed'

export interface ArtifactComposeRequest {
  prompt: string
  format: ArtifactFormat
  title?: string
  subtitle?: string
  author?: string
  filename?: string
  tone: ArtifactTone
  length: ArtifactLength
  language: string
  include_executive_summary: boolean
  include_table: boolean
  include_recommendations: boolean
  include_conclusion: boolean
}

export interface ArtifactComposeResponse
  extends ArtifactRecord {
  provider: string
  model: string
  request_id: string | null
  draft_character_count: number
  composition_mode:
    'ai_prompt_to_artifact'
}