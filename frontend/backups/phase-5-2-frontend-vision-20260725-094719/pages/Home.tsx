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
  ApiError,
  streamQuestion,
  type ChatMessage,
} from '../services/api'
import type {
  ConversationMessage,
  ConversationRecord,
} from '../types/chat'
import type { AppPage } from '../types/navigation'

interface HomeProps {
  initialConversation: ConversationRecord | null
  onConversationUpdated: (
    conversation: ConversationRecord,
  ) => void
  onOpenDevelopment: (page: AppPage) => void
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

const maximumFileSize =
  20 * 1024 * 1024

const quickActions: QuickAction[] = [
  {
    label: 'Verify image',
    prompt:
      'Explain how an AI system can determine whether an image is authentic or AI-generated.',
    icon: ShieldCheck,
  },
  {
    label: 'Extract text',
    prompt:
      'Explain how OCR extracts text from images and documents.',
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
      'What visual details can indicate that an image was AI-generated?',
    icon: ScanSearch,
  },
  {
    label: 'Image report',
    prompt:
      'What should a professional image-authenticity report contain?',
    icon: Image,
  },
]

function createId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
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

  return `${question.slice(0, 45)}...`
}

function toApiHistory(
  messages: ConversationMessage[],
): ChatMessage[] {
  return messages
    .filter(
      (message) =>
        message.content.trim().length > 0 &&
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
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    model: message.model,
  }))
}

