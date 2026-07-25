import {
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
import { UploadPreview } from '../components/Upload/UploadPreview'
import {
  analyzeImage,
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

const maximumImageFileSize =
  10 * 1024 * 1024

const maximumPdfFileSize =
  20 * 1024 * 1024

const defaultImagePrompt =
  'Describe this image accurately and explain the important visible details.'

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
        'Only PDF, PNG, JPEG and WEBP files are supported.',
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
        'PDF preview ready. PDF analysis will be connected in a later phase.',
      )
    }
  }

  const handleSubmit =
    async () => {
      const enteredQuestion =
        prompt.trim()

      const fileSnapshot =
        selectedFile

      setError('')

      if (
        fileSnapshot?.type ===
        'application/pdf'
      ) {
        setError(
          'PDF analysis is not connected yet. Upload a PNG, JPEG or WEBP image for visual analysis.',
        )

        return
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

      if (
        fileSnapshot &&
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
      }

      const requestPrompt =
        fileSnapshot &&
        !enteredQuestion
          ? defaultImagePrompt
          : enteredQuestion

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
          'Serenya is analyzing the image...',
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
              ? 'Authentic AI could not analyze the image.'
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

  if (conversationActive) {
    return (
      <div className="home-page conversation-mode">
        <section className="conversation-layout">
          <ChatTranscript
            messages={messages}
          />

          <div className="conversation-composer">
            <PromptBox
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

            {selectedFile && (
              <div className="conversation-upload-preview">
                <UploadPreview
                  file={
                    selectedFile
                  }
                  isWorking={
                    isWorking
                  }
                  onDownload={
                    handleDownload
                  }
                  onEditPrompt={
                    handleEditPrompt
                  }
                  onGenerateReport={
                    handleSubmit
                  }
                  onRemove={
                    handleRemoveFile
                  }
                  previewUrl={
                    previewUrl
                  }
                  status={
                    status
                  }
                />
              </div>
            )}

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
          What can I verify
          for you?
        </h1>

        <p className="hero-subtitle">
          Ask a question or upload
          an image. Serenya can
          understand visible objects,
          screenshots, diagrams,
          charts and text.
        </p>

        <div className="interaction-area">
          <PromptBox
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

          {selectedFile && (
            <UploadPreview
              file={
                selectedFile
              }
              isWorking={
                isWorking
              }
              onDownload={
                handleDownload
              }
              onEditPrompt={
                handleEditPrompt
              }
              onGenerateReport={
                handleSubmit
              }
              onRemove={
                handleRemoveFile
              }
              previewUrl={
                previewUrl
              }
              status={
                status
              }
            />
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
