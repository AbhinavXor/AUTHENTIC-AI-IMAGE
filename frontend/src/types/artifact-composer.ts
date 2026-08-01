import type {
  ArtifactBrandingMode,
  ArtifactDocumentType,
  ArtifactFooterMode,
  ArtifactFormat,
  ArtifactHeaderMode,
  ArtifactLayoutFamily,
  ArtifactPresentationTier,
  ArtifactRecord,
  ArtifactSourceSnapshot,
  ArtifactSourceReference,
  ArtifactVisualDensity,
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

export type ArtifactPromptMode =
  | 'auto'
  | 'standard'
  | 'compact'

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
  document_type?: ArtifactDocumentType
  purpose?: string
  audience?: string
  layout_family?: ArtifactLayoutFamily
  branding_mode?: ArtifactBrandingMode
  visual_density?: ArtifactVisualDensity
  presentation_tier?: ArtifactPresentationTier
  header_mode?: ArtifactHeaderMode
  footer_mode?: ArtifactFooterMode
  include_table_of_contents?: boolean
  include_section_openers?: boolean
  include_cover_date?: boolean
  include_cover_profile?: boolean
  include_document_label?: boolean
  include_cover_subtitle?: boolean
  source_snapshot?: ArtifactSourceSnapshot
  source_ref?: ArtifactSourceReference
  profile_id?: string
  prompt_mode?: ArtifactPromptMode
  idempotency_key?: string
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
