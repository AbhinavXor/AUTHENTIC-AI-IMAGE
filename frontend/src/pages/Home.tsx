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
import { PromptBox } from '../components/Prompt/PromptBox'
import { UploadPreview } from '../components/Upload/UploadPreview'
import type { AppPage } from '../types/navigation'

interface HomeProps {
  onActivityCreated: (title: string) => void
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

const maximumFileSize = 20 * 1024 * 1024

const quickActions: QuickAction[] = [
  {
    label: 'Verify image',
    prompt:
      'Analyze this image and verify whether it is authentic or AI-generated.',
    icon: ShieldCheck,
  },
  {
    label: 'Extract text',
    prompt:
      'Extract all readable text from this uploaded image or document.',
    icon: FileText,
  },
  {
    label: 'Analyze PDF',
    prompt:
      'Analyze this PDF and identify important evidence, text and anomalies.',
    icon: FileSearch,
  },
  {
    label: 'Inspect details',
    prompt:
      'Inspect this file for visual inconsistencies and suspicious details.',
    icon: ScanSearch,
  },
  {
    label: 'Image report',
    prompt:
      'Create a structured authenticity report for this image.',
    icon: Image,
  },
]

function createActivityTitle(
  prompt: string,
  selectedFile: File | null,
): string {
  const normalizedPrompt = prompt.trim()

  const sourceTitle =
    normalizedPrompt ||
    (selectedFile
      ? `Verify ${selectedFile.name}`
      : 'New verification')

  if (sourceTitle.length <= 42) {
    return sourceTitle
  }

  return `${sourceTitle.slice(0, 39)}...`
}

export function Home({
  onActivityCreated,
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

  const completionTimer = useRef<number | null>(null)

  useEffect(() => {
    if (
      !selectedFile ||
      !selectedFile.type.startsWith('image/')
    ) {
      setPreviewUrl(null)
      return
    }

    const objectUrl = URL.createObjectURL(selectedFile)
    setPreviewUrl(objectUrl)

    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [selectedFile])

  useEffect(() => {
    return () => {
      if (completionTimer.current !== null) {
        window.clearTimeout(completionTimer.current)
      }
    }
  }, [])

  const handleFileSelected = (file: File) => {
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
      setError('Maximum supported file size is 20 MB.')
      return
    }

    setSelectedFile(file)
    setStatus(
      'Preview ready. Add instructions or generate the report.',
    )
  }

  const handleSubmit = () => {
    setError('')

    if (!selectedFile && !prompt.trim()) {
      setError(
        'Add a prompt or upload a supported file first.',
      )
      return
    }

    if (isWorking) {
      return
    }

    const activityTitle = createActivityTitle(
      prompt,
      selectedFile,
    )

    onActivityCreated(activityTitle)

    setIsWorking(true)
    setStatus('Preparing your request...')

    if (completionTimer.current !== null) {
      window.clearTimeout(completionTimer.current)
    }

    completionTimer.current = window.setTimeout(() => {
      setIsWorking(false)
      setStatus(
        'Request accepted. FastAPI verification will be connected in the backend phase.',
      )
    }, 700)
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
      `Analyze "${selectedFile.name}" and describe what should be verified or edited: `,
    )

    setStatus(
      'Edit the instructions in the prompt box, then submit.',
    )
  }

  const handleDownload = () => {
    if (!selectedFile) {
      return
    }

    const downloadUrl = URL.createObjectURL(selectedFile)
    const link = document.createElement('a')

    link.href = downloadUrl
    link.download = selectedFile.name
    document.body.appendChild(link)
    link.click()
    link.remove()

    window.setTimeout(() => {
      URL.revokeObjectURL(downloadUrl)
    }, 0)
  }

  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="hero-logo">
          <BrandMark size={48} />
        </div>

        <h1>What can I verify for you?</h1>

        <p className="hero-subtitle">
          Upload an image or document. Authentic AI will inspect
          its content and prepare a structured authenticity report.
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
            <div className="validation-error" role="alert">
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
                  onClick={() => setPrompt(action.prompt)}
                  type="button"
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span>{action.label}</span>
                </button>
              )
            })}
          </div>
        </div>
      </section>

      <p className="home-disclaimer">
        Authentic AI uses multiple signals for verification and
        may still require human review for high-risk decisions.
      </p>
    </div>
  )
}