export function Home({
  initialConversation,
  onConversationUpdated,
  onOpenDevelopment,
}: HomeProps) {
  const [prompt, setPrompt] = useState('')

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null)

  const [previewUrl, setPreviewUrl] =
    useState<string | null>(null)

  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [isWorking, setIsWorking] = useState(false)

  const [messages, setMessages] =
    useState<ConversationMessage[]>(
      () =>
        initialConversation?.messages.map(
          (message) => ({
            ...message,
            isStreaming: false,
          }),
        ) ?? [],
    )

  const conversationIdRef = useRef(
    initialConversation?.id ?? createId(),
  )

  const createdAtRef = useRef(
    initialConversation?.createdAt ??
      new Date().toISOString(),
  )

  const titleRef = useRef(
    initialConversation?.title ?? '',
  )

  const requestControllerRef =
    useRef<AbortController | null>(null)

  const conversationActive =
    messages.length > 0 || isWorking

  useEffect(() => {
    if (
      !selectedFile ||
      !selectedFile.type.startsWith('image/')
    ) {
      setPreviewUrl(null)
      return
    }

    const objectUrl =
      URL.createObjectURL(selectedFile)

    setPreviewUrl(objectUrl)

    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [selectedFile])

  useEffect(() => {
    return () => {
      requestControllerRef.current?.abort()
    }
  }, [])

  const handleFileSelected = (
    file: File,
  ) => {
    setError('')
    setStatus('')

    if (!allowedTypes.has(file.type)) {
      setSelectedFile(null)

      setError(
        'Only PDF, PNG, JPEG and WEBP files are supported.',
      )

      return
    }

    if (file.size > maximumFileSize) {
      setSelectedFile(null)

      setError(
        'Maximum supported file size is 20 MB.',
      )

      return
    }

    setSelectedFile(file)

    setStatus(
      'Preview ready. Image and PDF analysis will be connected in the next phase.',
    )
  }

  const handleSubmit = async () => {
    const question = prompt.trim()

    setError('')

    if (selectedFile) {
      setError(
        'Text chat is connected. Image and PDF analysis will be connected in the next phase.',
      )

      return
    }

    if (!question) {
      setError(
        'Type a question before sending.',
      )

      return
    }

    if (isWorking) {
      return
    }

    requestControllerRef.current?.abort()

    const controller =
      new AbortController()

    requestControllerRef.current =
      controller

    const previousMessages =
      messages.filter(
        (message) => !message.isStreaming,
      )

    const userMessage:
      ConversationMessage = {
        id: createId(),
        role: 'user',
        content: question,
      }

    const assistantId = createId()

    const pendingAssistant:
      ConversationMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        isStreaming: true,
      }

    const pendingMessages = [
      ...previousMessages,
      userMessage,
      pendingAssistant,
    ]

    setMessages(pendingMessages)
    setPrompt('')
    setIsWorking(true)

    let accumulatedAnswer = ''

    try {
      const streamResult =
        await streamQuestion(
          {
            message: question,
            history: toApiHistory(
              previousMessages,
            ),
          },
          {
            onToken: (token) => {
              accumulatedAnswer += token

              setMessages((current) =>
                current.map((message) =>
                  message.id === assistantId
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

      if (!accumulatedAnswer.trim()) {
        throw new ApiError(
          'Serenya returned an empty response.',
          502,
        )
      }

      const finalAssistant:
        ConversationMessage = {
          id: assistantId,
          role: 'assistant',
          content: accumulatedAnswer,
          model: streamResult.model,
          isStreaming: false,
        }

      const finalMessages = [
        ...previousMessages,
        userMessage,
        finalAssistant,
      ]

      setMessages(finalMessages)

      if (!titleRef.current) {
        titleRef.current =
          createTitle(question)
      }

      onConversationUpdated({
        id: conversationIdRef.current,
        title: titleRef.current,
        createdAt: createdAtRef.current,
        updatedAt:
          new Date().toISOString(),
        messages:
          persistedMessages(finalMessages),
      })

    } catch (requestError) {
      if (
        requestError instanceof DOMException &&
        requestError.name === 'AbortError'
      ) {
        return
      }

      setMessages(previousMessages)
      setPrompt(question)

      if (requestError instanceof ApiError) {
        setError(requestError.message)
      } else {
        setError(
          'Authentic AI could not complete the request.',
        )
      }
    } finally {
      setIsWorking(false)

      if (
        requestControllerRef.current ===
        controller
      ) {
        requestControllerRef.current = null
      }
    }
  }

  const handleRemoveFile = () => {
    setSelectedFile(null)
    setStatus('')
    setError('')
  }

  const handleEditPrompt = () => {
    if (!selectedFile) {
      return
    }

    setPrompt(
      `Analyze "${selectedFile.name}" and describe what should be verified: `,
    )
  }

  const handleDownload = () => {
    if (!selectedFile) {
      return
    }

    const downloadUrl =
      URL.createObjectURL(selectedFile)

    const link =
      document.createElement('a')

    link.href = downloadUrl
    link.download = selectedFile.name

    document.body.appendChild(link)
    link.click()
    link.remove()

    window.setTimeout(() => {
      URL.revokeObjectURL(downloadUrl)
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
              isWorking={isWorking}
              onFileSelected={handleFileSelected}
              onPromptChange={setPrompt}
              onSherryClick={() =>
                onOpenDevelopment('sherry')
              }
              onSubmit={handleSubmit}
              prompt={prompt}
              selectedFile={selectedFile}
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
              Serenya can make mistakes. Review important
              information before using it.
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
          <BrandMark size={48} />
        </div>

        <h1>What can I verify for you?</h1>

        <p className="hero-subtitle">
          Ask a question or upload an image or document.
          Text answers are available in this private
          Authentic AI preview.
        </p>

        <div className="interaction-area">
          <PromptBox
            isWorking={isWorking}
            onFileSelected={handleFileSelected}
            onPromptChange={setPrompt}
            onSherryClick={() =>
              onOpenDevelopment('sherry')
            }
            onSubmit={handleSubmit}
            prompt={prompt}
            selectedFile={selectedFile}
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
              file={selectedFile}
              isWorking={isWorking}
              onDownload={handleDownload}
              onEditPrompt={handleEditPrompt}
              onGenerateReport={handleSubmit}
              onRemove={handleRemoveFile}
              previewUrl={previewUrl}
              status={status}
            />
          )}

          <div className="quick-actions">
            {quickActions.map((action) => {
              const Icon = action.icon

              return (
                <button
                  key={action.label}
                  onClick={() =>
                    setPrompt(action.prompt)
                  }
                  type="button"
                >
                  <Icon
                    size={17}
                    strokeWidth={1.8}
                  />

                  <span>{action.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      <p className="home-disclaimer">
        This is a private preview. AI responses may contain
        errors and should be reviewed before important use.
      </p>
    </div>
  )
}
