import {
  Check,
  Copy,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BrandMark } from '../Brand/BrandMark'
import type {
  ConversationMessage,
} from '../../types/chat'

interface ChatTranscriptProps {
  messages: ConversationMessage[]
}

function CopyButton({
  content,
}: {
  content: string
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)

      window.setTimeout(() => {
        setCopied(false)
      }, 1_500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <button
      aria-label="Copy response"
      className="message-copy-button"
      onClick={handleCopy}
      type="button"
    >
      {copied ? (
        <Check size={15} />
      ) : (
        <Copy size={15} />
      )}

      <span>
        {copied ? 'Copied' : 'Copy'}
      </span>
    </button>
  )
}

function AssistantMessage({
  message,
}: {
  message: ConversationMessage
}) {
  const hasContent =
    message.content.length > 0

  return (
    <article className="chat-message assistant-message">
      <div className="assistant-message-avatar">
        <BrandMark size={20} />
      </div>

      <div className="assistant-message-column">
        <header className="assistant-message-header">
          <strong>Serenya</strong>

          {message.isStreaming && (
            <span className="streaming-status">
              Responding
            </span>
          )}
        </header>

        {!hasContent && message.isStreaming ? (
          <div
            aria-label="Serenya is thinking"
            className="thinking-indicator"
          >
            <span />
            <span />
            <span />
          </div>
        ) : (
          <div className="markdown-answer">
            <ReactMarkdown
              components={{
                a: ({
                  children,
                  ...properties
                }) => (
                  <a
                    {...properties}
                    rel="noreferrer noopener"
                    target="_blank"
                  >
                    {children}
                  </a>
                ),
              }}
              remarkPlugins={[remarkGfm]}
            >
              {message.content}
            </ReactMarkdown>

            {message.isStreaming && (
              <span
                aria-hidden="true"
                className="streaming-cursor"
              />
            )}
          </div>
        )}

        {!message.isStreaming &&
          message.content && (
            <footer className="assistant-message-actions">
              <CopyButton
                content={message.content}
              />
            </footer>
          )}
      </div>
    </article>
  )
}

function UserMessage({
  message,
}: {
  message: ConversationMessage
}) {
  return (
    <article className="chat-message user-message">
      <div className="user-message-bubble">
        {message.content}
      </div>

      <div
        aria-label="You"
        className="user-message-avatar"
      >
        S
      </div>
    </article>
  )
}

export function ChatTranscript({
  messages,
}: ChatTranscriptProps) {
  const bottomRef =
    useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'end',
    })
  }, [messages])

  return (
    <section
      aria-label="Conversation"
      className="chat-transcript"
    >
      {messages.map((message) =>
        message.role === 'assistant' ? (
          <AssistantMessage
            key={message.id}
            message={message}
          />
        ) : (
          <UserMessage
            key={message.id}
            message={message}
          />
        ),
      )}

      <div ref={bottomRef} />
    </section>
  )
}
