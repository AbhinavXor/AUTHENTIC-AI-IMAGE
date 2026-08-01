import type {
  ChatArtifactMessage,
} from './chat-artifacts'


export type ConversationRole =
  | 'user'
  | 'assistant'


export type AttachmentKind =
  | 'image'
  | 'document'


export interface ConversationAttachment {
  name: string
  mimeType: string
  kind: AttachmentKind
  previewUrl?: string
}


export interface ConversationMessage {
  id: string
  role: ConversationRole
  content: string

  /** Full artifact source retained separately from compact chat previews. */
  artifactSourceContent?: string

  /** Durable IndexedDB key used when the source is too large for localStorage. */
  artifactSourceRef?: string

  model?: string
  isStreaming?: boolean

  attachment?:
    ConversationAttachment

  artifact?:
    ChatArtifactMessage
}


export interface ConversationRecord {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ConversationMessage[]
}
