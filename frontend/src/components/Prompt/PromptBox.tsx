import {
  ArrowUp,
  FileUp,
  Sparkles,
} from 'lucide-react'
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useRef,
} from 'react'
import { SherryMark } from '../Brand/SherryMark'

interface PromptBoxProps {
  prompt: string
  selectedFile: File | null
  isWorking: boolean
  onPromptChange: (value: string) => void
  onFileSelected: (file: File) => void
  onSubmit: () => void
  onSherryClick: () => void
}

export function PromptBox({
  prompt,
  selectedFile,
  isWorking,
  onPromptChange,
  onFileSelected,
  onSubmit,
  onSherryClick,
}: PromptBoxProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  const handleKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (
      event.key === 'Enter' &&
      (event.metaKey || event.ctrlKey)
    ) {
      event.preventDefault()
      onSubmit()
    }
  }

  const handleFileChange = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0]

    if (file) {
      onFileSelected(file)
    }

    event.target.value = ''
  }

  const submitDisabled =
    isWorking || (!prompt.trim() && !selectedFile)

  return (
    <form className="prompt-box" onSubmit={handleSubmit}>
      <textarea
        aria-label="Prompt"
        className="prompt-textarea"
        onChange={(event) =>
          onPromptChange(event.target.value)
        }
        onKeyDown={handleKeyDown}
        placeholder="Ask Authentic AI to verify an image or document..."
        rows={3}
        value={prompt}
      />

      <div className="prompt-toolbar">
        <div className="prompt-left-actions">
          <input
            accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
            className="hidden-file-input"
            onChange={handleFileChange}
            ref={fileInputRef}
            type="file"
          />

          <button
            aria-label="Upload image or PDF"
            className="upload-control"
            onClick={() => fileInputRef.current?.click()}
            title="Upload PDF, PNG, JPEG or WEBP"
            type="button"
          >
            <FileUp size={19} strokeWidth={1.8} />
          </button>

          <button
            className="sherry-control"
            onClick={onSherryClick}
            type="button"
          >
            <SherryMark
              className="sherry-mark-compact"
              size={24}
            />

            <span>Talk to Sherry</span>
          </button>

          {selectedFile && (
            <span className="attached-indicator">
              <Sparkles size={14} />
              File attached
            </span>
          )}
        </div>

        <button
          aria-label="Submit prompt"
          className="send-button"
          disabled={submitDisabled}
          type="submit"
        >
          <ArrowUp size={19} strokeWidth={2} />
        </button>
      </div>
    </form>
  )
}
