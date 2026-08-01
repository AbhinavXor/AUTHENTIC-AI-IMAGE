export type ArtifactFormat =
  | 'pdf'
  | 'docx'
  | 'pptx'
  | 'zip'

export type ArtifactSourceKind =
  | 'explicit_prompt'
  | 'previous_response'
  | 'conversation'
  | 'uploaded_file'
  | 'artifact_version'
  | 'project_context'

export type ArtifactDocumentType =
  | 'professional_report'
  | 'executive_brief'
  | 'technical_specification'
  | 'research_report'
  | 'proposal'
  | 'policy_document'
  | 'presentation'
  | 'general_document'
  | 'academic_textbook'
  | 'data_report'
  | 'case_study'
  | 'modern_summary'

export type ArtifactLayoutFamily =
  | 'auto'
  | 'executive_report'
  | 'research_paper'
  | 'academic_textbook'
  | 'technical_spec'
  | 'proposal_document'
  | 'data_report'
  | 'case_study'
  | 'modern_summary'

export type ArtifactBrandingMode =
  | 'none'
  | 'title_only'
  | 'subtle'
  | 'full'

export type ArtifactVisualDensity =
  | 'auto'
  | 'compact'
  | 'balanced'
  | 'spacious'

export type ArtifactPresentationTier =
  | 'auto'
  | 'standard'
  | 'professional'
  | 'premium'

export type ArtifactHeaderMode =
  | 'auto'
  | 'none'
  | 'minimal'
  | 'running_section'

export type ArtifactFooterMode =
  | 'none'
  | 'page_number'
  | 'page_number_and_title'

export interface ArtifactSourceSnapshot {
  kind: ArtifactSourceKind
  summary: string
  content?: string
  message_ids: string[]
  attachment_names: string[]
  confidence: number
}

export interface ArtifactSourceReference {
  source_id: string
  access_token: string
}

export interface ArtifactSourceCreateResponse {
  reference: ArtifactSourceReference
  summary: string
  source_characters: number
  created_at: string
  expires_at: string
}

export interface ArtifactGenerateRequest {
  content: string
  format: ArtifactFormat
  title?: string
  subtitle?: string
  author?: string
  filename?: string
  source_snapshot?: ArtifactSourceSnapshot
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
  idempotency_key?: string
}

export interface ArtifactQualityIssue {
  code: string
  message: string
  severity: string
}

export interface ArtifactQualitySummary {
  status:
    | 'passed'
    | 'passed_with_warnings'
    | 'failed'
  page_or_slide_count: number
  error_count: number
  warning_count: number
  issues: ArtifactQualityIssue[]
}

export interface ArtifactRecord {
  artifact_id: string
  access_token: string
  filename: string
  title: string
  format: ArtifactFormat
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
  updated_at: string
  expires_at: string
  download_url: string
  version: number
  version_count: number
  page_or_slide_count: number
  validation: ArtifactQualitySummary
}

export interface ArtifactSourceResponse {
  artifact_id: string
  version: number
  title: string
  filename: string
  kind: ArtifactSourceKind
  summary: string
  content: string
  message_ids: string[]
  attachment_names: string[]
  confidence: number
  recovered_from:
    | 'source_snapshot'
    | 'artifact_version'
}


export interface ArtifactRenameRequest {
  filename: string
  expected_version?: number
  idempotency_key?: string
}

export interface ArtifactRevisionRequest {
  instruction: string
  title?: string
  expected_version?: number
  idempotency_key?: string
}

export interface ArtifactExportRequest {
  format: ArtifactFormat
  expected_version?: number
  idempotency_key?: string
}

export interface ArtifactRestoreRequest {
  version: number
  expected_version?: number
  idempotency_key?: string
}

export interface ArtifactDuplicateRequest {
  filename?: string
  expected_version?: number
  idempotency_key?: string
}

export interface ArtifactVersionRecord {
  version: number
  filename: string
  format: ArtifactFormat
  media_type: string
  size_bytes: number
  sha256: string
  created_at: string
  expires_at: string
  page_or_slide_count: number
  validation: ArtifactQualitySummary
  is_current: boolean
  download_url: string
}

export interface ArtifactVersionListResponse {
  artifact_id: string
  current_version: number
  versions: ArtifactVersionRecord[]
}

export interface ArtifactAuditEvent {
  action: string
  timestamp: string
  detail: Record<string, unknown>
}

export interface ArtifactAuditResponse {
  artifact_id: string
  events: ArtifactAuditEvent[]
}

export interface ArtifactDeleteResponse {
  artifact_id: string
  deleted: boolean
}
