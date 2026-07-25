import {
  Check,
  Copy,
  Download,
  FileImage,
  FileText,
  ThumbsDown,
  ThumbsUp,
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

type FeedbackValue =
  | 'helpful'
  | 'not-helpful'
  | null

function CopyButton({
  content,
}: {
  content: string
}) {
  const [copied, setCopied] =
    useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(
        content,
      )

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
      aria-label={
        copied
          ? 'Response copied'
          : 'Copy response'
      }
      className="response-action-button"
      onClick={handleCopy}
      title={
        copied
          ? 'Copied'
          : 'Copy response'
      }
      type="button"
    >
      {copied ? (
        <Check
          size={15}
          strokeWidth={1.9}
        />
      ) : (
        <Copy
          size={15}
          strokeWidth={1.8}
        />
      )}
    </button>
  )
}

function DownloadResponseButton({
  content,
}: {
  content: string
}) {
  const handleDownload = () => {
    const blob = new Blob(
      [content],
      {
        type: 'text/markdown;charset=utf-8',
      },
    )

    const url =
      URL.createObjectURL(blob)

    const link =
      document.createElement('a')

    link.href = url
    link.download =
      'serenya-response.md'

    document.body.appendChild(link)
    link.click()
    link.remove()

    window.setTimeout(() => {
      URL.revokeObjectURL(url)
    }, 0)
  }

  return (
    <button
      aria-label="Download response"
      className="response-action-button"
      onClick={handleDownload}
      title="Download response"
      type="button"
    >
      <Download
        size={15}
        strokeWidth={1.8}
      />
    </button>
  )
}

function ResponseActions({
  content,
}: {
  content: string
}) {
  const [feedback, setFeedback] =
    useState<FeedbackValue>(null)

  return (
    <footer
      aria-label="Response actions"
      className="assistant-response-actions"
    >
      <CopyButton
        content={content}
      />

      <button
        aria-label="Mark response as helpful"
        aria-pressed={
          feedback === 'helpful'
        }
        className={`response-action-button ${
          feedback === 'helpful'
            ? 'active'
            : ''
        }`}
        onClick={() =>
          setFeedback(
            (current) =>
              current === 'helpful'
                ? null
                : 'helpful',
          )
        }
        title="Helpful"
        type="button"
      >
        <ThumbsUp
          size={15}
          strokeWidth={1.8}
        />
      </button>

      <button
        aria-label="Mark response as not helpful"
        aria-pressed={
          feedback === 'not-helpful'
        }
        className={`response-action-button ${
          feedback === 'not-helpful'
            ? 'active'
            : ''
        }`}
        onClick={() =>
          setFeedback(
            (current) =>
              current ===
              'not-helpful'
                ? null
                : 'not-helpful',
          )
        }
        title="Not helpful"
        type="button"
      >
        <ThumbsDown
          size={15}
          strokeWidth={1.8}
        />
      </button>

      <DownloadResponseButton
        content={content}
      />
    </footer>
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
          <strong>
            Serenya
          </strong>

          {message.isStreaming && (
            <span className="streaming-status">
              Responding
            </span>
          )}
        </header>

        {!hasContent &&
        message.isStreaming ? (
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
              remarkPlugins={[
                remarkGfm,
              ]}
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
            <ResponseActions
              content={message.content}
            />
          )}
      </div>
    </article>
  )
}

function UserAttachment({
  message,
}: {
  message: ConversationMessage
}) {
  const attachment =
    message.attachment

  if (!attachment) {
    return null
  }

  if (
    attachment.kind === 'image' &&
    attachment.previewUrl
  ) {
    return (
      <figure className="message-image-attachment">
        <img
          alt={`Uploaded file ${attachment.name}`}
          src={attachment.previewUrl}
        />

        <figcaption>
          <FileImage
            size={14}
            strokeWidth={1.8}
          />

          <span>
            {attachment.name}
          </span>
        </figcaption>
      </figure>
    )
  }

    const AttachmentIcon =
    attachment.kind === 'document'
      ? FileText
      : FileImage

  const attachmentLabel =
    attachment.kind === 'document'
      ? 'Uploaded PDF'
      : 'Uploaded image'

  return (
    <div className="message-file-attachment">
      <AttachmentIcon
        size={17}
        strokeWidth={1.8}
      />

      <div>
        <strong>
          {attachment.name}
        </strong>

        <span>
          {attachmentLabel}
        </span>
      </div>
    </div>
  )
}

function UserMessage({
  message,
}: {
  message: ConversationMessage
}) {
  return (
    <article className="chat-message user-message">
      <div className="user-message-stack">
        <UserAttachment
          message={message}
        />

        {message.content && (
          <div className="user-message-bubble">
            {message.content}
          </div>
        )}
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
        message.role ===
        'assistant' ? (
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
