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

interface DocumentCitationContext {
  page: number
  label: string
}

interface DocumentMetadataContext {
  title: string | null
  author: string | null
  subject: string | null
  creator: string | null
  producer: string | null
}

interface DocumentMessageContext {
  analysisMode:
    | 'text'
    | 'vision_ocr'

  pageCount: number
  selectedPages: number[]
  ocrPages: number[]

  citations:
    DocumentCitationContext[]

  metadata:
    DocumentMetadataContext
}

interface ParsedAssistantContent {
  displayContent: string
  documentContext:
    | DocumentMessageContext
    | null
}

type FeedbackValue =
  | 'helpful'
  | 'not-helpful'
  | null

const documentContextPattern =
  /(?:\r?\n){0,2}<!--AUTHENTIC_DOCUMENT_CONTEXT:([^>]*)-->\s*$/

function parseAssistantContent(
  content: string,
): ParsedAssistantContent {
  const match =
    content.match(
      documentContextPattern,
    )

  if (!match) {
    return {
      displayContent: content,
      documentContext: null,
    }
  }

  const displayContent =
    content
      .replace(
        documentContextPattern,
        '',
      )
      .trimEnd()

  try {
    const decoded =
      decodeURIComponent(
        match[1],
      )

    const parsed =
      JSON.parse(
        decoded,
      ) as DocumentMessageContext

    if (
      !parsed ||
      (
        parsed.analysisMode !==
          'text' &&
        parsed.analysisMode !==
          'vision_ocr'
      ) ||
      !Array.isArray(
        parsed.selectedPages,
      ) ||
      !Array.isArray(
        parsed.citations,
      )
    ) {
      return {
        displayContent,
        documentContext: null,
      }
    }

    return {
      displayContent,
      documentContext: parsed,
    }
  } catch {
    return {
      displayContent,
      documentContext: null,
    }
  }
}

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
        type:
          'text/markdown;charset=utf-8',
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

function DocumentSources({
  context,
}: {
  context: DocumentMessageContext
}) {
  const modeLabel =
    context.analysisMode ===
    'vision_ocr'
      ? 'Vision OCR'
      : 'Document text'

  const reviewedPages =
    context.selectedPages.length

  const pageLabel =
    reviewedPages === 1
      ? 'page reviewed'
      : 'pages reviewed'

  const sourceTitle =
    context.metadata.title ||
    context.metadata.subject ||
    'Uploaded PDF'

  return (
    <section
      aria-label="Document sources"
      className={`document-source-panel ${
        context.analysisMode ===
        'vision_ocr'
          ? 'is-ocr'
          : 'is-text'
      }`}
    >
      <div className="document-source-overview">
        <div className="document-source-identity">
          <span className="document-source-icon">
            <FileText
              size={15}
              strokeWidth={1.8}
            />
          </span>

          <div>
            <strong>
              {modeLabel}
            </strong>

            <span>
              {reviewedPages}{' '}
              {pageLabel}
            </span>
          </div>
        </div>

        <span
          className="document-source-title"
          title={sourceTitle}
        >
          {sourceTitle}
        </span>
      </div>

      {context.citations.length >
        0 && (
        <div className="document-source-citations">
          <span className="document-sources-label">
            Sources
          </span>

          <div className="document-source-chip-list">
            {context.citations.map(
              (citation) => (
                <span
                  className="document-source-chip"
                  key={
                    citation.page
                  }
                  title={`Source ${citation.label}`}
                >
                  {citation.label}
                </span>
              ),
            )}
          </div>
        </div>
      )}
    </section>
  )
}

function ResponseActions({
  content,
  documentContext,
}: {
  content: string
  documentContext:
    | DocumentMessageContext
    | null
}) {
  const [feedback, setFeedback] =
    useState<FeedbackValue>(null)

  return (
    <footer
      aria-label="Response actions"
      className={`assistant-response-actions ${
        documentContext
          ? 'has-document-sources'
          : ''
      }`}
    >
      {documentContext && (
        <DocumentSources
          context={documentContext}
        />
      )}

      <div className="response-action-buttons">
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
            feedback ===
            'not-helpful'
          }
          className={`response-action-button ${
            feedback ===
            'not-helpful'
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
      </div>
    </footer>
  )
}

function AssistantMessage({
  message,
}: {
  message: ConversationMessage
}) {
  const {
    displayContent,
    documentContext,
  } = parseAssistantContent(
    message.content,
  )

  const hasContent =
    displayContent.length > 0

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
              {displayContent}
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
          displayContent && (
            <ResponseActions
              content={displayContent}
              documentContext={
                documentContext
              }
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
    attachment.kind ===
    'document'
      ? FileText
      : FileImage

  const attachmentLabel =
    attachment.kind ===
    'document'
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
