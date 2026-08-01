import type {
  ArtifactFormat,
} from './artifacts'


export type ArtifactIntentAction =
  | 'create'
  | 'revise'
  | 'none'


export interface ArtifactIntentDecision {
  action: ArtifactIntentAction
  format: ArtifactFormat | null
  confidence: number
  reason: string
  source:
    | 'deterministic'
    | 'ai'
    | 'fallback'
}


export interface ArtifactIntentContext {
  hasAttachment: boolean
  attachmentNames: string[]
  hasGeneratedArtifact: boolean
}

