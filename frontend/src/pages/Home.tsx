import {
  FileSpreadsheet,
  MoreHorizontal,
  Download,
  FileImage,
  Pencil,
  X,
  FileSearch,
  FileText,
  Image,
  ScanSearch,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
} from 'react'
import { BrandMark } from '../components/Brand/BrandMark'
import { ChatTranscript } from '../components/Chat/ChatTranscript'
import { PromptBox } from '../components/Prompt/PromptBox'
import {
  analyzeDocument,
  analyzeImage,
  analyzeStructuredDocument,
  analyzeSpreadsheet,
  ApiError,
  streamQuestion,
  type ChatMessage,
} from '../services/api'
import {
  runChatArtifactJob,
} from '../services/chat-artifact-jobs'
import {
  createTextArtifactSource,
  createUploadedArtifactSource,
} from '../services/artifact-sources'
import {
  parseChartResponse,
} from '../lib/visualization'
import {
  buildChatArtifactJobRequest,
  createChatArtifactIntent,
  createChatArtifactIntentFromDecision,
  detectChatArtifactIntent,
} from '../lib/chatArtifactIntent'
import {
  resolveDynamicArtifactIntent,
} from '../services/artifact-intent'

import {
  routeArtifactCommand,
} from '../lib/artifactCommandRouter'
import {
  artifactSourceHasCompactPreviewGap,
  createExplicitArtifactSource,
  hasSubstantialExplicitArtifactSource,
  resolveArtifactSource,
} from '../lib/artifactSourceResolver'
import {
  resolveArtifactReference,
} from '../lib/artifactReferenceResolver'
import {
  deleteArtifact,
  duplicateArtifact,
  exportArtifact,
  getArtifactSource,
  listArtifactVersions,
  renameArtifact,
  restoreArtifact,
  reviseArtifact,
} from '../services/artifacts'
import {
  createCompactArtifactSourcePreview,
  hydrateArtifactSourceMessages,
  maximumArtifactSourceCharacters,
  recoverArtifactSourcePrompt,
  storeArtifactSource,
} from '../services/artifact-source-vault'
import type {
  ChatArtifactMessage,
} from '../types/chat-artifacts'
import type {
  ConversationAttachment,
  ConversationMessage,
  ConversationRecord,
} from '../types/chat'
import type {
  ArtifactRecord,
  ArtifactSourceReference,
  ArtifactSourceSnapshot,
} from '../types/artifacts'
import type { AppPage } from '../types/navigation'

interface HomeProps {
  initialConversation:
    ConversationRecord | null

  onConversationUpdated: (
    conversation: ConversationRecord,
  ) => void

  onOpenDevelopment: (
    page: AppPage,
  ) => void
}

interface QuickAction {
  label: string
  prompt: string
  icon: LucideIcon
}

const imageTypes = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
])


const imageExtensions =
  new Set([
    '.png',
    '.jpg',
    '.jpeg',
    '.webp',
  ])

const structuredDocumentExtensions =
  new Set([
    '.docx',
    '.txt',
    '.md',
    '.markdown',
    '.json',

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

const maximumImageBytes =
  10 * 1024 * 1024

const maximumPdfBytes =
  20 * 1024 * 1024

const maximumStructuredDocumentBytes =
  10 * 1024 * 1024


const spreadsheetExtensions =
  new Set([
    '.csv',
    '.xlsx',
  ])

const maximumSpreadsheetBytes =
  20 * 1024 * 1024

function isSpreadsheetFile(
  file: File,
): boolean {
  return (
    spreadsheetExtensions.has(
      getFileExtension(
        file.name,
      ),
    )
  )
}

function getFileExtension(
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

function isImageFile(
  file: File,
): boolean {
  return (
    imageTypes.has(
      file.type,
    ) ||
    imageExtensions.has(
      getFileExtension(
        file.name,
      ),
    )
  )
}

function isPdfFile(
  file: File,
): boolean {
  return (
    file.type ===
      'application/pdf' ||
    getFileExtension(
      file.name,
    ) === '.pdf'
  )
}

function isStructuredDocumentFile(
  file: File,
): boolean {
  return (
    structuredDocumentExtensions.has(
      getFileExtension(
        file.name,
      ),
    )
  )
}

function isSupportedUpload(
  file: File,
): boolean {
  return (
    isImageFile(file) ||
    isPdfFile(file) ||
    isSpreadsheetFile(file) ||
    isStructuredDocumentFile(
      file,
    )
  )
}

function getMaximumUploadBytes(
  file: File,
): number {
  if (isPdfFile(file)) {
    return maximumPdfBytes
  }

  if (
    isSpreadsheetFile(file)
  ) {
    return maximumSpreadsheetBytes
  }

  if (
    isStructuredDocumentFile(file)
  ) {
    return (
      maximumStructuredDocumentBytes
    )
  }

  return maximumImageBytes
}

const defaultImagePrompt =
  'Describe this image accurately and explain the important visible details.'

const defaultPdfPrompt =
  'Summarize this PDF, identify its main points, and cite the relevant pages.'

const defaultStructuredDocumentPrompt =
  'Summarize this document, identify its main points, and cite the relevant sections, tables or lines.'

const defaultSpreadsheetPrompt =
  'Summarize this spreadsheet, identify important metrics, missing values, duplicate rows, trends and anomalies, and cite the relevant sources.'




const quickActions: QuickAction[] = [
  {
    label: 'Verify image',
    prompt:
      'Analyze this image carefully. Describe visible details and identify any signs that may suggest manipulation or AI generation. Do not make unsupported claims.',
    icon: ShieldCheck,
  },
  {
    label: 'Extract text',
    prompt:
      'Transcribe all clearly visible text from this image and preserve its structure.',
    icon: FileText,
  },
  {
    label: 'Analyze PDF',
    prompt:
      'Explain the main stages of securely analyzing a PDF document.',
    icon: FileSearch,
  },
  {
    label: 'Inspect details',
    prompt:
      'Inspect this image carefully and explain the important visible details, objects, text, and relationships.',
    icon: ScanSearch,
  },
  {
    label: 'Image report',
    prompt:
      'Create a structured visual-analysis report for this image. Separate visible facts, reasonable inferences, and uncertainties.',
    icon: Image,
  },
]

function createId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID ===
      'function'
  ) {
    return crypto.randomUUID()
  }

  return `${Date.now()}-${Math.random()
    .toString(16)
    .slice(2)}`
}

function createTitle(
  question: string,
): string {
  if (question.length <= 48) {
    return question
  }

  return `${question.slice(
    0,
    45,
  )}...`
}

const maximumHistoryMessageCharacters =
  6_000

function compactHistoryContent(
  message: ConversationMessage,
): string {
  const rawContent =
    message.content.trim()

  if (
    message.role !== 'assistant' ||
    !rawContent.includes(
      '```authentic-chart',
    )
  ) {
    return rawContent.slice(
      0,
      maximumHistoryMessageCharacters,
    )
  }

  const parsed =
    parseChartResponse(rawContent)

  const visualizationSummary =
    parsed.charts.length > 0
      ? `[Visualizations generated: ${parsed.charts
          .map((chart) => chart.title)
          .join('; ')}]`
      : ''

  return [
    parsed.markdown,
    visualizationSummary,
  ]
    .filter(Boolean)
    .join('\n\n')
    .slice(
      0,
      maximumHistoryMessageCharacters,
    )
}

function toApiHistory(
  messages: ConversationMessage[],
): ChatMessage[] {
  return messages
    .filter(
      (message) =>
        message.content
          .trim()
          .length > 0 &&
        !message.isStreaming,
    )
    .map((message) => ({
      role: message.role,
      content:
        compactHistoryContent(
          message,
        ),
    }))
    .filter(
      (message) =>
        message.content.length > 0,
    )
    .slice(-8)
}

function persistedMessages(
  messages: ConversationMessage[],
): ConversationMessage[] {
  return messages.map(
    (message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
      artifactSourceContent:
        message.artifactSourceContent
        && message.artifactSourceContent.length
          <= 64_000
          ? message.artifactSourceContent
          : undefined,
      artifactSourceRef:
        message.artifactSourceRef,
      model: message.model,
      attachment:
        message.attachment
          ? {
              name:
                message.attachment.name,
              mimeType:
                message.attachment.mimeType,
              kind:
                message.attachment.kind,
            }
          : undefined,

      artifact:
        message.artifact
          ? {
              ...message.artifact,

              artifact:
                message.artifact.artifact
                  ? {
                      ...message
                        .artifact
                        .artifact,
                    }
                  : null,
            }
          : undefined,
    }),
  )
}

