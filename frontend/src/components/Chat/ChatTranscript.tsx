import {
  Check,
  Copy,
  Download,
  FileCode2,
  FileImage,
  FileText,
  ThumbsDown,
  ThumbsUp,
} from 'lucide-react'
import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { BrandMark } from '../Brand/BrandMark'
import {
  parseChartResponse,
} from '../../lib/visualization'
import type {
  ConversationMessage,
} from '../../types/chat'

interface ChatTranscriptProps {
  messages: ConversationMessage[]
}

interface PdfCitationContext {
  page: number
  label: string
}

interface PdfMetadataContext {
  title: string | null
  author: string | null
  subject: string | null
  creator: string | null
  producer: string | null
}

interface PdfSourceContext {
  kind: 'pdf'

  analysisMode:
    | 'text'
    | 'vision_ocr'

  pageCount: number
  selectedPages: number[]
  ocrPages: number[]

  citations:
    PdfCitationContext[]

  metadata:
    PdfMetadataContext
}

interface StructuredCitationContext {
  source_id: string
  label: string

  kind:
    | 'section'
    | 'table'
    | 'lines'
}

interface StructuredMetadataContext {
  title: string | null
  author: string | null
  subject: string | null
  keywords: string | null
  created: string | null
  modified: string | null
}

interface StructuredSourceContext {
  kind: 'structured'

  documentType:
    | 'docx'
    | 'text'
    | 'markdown'
    | 'json'
    | 'source_code'

  filename: string
  sourceCount: number
  selectedSources: string[]

  citations:
    StructuredCitationContext[]

  metadata:
    StructuredMetadataContext
}

type AssistantSourceContext =
  | PdfSourceContext
  | StructuredSourceContext

interface ParsedAssistantContent {
  displayContent: string
  sourceContext:
    | AssistantSourceContext
    | null
}

type FeedbackValue =
  | 'helpful'
  | 'not-helpful'
  | null

const pdfContextPattern =
  /(?:\r?\n){0,2}<!--AUTHENTIC_DOCUMENT_CONTEXT:([^>]*)-->\s*$/

const structuredContextPattern =
  /(?:\r?\n){0,2}<!--AUTHENTIC_STRUCTURED_DOCUMENT_CONTEXT:([^>]*)-->\s*$/

const ChartRenderer = lazy(
  () =>
    import(
      '../Visualization/ChartRenderer'
    ),
)

const codeExtensions =
  new Set([
    '.py',
    '.js',
    '.jsx',
    '.ts',
    '.tsx',
    '.java',
    '.go',
    '.rs',
    '.c',
    '.h',
    '.cpp',
    '.hpp',
    '.cs',
    '.rb',
    '.php',
    '.swift',
    '.kt',
    '.kts',
    '.sql',
    '.sh',
    '.bash',
    '.zsh',
    '.yaml',
    '.yml',
    '.toml',
    '.xml',
    '.html',
    '.htm',
    '.css',
    '.scss',
  ])

function fileExtension(
  filename: string,
): string {
  const finalDot =
    filename.lastIndexOf('.')

  if (finalDot < 0) {
    return ''
  }

  return filename
    .slice(finalDot)
    .toLowerCase()
}

