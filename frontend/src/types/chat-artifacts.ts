import type {
  ArtifactLength,
  ArtifactTone,
} from './artifact-composer'
import type {
  ArtifactBrandingMode,
  ArtifactFooterMode,
  ArtifactFormat,
  ArtifactHeaderMode,
  ArtifactLayoutFamily,
  ArtifactRecord,
  ArtifactVisualDensity,
} from './artifacts'


export type ChatArtifactTrigger =
  | 'automatic'
  | 'manual'


export type ChatArtifactStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'


export interface ChatArtifactSettings {
  enabled: boolean

  format: ArtifactFormat
  tone: ArtifactTone
  length: ArtifactLength
  language: string

  title: string
  subtitle: string
  author: string
  filename: string

  layoutFamily: ArtifactLayoutFamily
  brandingMode: ArtifactBrandingMode
  visualDensity: ArtifactVisualDensity
  headerMode: ArtifactHeaderMode
  footerMode: ArtifactFooterMode
  includeTableOfContents: boolean
  includeSectionOpeners: boolean
  includeCoverDate: boolean
  includeCoverProfile: boolean
  includeDocumentLabel: boolean
  includeCoverSubtitle: boolean

  includeExecutiveSummary: boolean
  includeTable: boolean
  includeRecommendations: boolean
  includeConclusion: boolean
}


export interface ChatArtifactMessage {
  trigger: ChatArtifactTrigger

  format: ArtifactFormat
  title: string
  filename: string

  status: ChatArtifactStatus
  progressPercent: number
  stage: string

  artifact: ArtifactRecord | null
  error: string | null

  job?: {
    jobId: string
    accessToken: string
  }
}


export interface ActiveChatArtifactJob {
  messageId: string

  jobId: string
  accessToken: string

  prompt: string
  settings: ChatArtifactSettings

  createdAt: string
  expiresAt: string
}


export const defaultChatArtifactSettings:
  ChatArtifactSettings = {
    enabled: false,

    format: 'pdf',
    tone: 'professional',
    length: 'standard',
    language: 'English',

    title: '',
    subtitle: '',
    author: '',
    filename: '',

    layoutFamily: 'auto',
    brandingMode: 'none',
    visualDensity: 'auto',
    headerMode: 'auto',
    footerMode: 'none',
    includeTableOfContents: true,
    includeSectionOpeners: true,
    includeCoverDate: false,
    includeCoverProfile: false,
    includeDocumentLabel: false,
    includeCoverSubtitle: false,

    includeExecutiveSummary: true,
    includeTable: true,
    includeRecommendations: true,
    includeConclusion: true,
  }


export function cloneChatArtifactSettings():
  ChatArtifactSettings {
  return {
    ...defaultChatArtifactSettings,
  }
}
