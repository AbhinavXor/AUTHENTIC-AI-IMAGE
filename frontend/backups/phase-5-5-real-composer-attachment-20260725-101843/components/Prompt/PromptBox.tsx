import {
  ArrowUp,
  FileUp,
  LoaderCircle,
  Sparkles,
} from 'lucide-react'
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useRef,
} from 'react'
import { SherryMark } from '../Brand/SherryMark'

interface PromptBoxProps {
  prompt: string
  selectedFile: File | null
  isWorking: boolean
  variant?: 'landing' | 'conversation'
  onPromptChange: (value: string) => void
  onFileSelected: (file: File) => void
  onSubmit: () => void
  onSherryClick: () => void
}

export function PromptBox({
  prompt,
  selectedFile,
  isWorking,
  variant = 'landing',
  onPromptChange,
  onFileSelected,
  onSubmit,
  onSherryClick,
}: PromptBoxProps) {
  const fileInputRef =
    useRef<HTMLInputElement>(null)

  const textareaRef =
    useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current

    if (!textarea) {
      return
    }

    textarea.style.height = 'auto'

    const maximumHeight =
      variant === 'conversation'
        ? 160
        : 190

    textarea.style.height =
      `${Math.min(
        textarea.scrollHeight,
        maximumHeight,
      )}px`
  }, [prompt, variant])

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()
    onSubmit()
  }

  const handleKeyDown = (
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (
      event.key === 'Enter' &&
      !event.shiftKey
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
    isWorking ||
    (!prompt.trim() && !selectedFile)

  const fileInput = (
    <input
      accept=".pdf,.png,.jpg,.jpeg,.webp,application/pdf,image/png,image/jpeg,image/webp"
      className="hidden-file-input"
      onChange={handleFileChange}
      ref={fileInputRef}
      type="file"
    />
  )

  if (variant === 'conversation') {
    return (
      <form
        className="conversation-prompt-box"
        onSubmit={handleSubmit}
      >
        {fileInput}

        <button
          aria-label="Upload image or PDF"
          className="conversation-tool-button"
          onClick={() =>
            fileInputRef.current?.click()
          }
          title="Upload file"
          type="button"
        >
          <FileUp
            size={19}
            strokeWidth={1.8}
          />
        </button>

        <textarea
          aria-label="Message Serenya"
          className="conversation-prompt-textarea"
          onChange={(event) =>
            onPromptChange(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder="Message Serenya..."
          ref={textareaRef}
          rows={1}
          value={prompt}
        />

        <button
          aria-label="Talk to Sherry"
          className="conversation-sherry-button"
          onClick={onSherryClick}
          title="Talk to Sherry"
          type="button"
        >
          <SherryMark size={29} />
        </button>

        <button
          aria-label={
            isWorking
              ? 'Generating response'
              : 'Send message'
          }
          className="conversation-send-button"
          disabled={submitDisabled}
          type="submit"
        >
          {isWorking ? (
            <LoaderCircle
              className="composer-spinner"
              size={18}
              strokeWidth={2}
            />
          ) : (
            <ArrowUp
              size={19}
              strokeWidth={2}
            />
          )}
        </button>
      </form>
    )
  }

  return (
    <form
      className="prompt-box"
      onSubmit={handleSubmit}
    >
      {fileInput}

      <textarea
        aria-label="Prompt"
        className="prompt-textarea"
        onChange={(event) =>
          onPromptChange(event.target.value)
        }
        onKeyDown={handleKeyDown}
        placeholder="Ask Authentic AI to verify an image or document..."
        ref={textareaRef}
        rows={2}
        value={prompt}
      />

      <div className="prompt-toolbar">
        <div className="prompt-left-actions">
          <button
            aria-label="Upload image or PDF"
            className="upload-control"
            onClick={() =>
              fileInputRef.current?.click()
            }
            title="Upload PDF, PNG, JPEG or WEBP"
            type="button"
          >
            <FileUp
              size={19}
              strokeWidth={1.8}
            />
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
          {isWorking ? (
            <LoaderCircle
              className="composer-spinner"
              size={18}
            />
          ) : (
            <ArrowUp
              size={19}
              strokeWidth={2}
            />
          )}
        </button>
      </div>
    </form>
  )
}