function replaceArtifactRecord(
  messages: ConversationMessage[],
  messageId: string,
  artifact: ArtifactRecord,
): ConversationMessage[] {
  return messages.map(
    (message) =>
      message.id === messageId &&
      message.artifact
        ? {
            ...message,
            artifact: {
              ...message.artifact,
              format: artifact.format,
              title: artifact.title,
              filename: artifact.filename,
              status: 'succeeded',
              progressPercent: 100,
              stage: 'Artifact ready',
              artifact,
              error: null,
            },
          }
        : message,
  )
}


function artifactMessageFromRecord(
  artifact: ArtifactRecord,
  stage: string,
  status: ChatArtifactMessage['status'] = 'succeeded',
  progressPercent = 100,
): ChatArtifactMessage {
  return {
    trigger: 'automatic',
    format: artifact.format,
    title: artifact.title,
    filename: artifact.filename,
    status,
    progressPercent,
    stage,
    artifact,
    error: null,
  }
}

function replaceArtifactRecordsById(
  messages: ConversationMessage[],
  artifact: ArtifactRecord,
): ConversationMessage[] {
  return messages.map(
    (message) => {
      const existing =
        message.artifact?.artifact

      if (
        !message.artifact ||
        existing?.artifact_id !==
          artifact.artifact_id
      ) {
        return message
      }

      return {
        ...message,
        artifact: {
          ...message.artifact,
          format: artifact.format,
          title: artifact.title,
          filename: artifact.filename,
          status: 'succeeded',
          progressPercent: 100,
          stage: 'Current artifact updated by a later action',
          artifact,
          error: null,
        },
      }
    },
  )
}

function removeArtifactRecordsById(
  messages: ConversationMessage[],
  artifactId: string,
): ConversationMessage[] {
  return messages.map(
    (message) =>
      message.artifact?.artifact
        ?.artifact_id === artifactId
        ? {
            ...message,
            artifact: undefined,
          }
        : message,
  )
}

function artifactOperationStage(
  type: ReturnType<
    typeof routeArtifactCommand
  >['type'],
): string {
  const stages: Record<string, string> = {
    rename: 'Renaming file…',
    revise: 'Creating a new document version…',
    convert: 'Exporting the current document…',
    duplicate: 'Creating a separate copy…',
    restore: 'Restoring the selected version…',
  }

  return stages[type] || 'Processing artifact action…'
}

function readFileAsDataUrl(
  file: File,
): Promise<string> {
  return new Promise(
    (resolve, reject) => {
      const reader =
        new FileReader()

      reader.onload = () => {
        if (
          typeof reader.result ===
          'string'
        ) {
          resolve(reader.result)
          return
        }

        reject(
          new Error(
            'The image preview could not be created.',
          ),
        )
      }

      reader.onerror = () => {
        reject(
          reader.error ??
            new Error(
              'The image preview could not be read.',
            ),
        )
      }

      reader.readAsDataURL(file)
    },
  )
}

interface CompactAttachmentPreviewProps {
  file: File
  previewUrl: string | null
  status: string
  isWorking: boolean
  onGenerateReport: () => void
  onEditPrompt: () => void
  onDownload: () => void
  onRemove: () => void
}

function formatFileSize(
  sizeBytes: number,
): string {
  if (sizeBytes < 1_024) {
    return `${sizeBytes} B`
  }

  const sizeKilobytes =
    sizeBytes / 1_024

  if (sizeKilobytes < 1_024) {
    return `${sizeKilobytes.toFixed(1)} KB`
  }

  return `${(
    sizeKilobytes / 1_024
  ).toFixed(1)} MB`
}

