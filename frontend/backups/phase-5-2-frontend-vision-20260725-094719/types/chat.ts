export type ConversationRole =
  | 'user'
  | 'assistant'

export interface ConversationMessage {
  id: string
  role: ConversationRole
  content: string
  model?: string
  isStreaming?: boolean
}

export interface ConversationRecord {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ConversationMessage[]
}
