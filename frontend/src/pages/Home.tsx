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
import type {
  ConversationAttachment,
  ConversationMessage,
  ConversationRecord,
} from '../types/chat'
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

const allowedTypes = new Set([
  'application/pdf',
  'image/png',
  'image/jpeg',
  'image/webp',
])

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



const maximumImageFileSize =
  10 * 1024 * 1024

const maximumPdfFileSize =
  20 * 1024 * 1024

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
      content: message.content,
    }))
    .slice(-12)
}

function persistedMessages(
  messages: ConversationMessage[],
): ConversationMessage[] {
  return messages.map(
    (message) => ({
      id: message.id,
      role: message.role,
      content: message.content,
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
    }),
  )
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

    if (
      !allowedTypes.has(
        file.type,
      )
    ) {
      setSelectedFile(null)

      setError(
        'Only images, PDF, DOCX, CSV, XLSX, text, JSON, Markdown and source-code files files are supported.',
      )

      return
    }

    if (
      imageTypes.has(
        file.type,
      ) &&
      file.size >
        maximumImageFileSize
    ) {
      setSelectedFile(null)

      setError(
        'Images must be 10 MB or smaller.',
      )

      return
    }

    if (
      file.type ===
        'application/pdf' &&
      file.size >
        maximumPdfFileSize
    ) {
      setSelectedFile(null)

      setError(
        'PDF files must be 20 MB or smaller.',
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

    if (
      imageTypes.has(
        file.type,
      )
    ) {
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

      const selectedFileSnapshot =
        selectedFile

      const continuationPlan =
        selectedFileSnapshot
          ? {}
          : resolvePdfContinuation(
              enteredQuestion,
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
        !enteredQuestion &&
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
        if (
          imageTypes.has(
            fileSnapshot.type,
          )
        ) {
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
          fileSnapshot.type ===
          'application/pdf'
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
        !enteredQuestion
          ? (
              fileSnapshot.type ===
              'application/pdf'
                ? defaultPdfPrompt
                : defaultImagePrompt
            )
          : enteredQuestion

      const requestPrompt =
        continuationPlan
          .resolvedPrompt ??
        baseRequestPrompt

      const displayedQuestion =
        enteredQuestion ||
        (
          fileSnapshot
            ? `Analyze ${fileSnapshot.name}`
            : requestPrompt
        )

      const userMessage:
        ConversationMessage = {
          id: createId(),
          role: 'user',
          content:
            displayedQuestion,
          attachment,
        }

      const assistantId =
        createId()

      const pendingAssistant:
        ConversationMessage = {
          id: assistantId,
          role: 'assistant',
          content: '',
          isStreaming: true,
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
          fileSnapshot.type ===
            'application/pdf'
            ? 'Serenya is analyzing the PDF...'
            : 'Serenya is analyzing the image...',
        )
      }

      let accumulatedAnswer = ''
      let selectedModel = ''

      try {
        if (
          fileSnapshot &&
          imageTypes.has(
            fileSnapshot.type,
          )
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
          fileSnapshot?.type ===
          'application/pdf'
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
            enteredQuestion ||
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

        setMessages(
          previousMessages,
        )

        setPrompt(
          enteredQuestion,
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

      if (
        imageTypes.has(
          selectedFile.type,
        )
      ) {
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