function CompactAttachmentPreview({
  file,
  previewUrl,
  status,
  isWorking,
  onGenerateReport,
  onEditPrompt,
  onDownload,
  onRemove,
}: CompactAttachmentPreviewProps) {
  const [isMenuOpen, setIsMenuOpen] =
    useState(false)

  const attachmentRef =
    useRef<HTMLDivElement>(null)

  const isImage =
    file.type.startsWith('image/')

  const isSpreadsheet =
    spreadsheetExtensions.has(
      getFileExtension(
        file.name,
      ),
    )

  const AttachmentPreviewIcon =
    isSpreadsheet
      ? FileSpreadsheet
      : FileImage

  useEffect(() => {
    if (!isMenuOpen) {
      return
    }

    const handlePointerDown = (
      event: PointerEvent,
    ) => {
      if (
        attachmentRef.current &&
        event.target instanceof Node &&
        !attachmentRef.current.contains(
          event.target,
        )
      ) {
        setIsMenuOpen(false)
      }
    }

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (event.key === 'Escape') {
        setIsMenuOpen(false)
      }
    }

    document.addEventListener(
      'pointerdown',
      handlePointerDown,
    )

    document.addEventListener(
      'keydown',
      handleKeyDown,
    )

    return () => {
      document.removeEventListener(
        'pointerdown',
        handlePointerDown,
      )

      document.removeEventListener(
        'keydown',
        handleKeyDown,
      )
    }
  }, [isMenuOpen])

  useEffect(() => {
    if (isWorking) {
      setIsMenuOpen(false)
    }
  }, [isWorking])

  const normalizedStatus =
    isWorking
      ? 'Analyzing…'
      : status
          .toLowerCase()
          .includes('ready')
        ? 'Ready'
        : status || 'Ready'

  return (
    <div
      aria-label="Selected attachment"
      className={`compact-attachment-preview ${
        isWorking
          ? 'is-working'
          : ''
      }`}
      ref={attachmentRef}
    >
      <div className="compact-attachment-thumbnail">
        {isImage && previewUrl ? (
          <img
            alt=""
            src={previewUrl}
          />
        ) : (
          <AttachmentPreviewIcon
            size={21}
            strokeWidth={1.7}
          />
        )}
      </div>

      <div className="compact-attachment-information">
        <strong
          className="compact-attachment-name"
          title={file.name}
        >
          {file.name}
        </strong>

        <span className="compact-attachment-meta">
          {formatFileSize(file.size)}

          <span aria-hidden="true">
            ·
          </span>

          <span
            className={
              isWorking
                ? 'attachment-state-working'
                : 'attachment-state-ready'
            }
          >
            {normalizedStatus}
          </span>
        </span>
      </div>

      <div className="compact-attachment-controls">
        <button
          aria-expanded={isMenuOpen}
          aria-haspopup="menu"
          aria-label="Attachment options"
          className="compact-attachment-more"
          disabled={isWorking}
          onClick={() =>
            setIsMenuOpen(
              (current) => !current,
            )
          }
          title="Attachment options"
          type="button"
        >
          <MoreHorizontal
            size={17}
            strokeWidth={1.9}
          />
        </button>

        <button
          aria-label={`Remove ${file.name}`}
          className="compact-attachment-remove"
          disabled={isWorking}
          onClick={onRemove}
          title="Remove attachment"
          type="button"
        >
          <X
            size={16}
            strokeWidth={1.9}
          />
        </button>

        {isMenuOpen && (
          <div
            aria-label="Attachment actions"
            className="compact-attachment-action-menu"
            role="menu"
          >
            <button
              onClick={() => {
                setIsMenuOpen(false)
                onGenerateReport()
              }}
              role="menuitem"
              type="button"
            >
              <ScanSearch
                size={16}
                strokeWidth={1.8}
              />

              <span>
                Generate report
              </span>
            </button>

            <button
              onClick={() => {
                setIsMenuOpen(false)
                onEditPrompt()
              }}
              role="menuitem"
              type="button"
            >
              <Pencil
                size={16}
                strokeWidth={1.8}
              />

              <span>
                Edit prompt
              </span>
            </button>

            <button
              onClick={() => {
                setIsMenuOpen(false)
                onDownload()
              }}
              role="menuitem"
              type="button"
            >
              <Download
                size={16}
                strokeWidth={1.8}
              />

              <span>
                Download
              </span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}


interface PdfContinuationContext {
  pageCount: number
  selectedPages: number[]
}

interface PdfContinuationPlan {
  resolvedPrompt?: string
  error?: string
}

const continuationPdfContextPattern =
  /(?:\r?\n){0,2}<!--AUTHENTIC_DOCUMENT_CONTEXT:([^>]*)-->\s*$/

function isPdfContinuationFile(
  file: File,
): boolean {
  return (
    file.type ===
      'application/pdf' ||
    file.name
      .toLowerCase()
      .endsWith('.pdf')
  )
}

function getLatestPdfContinuationContext(
  conversationMessages:
    ConversationMessage[],
): PdfContinuationContext | null {
  for (
    let index =
      conversationMessages.length - 1;
    index >= 0;
    index -= 1
  ) {
    const message =
      conversationMessages[index]

    if (
      message.role !== 'assistant'
    ) {
      continue
    }

    const match =
      message.content.match(
        continuationPdfContextPattern,
      )

    if (!match) {
      continue
    }

    try {
      const parsed =
        JSON.parse(
          decodeURIComponent(
            match[1],
          ),
        ) as {
          pageCount?: unknown
          selectedPages?: unknown
        }

      if (
        typeof parsed.pageCount !==
          'number' ||
        !Number.isInteger(
          parsed.pageCount,
        ) ||
        parsed.pageCount < 1 ||
        !Array.isArray(
          parsed.selectedPages,
        )
      ) {
        continue
      }

      const selectedPages =
        parsed.selectedPages.filter(
          (
            value,
          ): value is number =>
            typeof value ===
              'number' &&
            Number.isInteger(
              value,
            ) &&
            value >= 1,
        )

      if (
        selectedPages.length === 0
      ) {
        continue
      }

      return {
        pageCount:
          parsed.pageCount,

        selectedPages,
      }
    } catch {
      continue
    }
  }

  return null
}

function getPdfContinuationCount(
  prompt: string,
): number | null {
  const patterns = [
    /\b(?:next|agle|agla|agli|aage\s+ke|aage\s+ka)\s*(\d{1,2})?\s*(pages?|panne|panno?)\b/i,

    /\b(?:continue|aage\s+badho|aage\s+continue)\b[\s\S]{0,40}?\b(\d{1,2})?\s*(pages?|panne|panno?)\b/i,
  ]

  for (const pattern of patterns) {
    const match =
      prompt.match(pattern)

    if (!match) {
      continue
    }

    if (match[1]) {
      return Number(
        match[1],
      )
    }

    const unit =
      match[2]
        ?.toLowerCase() ?? ''

    return unit === 'page'
      ? 1
      : 10
  }

  return null
}

function resolvePdfContinuation(
  prompt: string,
  conversationMessages:
    ConversationMessage[],
): PdfContinuationPlan {
  const requestedCount =
    getPdfContinuationCount(
      prompt,
    )

  if (requestedCount === null) {
    return {}
  }

  if (
    requestedCount < 1 ||
    requestedCount > 16
  ) {
    return {
      error:
        'PDF continuation supports 1 to 16 pages per request.',
    }
  }

  const context =
    getLatestPdfContinuationContext(
      conversationMessages,
    )

  if (!context) {
    return {
      error:
        'No previous PDF page range was found in this conversation. Upload the PDF and request an explicit page range first.',
    }
  }

  const orderedPages = [
    ...new Set(
      context.selectedPages,
    ),
  ].sort(
    (left, right) =>
      left - right,
  )

  const isContiguous =
    orderedPages.every(
      (page, index) =>
        index === 0 ||
        page ===
          orderedPages[0] +
            index,
    )

  if (!isContiguous) {
    return {
      error:
        'The previous PDF response used non-sequential relevant pages. Request an explicit page range before using “next pages”.',
    }
  }

  const previousFinalPage =
    orderedPages[
      orderedPages.length - 1
    ]

  const nextStartPage =
    previousFinalPage + 1

  if (
    nextStartPage >
    context.pageCount
  ) {
    return {
      error:
        'The previous response already reached the final page of this PDF.',
    }
  }

  const nextFinalPage =
    Math.min(
      context.pageCount,
      nextStartPage +
        requestedCount -
        1,
    )

  if (
    nextStartPage ===
    nextFinalPage
  ) {
    return {
      resolvedPrompt:
        `Analyze only Page ${nextStartPage}. Explain that page clearly and use the exact citation [Page ${nextStartPage}]. Respond in the same language as the latest user message below.

Latest user message: ${prompt}`,
    }
  }

  return {
    resolvedPrompt:
      `Analyze only Page ${nextStartPage} through Page ${nextFinalPage}. Explain every page separately in original order and cite each page using its exact page number. Respond in the same language as the latest user message below.

Latest user message: ${prompt}`,
  }
}


interface UploadedArtifactSource {
  prompt: string
  snapshot: ArtifactSourceSnapshot
  sourceReference?: ArtifactSourceReference
}

async function resolveUploadedArtifactSource(
  file: File,
  requestPrompt: string,
  signal: AbortSignal,
): Promise<UploadedArtifactSource> {
  const sourceInstruction = [
    'Analyze this uploaded source accurately for use in a professional document.',
    'Extract the subject, facts, visible details, structure, and supported conclusions.',
    'Do not invent information that is not present in the source.',
  ].join(' ')

  let sourceContent = ''

  if (isImageFile(file)) {
    const result = await analyzeImage(
      file,
      sourceInstruction,
      signal,
    )
    sourceContent = result.answer
  } else if (
    isPdfFile(file)
  ) {
    try {
      const storedSource =
        await createUploadedArtifactSource(
          file,
          signal,
        )

      return {
        prompt: requestPrompt,
        sourceReference:
          storedSource.reference,
        snapshot: {
          kind: 'uploaded_file',
          summary: storedSource.summary,
          message_ids: [],
          attachment_names: [file.name],
          confidence: 1,
        },
      }
    } catch (error) {
      if (
        !(error instanceof ApiError)
        || error.status !== 422
      ) {
        throw error
      }

      // Scanned/image-only PDFs fall back to the existing OCR-aware
      // analyzer. Its compact result is then persisted in the source vault
      // by the caller before the artifact job is created.
      const result = await analyzeDocument(
        file,
        sourceInstruction,
        signal,
      )
      sourceContent = result.answer
    }
  } else if (isSpreadsheetFile(file)) {
    const result = await analyzeSpreadsheet(
      file,
      sourceInstruction,
      signal,
    )
    sourceContent = result.answer
  } else if (
    isStructuredDocumentFile(file)
  ) {
    const result =
      await analyzeStructuredDocument(
        file,
        sourceInstruction,
        signal,
      )
    sourceContent = result.answer
  } else {
    throw new ApiError(
      'The uploaded file cannot be used as an artifact source.',
      422,
    )
  }

  const normalizedContent =
    sourceContent.trim()

  if (!normalizedContent) {
    throw new ApiError(
      'The uploaded file did not produce usable source content.',
      422,
    )
  }

  return {
    prompt: [
      requestPrompt,
      '',
      'Use the uploaded source analysis as the primary factual basis for the artifact.',
      `Uploaded source: ${file.name}`,
    ].join('\n'),
    snapshot: {
      kind: 'uploaded_file',
      summary:
        `${file.name}: ${normalizedContent}`
          .replace(/\s+/g, ' ')
          .slice(0, 500),
      content:
        normalizedContent.slice(0, 16_000),
      message_ids: [],
      attachment_names: [file.name],
      confidence: 0.96,
    },
  }
}


export function Home({
  initialConversation,
  onConversationUpdated,
  onOpenDevelopment,
}: HomeProps) {
  const [prompt, setPrompt] =
    useState('')

  const [
    selectedFile,
    setSelectedFile,
  ] = useState<File | null>(
    null,
  )

  const [
    previewUrl,
    setPreviewUrl,
  ] = useState<string | null>(
    null,
  )

  const [status, setStatus] =
    useState('')

  const [error, setError] =
    useState('')

  const [
    isWorking,
    setIsWorking,
  ] = useState(false)

  const [
    messages,
    setMessages,
  ] = useState<
    ConversationMessage[]
  >(
    () =>
      initialConversation
        ?.messages
        .map((message) => ({
          ...message,
          isStreaming: false,
        })) ?? [],
  )

  const messagesRef =
    useRef<ConversationMessage[]>(
      messages,
    )

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  const conversationIdRef =
    useRef(
      initialConversation?.id ??
        createId(),
    )

  const createdAtRef =
    useRef(
      initialConversation
        ?.createdAt ??
        new Date().toISOString(),
    )

  const titleRef =
    useRef(
      initialConversation?.title ??
        '',
    )

  const requestControllerRef =
    useRef<
      AbortController | null
    >(null)

  const activePdfFileRef =
    useRef<File | null>(
      null,
    )

  const activePdfConversationIdRef =
    useRef<string | null>(
      null,
    )


  const conversationActive =
    messages.length > 0 ||
    isWorking

  useEffect(() => {
    if (
      !selectedFile ||
      !selectedFile.type
        .startsWith('image/')
    ) {
      setPreviewUrl(null)
      return
    }

    const objectUrl =
      URL.createObjectURL(
        selectedFile,
      )

    setPreviewUrl(objectUrl)

    return () => {
      URL.revokeObjectURL(
        objectUrl,
      )
    }
  }, [selectedFile])

  useEffect(() => {
    return () => {
      requestControllerRef
        .current
        ?.abort()
    }
  }, [])

  const handleFileSelected = (
    file: File,
  ) => {
    setError('')
    setStatus('')

    if (!isSupportedUpload(file)) {
      setSelectedFile(null)

      setError(
        'Only images, PDF, DOCX, CSV, XLSX, text, JSON, Markdown and source-code files files are supported.',
      )

      return
    }

    const maximumBytes =
      getMaximumUploadBytes(file)

    if (file.size > maximumBytes) {
      setSelectedFile(null)

      const maximumMegabytes =
        Math.round(
          maximumBytes /
          (1024 * 1024),
        )

      setError(
        `Files of this type must be ${maximumMegabytes} MB or smaller.`,
      )

      return
    }

    if (isPdfContinuationFile(file)) {


      activePdfFileRef.current = file


      activePdfConversationIdRef.current =


        conversationIdRef.current


    } else {


      activePdfFileRef.current = null


      activePdfConversationIdRef.current = null


    }



    setSelectedFile(file)

    if (isImageFile(file)) {
      setStatus(
        'Image ready for Serenya Vision.',
      )
    } else {
      setStatus(
        'Document ready for Serenya Document Intelligence.',
      )
    }
  }

  const handleSubmit =
    async () => {
      const enteredQuestion =
        prompt.trim()

      const recoveredCurrentSource =
        enteredQuestion
          ? await recoverArtifactSourcePrompt(
              enteredQuestion,
            )
          : null

      const authoritativeQuestion =
        recoveredCurrentSource?.content
        ?? enteredQuestion

      const selectedFileSnapshot =
        selectedFile

      // Creation intent must take precedence over artifact mutation.
      // Large source prompts commonly contain words such as "include",
      // "remove", "final filename", and "PDF". Those are document
      // production instructions, not requests to revise a previous artifact.
      let directArtifactCreationIntent =
        authoritativeQuestion
          ? detectChatArtifactIntent(
              authoritativeQuestion,
            )
          : null

      let artifactCommand =
        routeArtifactCommand(
          authoritativeQuestion,
        )

      // A newly uploaded source is not an existing generated artifact.
      // Redesign/edit language for an attachment must create a fresh output
      // file, so let the semantic classifier resolve it instead of sending it
      // into the stored-artifact revision branch.
      if (
        selectedFileSnapshot &&
        artifactCommand.type === 'revise'
      ) {
        artifactCommand = {
          type: 'none',
          raw: authoritativeQuestion,
          confidence: 0,
        }
      }

      if (
        !directArtifactCreationIntent &&
        artifactCommand.type === 'create' &&
        artifactCommand.format
      ) {
        directArtifactCreationIntent =
          createChatArtifactIntent(
            authoritativeQuestion,
            artifactCommand.format,
          )
      }

      if (
        authoritativeQuestion &&
        !directArtifactCreationIntent &&
        artifactCommand.type === 'none'
      ) {
        const dynamicDecision =
          await resolveDynamicArtifactIntent(
            authoritativeQuestion,
            {
              hasAttachment:
                Boolean(selectedFileSnapshot),
              attachmentNames:
                selectedFileSnapshot
                  ? [selectedFileSnapshot.name]
                  : [],
              hasGeneratedArtifact:
                messages.some(
                  (message) =>
                    Boolean(
                      message.artifact
                        ?.artifact,
                    ),
                ),
            },
          )

        const dynamicCreationIntent =
          createChatArtifactIntentFromDecision(
            authoritativeQuestion,
            dynamicDecision,
          )

        if (dynamicCreationIntent) {
          directArtifactCreationIntent =
            dynamicCreationIntent
        } else if (
          dynamicDecision?.action ===
          'revise'
        ) {
          artifactCommand = {
            type: 'revise',
            raw: authoritativeQuestion,
            instruction:
              authoritativeQuestion,
            confidence:
              dynamicDecision.confidence,
          }
        }
      }

      if (
        !directArtifactCreationIntent &&
        artifactCommand.type !== 'none' &&
        artifactCommand.type !== 'create'
      ) {
        if (isWorking) {
          return
        }

        const commandMessages =
          messages.filter(
            (message) =>
              !message.isStreaming,
          )
        const target =
          resolveArtifactReference(
            authoritativeQuestion,
            commandMessages,
          )
        const commandUserMessage:
          ConversationMessage = {
            id: createId(),
            role: 'user',
            content: enteredQuestion,
          }

        if (!target) {
          const missingArtifactMessage:
            ConversationMessage = {
              id: createId(),
              role: 'assistant',
              content:
                'I could not find a completed generated file in this chat. Create a PDF, DOCX, or PPTX first, then ask me to modify it.',
              model:
                'Serenya Artifact Engine',
              isStreaming: false,
            }
          const nextMessages = [
            ...commandMessages,
            commandUserMessage,
            missingArtifactMessage,
          ]

          setMessages(nextMessages)
          setPrompt('')
          onConversationUpdated({
            id: conversationIdRef.current,
            title:
              titleRef.current ||
              createTitle(enteredQuestion),
            createdAt: createdAtRef.current,
            updatedAt:
              new Date().toISOString(),
            messages:
              persistedMessages(nextMessages),
          })
          return
        }

        setError('')
        setPrompt('')
        setIsWorking(true)

        const controller =
          new AbortController()
        requestControllerRef.current =
          controller

        const operationAssistantId =
          createId()
        const showsArtifactProgress =
          new Set([
            'rename',
            'revise',
            'convert',
            'duplicate',
            'restore',
          ]).has(artifactCommand.type)
        const pendingAssistant:
          ConversationMessage = {
            id: operationAssistantId,
            role: 'assistant',
            content:
              showsArtifactProgress
                ? ''
                : artifactCommand.type ===
                    'history'
                  ? 'Loading version history…'
                  : 'Processing artifact action…',
            model:
              'Serenya Artifact Engine',
            isStreaming: false,
            artifact:
              showsArtifactProgress
                ? artifactMessageFromRecord(
                    target.artifact,
                    artifactOperationStage(
                      artifactCommand.type,
                    ),
                    'running',
                    18,
                  )
                : undefined,
          }
        const pendingMessages = [
          ...commandMessages,
          commandUserMessage,
          pendingAssistant,
        ]

        setMessages(pendingMessages)

        try {
          let updatedArtifact:
            ArtifactRecord | null = null
          let duplicate:
            ArtifactRecord | null = null
          let responseContent = ''
          let resultStage = ''
          let deleted = false

          if (
            artifactCommand.type ===
            'rename'
          ) {
            updatedArtifact =
              await renameArtifact(
                target.artifact,
                {
                  filename:
                    artifactCommand.filename ||
                    'Renamed artifact',
                  expected_version:
                    target.artifact.version,
                  idempotency_key:
                    createId(),
                },
                controller.signal,
              )
            responseContent =
              `Renamed successfully to **${updatedArtifact.filename}**. The ready-to-download file is below.`
            resultStage =
              'Renamed successfully · ready to download'
          } else if (
            artifactCommand.type ===
            'revise'
          ) {
            updatedArtifact =
              await reviseArtifact(
                target.artifact,
                {
                  instruction:
                    artifactCommand.instruction ||
                    authoritativeQuestion,
                  expected_version:
                    target.artifact.version,
                  idempotency_key:
                    createId(),
                },
                controller.signal,
              )
            responseContent =
              `Created version ${updatedArtifact.version} with the requested changes. Previous versions remain available in Version history.`
            resultStage =
              `Version ${updatedArtifact.version} created · ready to open or download`
          } else if (
            artifactCommand.type ===
            'convert'
          ) {
            updatedArtifact =
              await exportArtifact(
                target.artifact,
                {
                  format:
                    artifactCommand.format ||
                    target.artifact.format,
                  expected_version:
                    target.artifact.version,
                  idempotency_key:
                    createId(),
                },
                controller.signal,
              )
            responseContent =
              `Exported the current document as ${updatedArtifact.format.toUpperCase()}. The exported file is below.`
            resultStage =
              `${updatedArtifact.format.toUpperCase()} export ready`
          } else if (
            artifactCommand.type ===
            'duplicate'
          ) {
            duplicate =
              await duplicateArtifact(
                target.artifact,
                {
                  expected_version:
                    target.artifact.version,
                  idempotency_key:
                    createId(),
                },
                controller.signal,
              )
            responseContent =
              `Created a separate copy named **${duplicate.filename}**.`
            resultStage =
              'Separate copy ready'
          } else if (
            artifactCommand.type ===
            'delete'
          ) {
            await deleteArtifact(
              target.artifact,
              controller.signal,
            )
            deleted = true
            responseContent =
              'Deleted the generated artifact and all of its stored versions.'
          } else if (
            artifactCommand.type ===
            'restore'
          ) {
            updatedArtifact =
              await restoreArtifact(
                target.artifact,
                {
                  version:
                    artifactCommand.version || 1,
                  expected_version:
                    target.artifact.version,
                  idempotency_key:
                    createId(),
                },
                controller.signal,
              )
            responseContent =
              `Restored version ${updatedArtifact.version}. The restored file is below.`
            resultStage =
              `Version ${updatedArtifact.version} restored · ready to download`
          } else if (
            artifactCommand.type ===
            'history'
          ) {
            const versionResult =
              await listArtifactVersions(
                target.artifact,
                controller.signal,
              )
            responseContent = [
              `This artifact has ${versionResult.versions.length} version${
                versionResult.versions.length === 1
                  ? ''
                  : 's'
              }.`,
              '',
              ...versionResult.versions.map(
                (version) =>
                  `- Version ${version.version}${
                    version.is_current
                      ? ' (current)'
                      : ''
                  }: ${version.format.toUpperCase()}, ${version.page_or_slide_count} page/slide${
                    version.page_or_slide_count === 1
                      ? ''
                      : 's'
                  }`,
              ),
              '',
              'Use the artifact card menu to download or restore a specific version.',
            ].join('\n')
          }

          let baseMessages =
            commandMessages

          if (updatedArtifact) {
            baseMessages =
              replaceArtifactRecordsById(
                baseMessages,
                updatedArtifact,
              )
          } else if (deleted) {
            baseMessages =
              removeArtifactRecordsById(
                baseMessages,
                target.artifact.artifact_id,
              )
          }

          const finalArtifact =
            duplicate || updatedArtifact
          const commandAssistantMessage:
            ConversationMessage = {
              id: operationAssistantId,
              role: 'assistant',
              content: responseContent,
              model:
                'Serenya Artifact Engine',
              isStreaming: false,
              artifact:
                finalArtifact
                  ? artifactMessageFromRecord(
                      finalArtifact,
                      resultStage ||
                        'Artifact ready',
                    )
                  : undefined,
            }
          const nextMessages = [
            ...baseMessages,
            commandUserMessage,
            commandAssistantMessage,
          ]

          messagesRef.current = nextMessages
          setMessages(nextMessages)
          onConversationUpdated({
            id: conversationIdRef.current,
            title:
              titleRef.current ||
              createTitle(enteredQuestion),
            createdAt: createdAtRef.current,
            updatedAt:
              new Date().toISOString(),
            messages:
              persistedMessages(nextMessages),
          })
        } catch (commandError) {
          const failedMessage:
            ConversationMessage = {
              id: operationAssistantId,
              role: 'assistant',
              content:
                commandError instanceof Error
                  ? commandError.message
                  : 'The artifact action could not be completed.',
              model:
                'Serenya Artifact Engine',
              isStreaming: false,
            }
          const nextMessages = [
            ...commandMessages,
            commandUserMessage,
            failedMessage,
          ]
          messagesRef.current = nextMessages
          setMessages(nextMessages)
          onConversationUpdated({
            id: conversationIdRef.current,
            title:
              titleRef.current ||
              createTitle(enteredQuestion),
            createdAt: createdAtRef.current,
            updatedAt:
              new Date().toISOString(),
            messages:
              persistedMessages(nextMessages),
          })
        } finally {
          setIsWorking(false)
          if (
            requestControllerRef.current ===
            controller
          ) {
            requestControllerRef.current =
              null
          }
        }

        return
      }

      const continuationPlan =
        selectedFileSnapshot
          ? {}
          : resolvePdfContinuation(
              authoritativeQuestion,
              messages,
            )

      setError('')

      if (
        continuationPlan.error
      ) {
        setError(
          continuationPlan.error,
        )

        return
      }

      let continuationPdfFile:
        File | null = null

      if (
        continuationPlan
          .resolvedPrompt
      ) {
        const retainedFile =
          activePdfFileRef.current

        const belongsToConversation =
          activePdfConversationIdRef
            .current ===
          conversationIdRef.current

        if (
          !retainedFile ||
          !belongsToConversation
        ) {
          setError(
            'The original PDF is no longer available in browser memory. Re-upload the same PDF, then request the required page range.',
          )

          return
        }

        continuationPdfFile =
          retainedFile
      }

      const fileSnapshot =
        selectedFileSnapshot ??
        continuationPdfFile

      if (
        selectedFileSnapshot &&
        isPdfContinuationFile(
          selectedFileSnapshot,
        )
      ) {
        activePdfFileRef.current =
          selectedFileSnapshot

        activePdfConversationIdRef
          .current =
          conversationIdRef.current
      }


      if (
        !authoritativeQuestion &&
        !fileSnapshot
      ) {
        setError(
          'Type a question or upload an image before sending.',
        )

        return
      }

      if (isWorking) {
        return
      }

      requestControllerRef
        .current
        ?.abort()

      const controller =
        new AbortController()

      requestControllerRef.current =
        controller

      const previousMessages =
        messages.filter(
          (message) =>
            !message.isStreaming,
        )

      let attachment:
        | ConversationAttachment
        | undefined

      if (fileSnapshot) {
        if (isImageFile(fileSnapshot)) {
          try {
            attachment = {
              name:
                fileSnapshot.name,
              mimeType:
                fileSnapshot.type,
              kind: 'image',
              previewUrl:
                await readFileAsDataUrl(
                  fileSnapshot,
                ),
            }
          } catch {
            setError(
              'The selected image preview could not be created.',
            )

            return
          }
        } else if (
          isPdfFile(fileSnapshot)
        ) {
          attachment = {
            name:
              fileSnapshot.name,
            mimeType:
              fileSnapshot.type,
            kind: 'document',
          }
        }
      }

      const baseRequestPrompt =
        fileSnapshot &&
        !authoritativeQuestion
          ? (
              isPdfFile(fileSnapshot)
                ? defaultPdfPrompt
                : isSpreadsheetFile(fileSnapshot)
                  ? defaultSpreadsheetPrompt
                  : isStructuredDocumentFile(fileSnapshot)
                    ? defaultStructuredDocumentPrompt
                    : defaultImagePrompt
            )
          : authoritativeQuestion

      const requestPrompt =
        continuationPlan
          .resolvedPrompt ??
        baseRequestPrompt

      const detectedArtifactIntent =
        requestPrompt === authoritativeQuestion
          ? directArtifactCreationIntent
          : detectChatArtifactIntent(
              requestPrompt,
            )

      const artifactIntent =
        detectedArtifactIntent

      const sourceReadyMessages =
        artifactIntent && !fileSnapshot
          ? await hydrateArtifactSourceMessages(
              previousMessages,
            )
          : previousMessages

      let artifactSource =
        artifactIntent && !fileSnapshot
          ? resolveArtifactSource(
              requestPrompt,
              sourceReadyMessages,
            )
          : null

      // Defense in depth: a substantial source pasted in the
      // current submit is always authoritative. Conversation-reference
      // words inside its narrative must never trigger a clarification.
      if (
        artifactIntent
        && !fileSnapshot
        && artifactSource
          ?.requiresClarification
        && hasSubstantialExplicitArtifactSource(
          authoritativeQuestion,
        )
      ) {
        artifactSource =
          createExplicitArtifactSource(
            authoritativeQuestion,
          )
      }

      if (
        artifactIntent
        && !fileSnapshot
        && artifactSourceHasCompactPreviewGap(
          artifactSource,
          sourceReadyMessages,
        )
      ) {
        const recoverableArtifact =
          resolveArtifactReference(
            'latest generated artifact',
            sourceReadyMessages,
          )

        if (recoverableArtifact) {
          try {
            const recoveredSource =
              await getArtifactSource(
                recoverableArtifact.artifact,
              )

            const recoveryInstruction =
              recoveredSource.recovered_from ===
                'artifact_version'
                ? (
                    'The securely recovered payload is '
                    + 'an already-composed canonical artifact '
                    + 'version. Re-render it idempotently. Do '
                    + 'not send it through raw-source '
                    + 'organisation again, do not duplicate '
                    + 'sections, and preserve its complete '
                    + 'topic, equations, examples, visuals, '
                    + 'title hierarchy, and structure.'
                  )
                : (
                    'Use the securely recovered original '
                    + 'source as the authoritative basis. '
                    + 'Preserve its complete topic, equations, '
                    + 'examples, visuals and structure.'
                  )

            artifactSource = {
              prompt: [
                requestPrompt,
                '',
                recoveryInstruction,
              ].join('\n'),
              snapshot: {
                kind:
                  recoveredSource.recovered_from ===
                    'artifact_version'
                    ? 'artifact_version'
                    : recoveredSource.kind,
                summary:
                  recoveredSource.summary,
                content:
                  recoveredSource.content,
                message_ids:
                  recoveredSource.message_ids,
                attachment_names:
                  recoveredSource.attachment_names,
                confidence:
                  recoveredSource.confidence,
              },
              requiresClarification: false,
            }
          } catch {
            artifactSource = {
              prompt: requestPrompt,
              snapshot: undefined,
              requiresClarification: true,
              clarification: (
                'The complete source is no longer '
                + 'available in this chat preview. '
                + 'Paste or upload the original source, '
                + 'or use a completed artifact card in '
                + 'this conversation so Serenya can '
                + 'recover its stored source.'
              ),
            }
          }
        } else {
          artifactSource = {
            prompt: requestPrompt,
            snapshot: undefined,
            requiresClarification: true,
            clarification: (
              'The complete source is no longer '
              + 'available in this chat preview. '
              + 'Paste or upload the original source '
              + 'again.'
            ),
          }
        }
      }

      if (
        artifactIntent &&
        artifactSource
          ?.requiresClarification
      ) {
        const clarificationUser:
          ConversationMessage = {
            id: createId(),
            role: 'user',
            content:
              enteredQuestion,
          }
        const clarificationAssistant:
          ConversationMessage = {
            id: createId(),
            role: 'assistant',
            content:
              artifactSource.clarification ||
              'What should the document be about?',
            model:
              'Serenya Artifact Engine',
            isStreaming: false,
          }
        const clarificationMessages = [
          ...previousMessages,
          clarificationUser,
          clarificationAssistant,
        ]

        setMessages(
          clarificationMessages,
        )
        setPrompt('')
        onConversationUpdated({
          id:
            conversationIdRef.current,
          title:
            titleRef.current ||
            createTitle(
              authoritativeQuestion,
            ),
          createdAt:
            createdAtRef.current,
          updatedAt:
            new Date().toISOString(),
          messages:
            persistedMessages(
              clarificationMessages,
            ),
        })
        return
      }

      const userMessageId =
        createId()

      const shouldPersistArtifactSource =
        Boolean(
          artifactIntent
          && authoritativeQuestion
          && hasSubstantialExplicitArtifactSource(
            authoritativeQuestion,
          ),
        )

      const artifactSourceRef =
        shouldPersistArtifactSource
          ? (
              recoveredCurrentSource?.sourceId
              ?? `artifact-source:${createId()}`
            )
          : undefined

      if (artifactSourceRef) {
        await storeArtifactSource(
          artifactSourceRef,
          authoritativeQuestion.slice(
            0,
            maximumArtifactSourceCharacters,
          ),
        )
      }

      const displayedQuestion =
        artifactIntent && authoritativeQuestion
          ? createCompactArtifactSourcePreview(
              authoritativeQuestion,
              artifactSourceRef,
            )
          : enteredQuestion ||
            (
              fileSnapshot
                ? `Analyze ${fileSnapshot.name}`
                : requestPrompt
            )

      const userMessage:
        ConversationMessage = {
          id: userMessageId,
          role: 'user',
          content:
            displayedQuestion,
          artifactSourceContent:
            artifactIntent && authoritativeQuestion
              ? authoritativeQuestion.slice(
                  0,
                  maximumArtifactSourceCharacters,
                )
              : undefined,
          artifactSourceRef,
          attachment,
        }

      const assistantId =
        createId()

      const pendingAssistant:
        ConversationMessage = {
          id: assistantId,
          role: 'assistant',

          content: '',

          isStreaming:
            !artifactIntent,

          artifact:
            artifactIntent
              ? {
                  trigger:
                    artifactIntent
                      .trigger,

                  format:
                    artifactIntent
                      .settings
                      .format,

                  title:
                    artifactIntent
                      .settings
                      .title,

                  filename:
                    artifactIntent
                      .settings
                      .filename,

                  status: 'queued',
                  progressPercent: 0,

                  stage:
                    'Preparing document generation',

                  artifact: null,
                  error: null,
                }
              : undefined,
        }

      setMessages([
        ...previousMessages,
        userMessage,
        pendingAssistant,
      ])

      setPrompt('')
      setIsWorking(true)

      if (fileSnapshot) {
        setStatus(
          isPdfFile(fileSnapshot)
            ? 'Serenya is analyzing the PDF...'
            : 'Serenya is analyzing the image...',
        )
      }

      let accumulatedAnswer = ''
      let selectedModel = ''

      let generatedArtifactMessage:
        ChatArtifactMessage | undefined

      try {
        if (artifactIntent) {
          let resolvedSource = artifactSource
          let resolvedSourceReference:
            ArtifactSourceReference | undefined

          if (fileSnapshot) {
            setMessages(
              (current) =>
                current.map(
                  (message) =>
                    message.id === assistantId &&
                    message.artifact
                      ? {
                          ...message,
                          artifact: {
                            ...message.artifact,
                            status: 'running',
                            progressPercent: 5,
                            stage:
                              'Reading uploaded source',
                          },
                        }
                      : message,
                ),
            )

            const uploadedSource =
              await resolveUploadedArtifactSource(
                fileSnapshot,
                requestPrompt,
                controller.signal,
              )
            resolvedSourceReference =
              uploadedSource.sourceReference
            resolvedSource = {
              ...uploadedSource,
              requiresClarification: false,
            }
          }

          let transportSnapshot =
            resolvedSource?.snapshot

          if (
            !resolvedSourceReference
            && transportSnapshot?.content
          ) {
            try {
              const storedSource =
                await createTextArtifactSource(
                  transportSnapshot,
                  controller.signal,
                )

              resolvedSourceReference =
                storedSource.reference

              transportSnapshot = {
                ...transportSnapshot,
                content: undefined,
              }
            } catch {
              // Compatibility fallback: an older backend can still accept
              // the inline snapshot while V20 source storage is unavailable.
            }
          }

          let activeArtifactJob:
            | {
                jobId: string
                accessToken: string
              }
            | undefined

          const artifactResult =
            await runChatArtifactJob(
              buildChatArtifactJobRequest(
                resolvedSource?.prompt ??
                  requestPrompt,
                artifactIntent.settings,
                transportSnapshot,
                resolvedSourceReference,
              ),
              {
                signal:
                  controller.signal,

                onCreated: (job) => {
                  activeArtifactJob = job

                  setMessages(
                    (current) =>
                      current.map(
                        (message) =>
                          message.id === assistantId &&
                          message.artifact
                            ? {
                                ...message,
                                artifact: {
                                  ...message.artifact,
                                  job,
                                },
                              }
                            : message,
                      ),
                  )
                },

                onUpdate: (
                  update,
                ) => {
                  const artifactUpdate:
                    ChatArtifactMessage = {
                      trigger:
                        artifactIntent
                          .trigger,

                      format:
                        update.artifact
                          ?.format ??
                        artifactIntent
                          .settings
                          .format,

                      title:
                        update.artifact
                          ?.title ??
                        artifactIntent
                          .settings
                          .title,

                      filename:
                        update.artifact
                          ?.filename ??
                        artifactIntent
                          .settings
                          .filename,

                      status:
                        update.status,

                      progressPercent:
                        update
                          .progressPercent,

                      stage:
                        update.stage,

                      artifact:
                        update.artifact,

                      error:
                        update.error,

                      job:
                        activeArtifactJob,
                    }

                  generatedArtifactMessage =
                    artifactUpdate

                  setMessages(
                    (current) =>
                      current.map(
                        (message) =>
                          message.id ===
                          assistantId
                            ? {
                                ...message,

                                content:
                                  update.status ===
                                  'failed'
                                    ? (
                                        'I could not create '
                                        + 'the requested file.'
                                      )
                                    : update.status ===
                                      'cancelled'
                                      ? (
                                          'Document generation '
                                          + 'was cancelled.'
                                        )
                                      : '',

                                isStreaming:
                                  false,

                                artifact:
                                  artifactUpdate,
                              }
                            : message,
                      ),
                  )
                },
              },
            )

          generatedArtifactMessage = {
            trigger:
              artifactIntent.trigger,

            format:
              artifactResult.artifact
                ?.format ??
              artifactIntent
                .settings.format,

            title:
              artifactResult.artifact
                ?.title ??
              artifactIntent
                .settings.title,

            filename:
              artifactResult.artifact
                ?.filename ??
              artifactIntent
                .settings.filename,

            status:
              artifactResult.status,

            progressPercent:
              artifactResult
                .progress_percent,

            stage:
              artifactResult.stage,

            artifact:
              artifactResult.artifact,

            error:
              artifactResult.error,

            job:
              activeArtifactJob,
          }

          const artifactSucceeded =
            artifactResult.status ===
              'succeeded'
            && Boolean(
              artifactResult.artifact,
            )

          accumulatedAnswer =
            artifactSucceeded
              ? (
                  `Your ${
                    artifactIntent
                      .settings
                      .format
                      .toUpperCase()
                  } is ready. `
                  + (
                    'You can download '
                    + 'it below.'
                  )
                )
              : (
                  'I could not create '
                  + 'the requested file. '
                  + (
                    'Review the generation '
                    + 'error below and try again.'
                  )
                )

          selectedModel =
            'Serenya Artifact Engine'

        } else if (
          fileSnapshot &&
          isImageFile(fileSnapshot)
        ) {
          const visionResult =
            await analyzeImage(
              fileSnapshot,
              requestPrompt,
              controller.signal,
            )

          accumulatedAnswer =
            visionResult.answer

          selectedModel =
            visionResult.model
        } else if (
          fileSnapshot &&
          isPdfFile(fileSnapshot)
        ) {
          const documentResult =
            await analyzeDocument(
              fileSnapshot,
              requestPrompt,
              controller.signal,
            )

          const documentContext =
            encodeURIComponent(
              JSON.stringify({
                analysisMode:
                  documentResult
                    .analysis_mode,

                pageCount:
                  documentResult
                    .page_count,

                selectedPages:
                  documentResult
                    .selected_pages,

                ocrPages:
                  documentResult
                    .ocr_pages,

                citations:
                  documentResult
                    .citations,

                metadata:
                  documentResult
                    .metadata,
              }),
            )

          accumulatedAnswer =
            `${documentResult.answer}\n\n<!--AUTHENTIC_DOCUMENT_CONTEXT:${documentContext}-->`

          selectedModel =
            documentResult.model
        } else if (
          fileSnapshot &&
          isSpreadsheetFile(
            fileSnapshot,
          )
        ) {
          const spreadsheetResult =
            await analyzeSpreadsheet(
              fileSnapshot,
              requestPrompt,
              controller.signal,
            )

          const spreadsheetContext =
            encodeURIComponent(
              JSON.stringify({
                filename:
                  spreadsheetResult
                    .filename,

                spreadsheetType:
                  spreadsheetResult
                    .spreadsheet_type,

                sheetNames:
                  spreadsheetResult
                    .sheet_names,

                sheetCount:
                  spreadsheetResult
                    .sheet_count,

                rowsScanned:
                  spreadsheetResult
                    .rows_scanned,

                maximumColumnsSeen:
                  spreadsheetResult
                    .maximum_columns_seen,

                formulaCount:
                  spreadsheetResult
                    .formula_count,

                truncated:
                  spreadsheetResult
                    .truncated,

                selectedSources:
                  spreadsheetResult
                    .selected_sources,

                citations:
                  spreadsheetResult
                    .citations,
              }),
            )

          accumulatedAnswer =
            `${spreadsheetResult.answer}\n\n<!--AUTHENTIC_SPREADSHEET_CONTEXT:${spreadsheetContext}-->`

          selectedModel =
            spreadsheetResult.model
        } else if (
          fileSnapshot &&
          isStructuredDocumentFile(
            fileSnapshot,
          )
        ) {
          const structuredResult =
            await analyzeStructuredDocument(
              fileSnapshot,
              requestPrompt,
              controller.signal,
            )

          const structuredContext =
            encodeURIComponent(
              JSON.stringify({
                documentType:
                  structuredResult
                    .document_type,

                filename:
                  structuredResult
                    .filename,

                sourceCount:
                  structuredResult
                    .source_count,

                selectedSources:
                  structuredResult
                    .selected_sources,

                citations:
                  structuredResult
                    .citations,

                metadata:
                  structuredResult
                    .metadata,
              }),
            )

          accumulatedAnswer =
            `${structuredResult.answer}\n\n<!--AUTHENTIC_STRUCTURED_DOCUMENT_CONTEXT:${structuredContext}-->`

          selectedModel =
            structuredResult.model
        } else {
          const streamResult =
            await streamQuestion(
              {
                message:
                  requestPrompt,
                history:
                  toApiHistory(
                    previousMessages,
                  ),
              },
              {
                onToken: (
                  token,
                ) => {
                  accumulatedAnswer +=
                    token

                  setMessages(
                    (current) =>
                      current.map(
                        (message) =>
                          message.id ===
                          assistantId
                            ? {
                                ...message,
                                content:
                                  accumulatedAnswer,
                              }
                            : message,
                      ),
                  )
                },
              },
              controller.signal,
            )

          selectedModel =
            streamResult.model
        }

        if (
          !accumulatedAnswer
            .trim()
        ) {
          throw new ApiError(
            'Serenya returned an empty response.',
            502,
          )
        }

        const finalAssistant:
          ConversationMessage = {
            id: assistantId,
            role: 'assistant',
            content:
              accumulatedAnswer,
            model:
              selectedModel,

            isStreaming: false,

            artifact:
              generatedArtifactMessage,
          }

        const finalMessages = [
          ...previousMessages,
          userMessage,
          finalAssistant,
        ]

        setMessages(
          finalMessages,
        )

        if (!titleRef.current) {
          const titleSource =
            authoritativeQuestion ||
            fileSnapshot?.name ||
            'Image analysis'

          titleRef.current =
            createTitle(
              titleSource,
            )
        }

        onConversationUpdated({
          id:
            conversationIdRef
              .current,
          title:
            titleRef.current,
          createdAt:
            createdAtRef
              .current,
          updatedAt:
            new Date()
              .toISOString(),
          messages:
            persistedMessages(
              finalMessages,
            ),
        })

        if (fileSnapshot) {
          setSelectedFile(null)
          setStatus('')
        }
      } catch (
        requestError
      ) {
        if (
          requestError instanceof
            DOMException &&
          requestError.name ===
            'AbortError'
        ) {
          return
        }

        if (artifactIntent) {
          const artifactError =
            requestError instanceof Error
              ? requestError.message
              : (
                  'The requested file '
                  + 'could not be generated.'
                )

          const failedAssistant:
            ConversationMessage = {
              id: assistantId,
              role: 'assistant',

              content:
                'I could not create '
                + 'the requested file.',

              model:
                'Serenya Artifact Engine',

              isStreaming: false,

              artifact: {
                trigger:
                  artifactIntent.trigger,

                format:
                  artifactIntent
                    .settings.format,

                title:
                  artifactIntent
                    .settings.title,

                filename:
                  artifactIntent
                    .settings.filename,

                status: 'failed',
                progressPercent: 0,
                stage: 'Generation failed',
                artifact: null,
                error: artifactError,
              },
            }

          const failedMessages = [
            ...previousMessages,
            userMessage,
            failedAssistant,
          ]

          setMessages(
            failedMessages,
          )

          if (!titleRef.current) {
            titleRef.current =
              createTitle(
                authoritativeQuestion ||
                  'Generated document',
              )
          }

          onConversationUpdated({
            id:
              conversationIdRef
                .current,

            title:
              titleRef.current,

            createdAt:
              createdAtRef.current,

            updatedAt:
              new Date()
                .toISOString(),

            messages:
              persistedMessages(
                failedMessages,
              ),
          })

          return
        }

        setMessages(
          previousMessages,
        )

        setPrompt(
          authoritativeQuestion,
        )

        if (
          requestError instanceof
          ApiError
        ) {
          setError(
            requestError.message,
          )
        } else {
          setError(
            fileSnapshot
              ? 'Authentic AI could not analyze the uploaded file.'
              : 'Authentic AI could not complete the request.',
          )
        }

        if (fileSnapshot) {
          setStatus(
            'Image remains selected. You can retry the request.',
          )
        }
      } finally {
        setIsWorking(false)

        if (
          requestControllerRef
            .current ===
          controller
        ) {
          requestControllerRef
            .current = null
        }
      }
    }

  const handleRemoveFile =
    () => {
      if (isWorking) {
        return
      }

      setSelectedFile(null)
      setStatus('')
      setError('')
    }

  const handleEditPrompt =
    () => {
      if (!selectedFile) {
        return
      }

      if (isImageFile(selectedFile)) {
        setPrompt(
          `Analyze "${selectedFile.name}" and explain the important visible details: `,
        )

        return
      }

      setPrompt(
        `Analyze "${selectedFile.name}": `,
      )
    }

  const handleDownload =
    () => {
      if (!selectedFile) {
        return
      }

      const downloadUrl =
        URL.createObjectURL(
          selectedFile,
        )

      const link =
        document.createElement(
          'a',
        )

      link.href =
        downloadUrl

      link.download =
        selectedFile.name

      document.body.appendChild(
        link,
      )

      link.click()
      link.remove()

      window.setTimeout(() => {
        URL.revokeObjectURL(
          downloadUrl,
        )
      }, 0)
    }


  const persistArtifactMessages = (
    nextMessages: ConversationMessage[],
    titleSource: string,
  ) => {
    messagesRef.current = nextMessages
    setMessages(nextMessages)

    if (!titleRef.current) {
      titleRef.current =
        createTitle(titleSource)
    }

    onConversationUpdated({
      id: conversationIdRef.current,
      title: titleRef.current,
      createdAt: createdAtRef.current,
      updatedAt:
        new Date().toISOString(),
      messages:
        persistedMessages(nextMessages),
    })
  }

  const handleArtifactCardUpdated = (
    messageId: string,
    updatedArtifact: ArtifactRecord,
  ) => {
    const nextMessages =
      replaceArtifactRecordsById(
        replaceArtifactRecord(
          messagesRef.current,
          messageId,
          updatedArtifact,
        ),
        updatedArtifact,
      )

    persistArtifactMessages(
      nextMessages,
      updatedArtifact.title,
    )
  }

  const handleArtifactCardDeleted = (
    messageId: string,
  ) => {
    const nextMessages =
      messagesRef.current.map(
        (message) =>
          message.id === messageId
            ? {
                ...message,
                artifact: undefined,
              }
            : message,
      )

    persistArtifactMessages(
      nextMessages,
      'Artifact deleted',
    )
  }

  const handleArtifactCardDuplicated = (
    duplicatedArtifact: ArtifactRecord,
  ) => {
    const duplicateMessage:
      ConversationMessage = {
        id: createId(),
        role: 'assistant',
        content:
          'Created a separate copy. You can open, revise, or download it below.',
        model:
          'Serenya Artifact Engine',
        isStreaming: false,
        artifact: {
          trigger: 'automatic',
          format:
            duplicatedArtifact.format,
          title:
            duplicatedArtifact.title,
          filename:
            duplicatedArtifact.filename,
          status: 'succeeded',
          progressPercent: 100,
          stage: 'Artifact ready',
          artifact:
            duplicatedArtifact,
          error: null,
        },
      }

    const nextMessages = [
      ...messagesRef.current,
      duplicateMessage,
    ]

    persistArtifactMessages(
      nextMessages,
      duplicatedArtifact.title,
    )
  }

  const composerAttachment =
    selectedFile ? (
      <CompactAttachmentPreview
        file={selectedFile}
        isWorking={isWorking}
        onDownload={handleDownload}
        onEditPrompt={handleEditPrompt}
        onGenerateReport={handleSubmit}
        onRemove={handleRemoveFile}
        previewUrl={previewUrl}
        status={status}
      />
    ) : null

  if (conversationActive) {
    return (
      <div className="home-page conversation-mode">
        <section className="conversation-layout">
          <ChatTranscript
            messages={messages}
            onArtifactDeleted={
              handleArtifactCardDeleted
            }
            onArtifactDuplicated={
              handleArtifactCardDuplicated
            }
            onArtifactUpdated={
              handleArtifactCardUpdated
            }
          />

          <div className="conversation-composer">
            <PromptBox
              attachment={composerAttachment}
              isWorking={
                isWorking
              }
              onFileSelected={
                handleFileSelected
              }
              onPromptChange={
                setPrompt
              }
              onSherryClick={() =>
                onOpenDevelopment(
                  'sherry',
                )
              }
              onSubmit={
                handleSubmit
              }
              prompt={prompt}
              selectedFile={
                selectedFile
              }
              variant="conversation"
            />


            {error && (
              <div
                className="validation-error conversation-error"
                role="alert"
              >
                {error}
              </div>
            )}

            <p className="conversation-disclaimer">
              Serenya can make mistakes.
              Review important information
              before using it.
            </p>
          </div>
        </section>
      </div>
    )
  }

  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="hero-logo">
          <BrandMark
            size={48}
          />
        </div>

        <h1>
          What would you like
          to verify?
        </h1>

        <p className="hero-subtitle">
          Ask Serenya a question or
          upload an image or document
          for careful analysis.
        </p>

        <div className="interaction-area">
          <PromptBox
            attachment={composerAttachment}
            isWorking={
              isWorking
            }
            onFileSelected={
              handleFileSelected
            }
            onPromptChange={
              setPrompt
            }
            onSherryClick={() =>
              onOpenDevelopment(
                'sherry',
              )
            }
            onSubmit={
              handleSubmit
            }
            prompt={prompt}
            selectedFile={
              selectedFile
            }
          />

          {error && (
            <div
              className="validation-error"
              role="alert"
            >
              {error}
            </div>
          )}


          <div className="quick-actions">
            {quickActions.map(
              (action) => {
                const Icon =
                  action.icon

                return (
                  <button
                    key={
                      action.label
                    }
                    onClick={() =>
                      setPrompt(
                        action.prompt,
                      )
                    }
                    type="button"
                  >
                    <Icon
                      size={17}
                      strokeWidth={
                        1.8
                      }
                    />

                    <span>
                      {
                        action.label
                      }
                    </span>
                  </button>
                )
              },
            )}
          </div>
        </div>
      </section>

      <p className="home-disclaimer">
        This is a private preview.
        AI responses may contain errors
        and should be reviewed before
        important use.
      </p>
    </div>
  )
}