function parseAssistantContent(
  content: string,
): ParsedAssistantContent {
  const structuredMatch =
    content.match(
      structuredContextPattern,
    )

  if (structuredMatch) {
    const displayContent =
      content
        .replace(
          structuredContextPattern,
          '',
        )
        .trimEnd()

    try {
      const parsed =
        JSON.parse(
          decodeURIComponent(
            structuredMatch[1],
          ),
        ) as Omit<
          StructuredSourceContext,
          'kind'
        >

      if (
        parsed &&
        Array.isArray(
          parsed.selectedSources,
        ) &&
        Array.isArray(
          parsed.citations,
        )
      ) {
        return {
          displayContent,
          sourceContext: {
            ...parsed,
            kind: 'structured',
          },
        }
      }
    } catch {
      return {
        displayContent,
        sourceContext: null,
      }
    }
  }

  const pdfMatch =
    content.match(
      pdfContextPattern,
    )

  if (pdfMatch) {
    const displayContent =
      content
        .replace(
          pdfContextPattern,
          '',
        )
        .trimEnd()

    try {
      const parsed =
        JSON.parse(
          decodeURIComponent(
            pdfMatch[1],
          ),
        ) as Omit<
          PdfSourceContext,
          'kind'
        >

      if (
        parsed &&
        (
          parsed.analysisMode ===
            'text' ||
          parsed.analysisMode ===
            'vision_ocr'
        ) &&
        Array.isArray(
          parsed.selectedPages,
        ) &&
        Array.isArray(
          parsed.citations,
        )
      ) {
        return {
          displayContent,
          sourceContext: {
            ...parsed,
            kind: 'pdf',
          },
        }
      }
    } catch {
      return {
        displayContent,
        sourceContext: null,
      }
    }
  }

  return {
    displayContent: content,
    sourceContext: null,
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

    document.body.appendChild(
      link,
    )

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

function structuredModeLabel(
  documentType:
    StructuredSourceContext['documentType'],
): string {
  switch (documentType) {
    case 'docx':
      return 'Word document'

    case 'markdown':
      return 'Markdown document'

    case 'json':
      return 'JSON document'

    case 'source_code':
      return 'Source code'

    default:
      return 'Text document'
  }
}

function SourcePanel({
  context,
}: {
  context: AssistantSourceContext
}) {
  const isPdf =
    context.kind === 'pdf'

  const modeLabel = isPdf
    ? (
        context.analysisMode ===
        'vision_ocr'
          ? 'Vision OCR'
          : 'Document text'
      )
    : structuredModeLabel(
        context.documentType,
      )

  const reviewedCount = isPdf
    ? context.selectedPages.length
    : context.selectedSources.length

  const reviewedLabel = isPdf
    ? (
        reviewedCount === 1
          ? 'page reviewed'
          : 'pages reviewed'
      )
    : (
        reviewedCount === 1
          ? 'source reviewed'
          : 'sources reviewed'
      )

  const sourceTitle = isPdf
    ? (
        context.metadata.title ||
        context.metadata.subject ||
        'Uploaded PDF'
      )
    : (
        context.metadata.title ||
        context.metadata.subject ||
        context.filename
      )

  const citations = isPdf
    ? context.citations.map(
        (citation) => ({
          id: String(
            citation.page,
          ),
          label:
            citation.label,
          kind: 'page',
        }),
      )
    : context.citations.map(
        (citation) => ({
          id:
            citation.source_id,
          label:
            citation.label,
          kind:
            citation.kind,
        }),
      )

  const SourceIcon =
    !isPdf &&
    context.documentType ===
      'source_code'
      ? FileCode2
      : FileText

  return (
    <section
      aria-label="Document sources"
      className={`document-source-panel ${
        isPdf
          ? (
              context.analysisMode ===
              'vision_ocr'
                ? 'is-ocr'
                : 'is-text'
            )
          : 'is-structured'
      }`}
    >
      <div className="document-source-overview">
        <div className="document-source-identity">
          <span className="document-source-icon">
            <SourceIcon
              size={15}
              strokeWidth={1.8}
            />
          </span>

          <div>
            <strong>
              {modeLabel}
            </strong>

            <span>
              {reviewedCount}{' '}
              {reviewedLabel}
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

      {citations.length > 0 && (
        <div className="document-source-citations">
          <span className="document-sources-label">
            Sources
          </span>

          <div className="document-source-chip-list">
            {citations.map(
              (citation) => (
                <span
                  className={`document-source-chip is-${citation.kind}`}
                  key={
                    citation.id
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
  sourceContext,
}: {
  content: string
  sourceContext:
    | AssistantSourceContext
    | null
}) {
  const [feedback, setFeedback] =
    useState<FeedbackValue>(null)

  return (
    <footer
      aria-label="Response actions"
      className={`assistant-response-actions ${
        sourceContext
          ? 'has-document-sources'
          : ''
      }`}
    >
      {sourceContext && (
        <SourcePanel
          context={sourceContext}
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
    sourceContext,
  } = parseAssistantContent(
    message.content,
  )

  /*
   * Do not expose incomplete chart JSON while
   * the response is still streaming.
   */
  const streamingMarkdown =
    displayContent
      .replace(
        /```authentic-chart[\s\S]*$/i,
        '',
      )
      .trimEnd()

  const chartResponse =
    message.isStreaming
      ? {
          markdown:
            streamingMarkdown,
          charts: [],
          rejectedCount: 0,
        }
      : parseChartResponse(
          displayContent,
        )

  const hasContent =
    chartResponse.markdown.length >
      0 ||
    chartResponse.charts.length >
      0

  const responseActionContent =
    chartResponse.markdown ||
    chartResponse.charts
      .map(
        (chart) =>
          chart.title,
      )
      .join('\n')

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
          <div className="assistant-content-stack">
            {chartResponse.markdown && (
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
                  {chartResponse.markdown}
                </ReactMarkdown>
              </div>
            )}

            {chartResponse.charts.length >
              0 && (
              <div className="assistant-visualizations">
                {chartResponse.charts.map(
                  (
                    chart,
                    index,
                  ) => (
                    <Suspense
                      fallback={
                        <div className="authentic-chart-loading">
                          Preparing visualization…
                        </div>
                      }
                      key={`${message.id}:chart:${index}`}
                    >
                      <ChartRenderer
                        spec={chart}
                      />
                    </Suspense>
                  ),
                )}
              </div>
            )}

            {!message.isStreaming &&
              chartResponse.rejectedCount >
                0 && (
                <div
                  className="authentic-chart-error"
                  role="alert"
                >
                  A visualization was not
                  displayed because its chart
                  specification was invalid.
                </div>
              )}

            {message.isStreaming && (
              <span
                aria-hidden="true"
                className="streaming-cursor"
              />
            )}
          </div>
        )}

        {!message.isStreaming &&
          hasContent && (
            <ResponseActions
              content={
                responseActionContent
              }
              sourceContext={
                sourceContext
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

  const extension =
    fileExtension(
      attachment.name,
    )

  const isCode =
    codeExtensions.has(
      extension,
    )

  const AttachmentIcon =
    isCode
      ? FileCode2
      : FileText

  let attachmentLabel =
    'Uploaded document'

  if (extension === '.pdf') {
    attachmentLabel =
      'Uploaded PDF'
  } else if (
    extension === '.docx'
  ) {
    attachmentLabel =
      'Uploaded Word document'
  } else if (isCode) {
    attachmentLabel =
      'Uploaded source code'
  } else if (
    extension === '.json'
  ) {
    attachmentLabel =
      'Uploaded JSON document'
  } else if (
    extension === '.md' ||
    extension === '.markdown'
  ) {
    attachmentLabel =
      'Uploaded Markdown document'
  } else if (
    extension === '.txt'
  ) {
    attachmentLabel =
      'Uploaded text document'
  }

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
