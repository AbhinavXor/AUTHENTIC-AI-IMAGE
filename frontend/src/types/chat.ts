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
  model?: string
  isStreaming?: boolean
  attachment?: ConversationAttachment
}

export interface ConversationRecord {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ConversationMessage[]
}
