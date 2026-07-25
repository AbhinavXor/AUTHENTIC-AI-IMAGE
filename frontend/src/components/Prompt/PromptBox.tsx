import { UploadMenuButton } from '../Upload/UploadMenuButton'
import type { ReactNode } from 'react'
import {
  ArrowUp,
  LoaderCircle,
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
  attachment?: ReactNode
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
  attachment,
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
        className={`conversation-prompt-box ${attachment ? 'has-attachment' : ''}`}
        onSubmit={handleSubmit}
      >
        {fileInput}

      {attachment && (
        <div className="composer-attachment-slot">
          {attachment}
        </div>
      )}

        <UploadMenuButton
          buttonClassName="conversation-tool-button"
          disabled={isWorking}
          onFileSelected={onFileSelected}
          variant="conversation"
        />

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
      className={`prompt-box ${attachment ? 'has-attachment' : ''}`}
      onSubmit={handleSubmit}
    >
      {fileInput}

      {attachment && (
        <div className="composer-attachment-slot">
          {attachment}
        </div>
      )}

      <textarea
        aria-label="Prompt"
        className="prompt-textarea"
        onChange={(event) =>
          onPromptChange(event.target.value)
        }
        onKeyDown={handleKeyDown}
        placeholder="Ask Serenya a question or upload a file..."
        ref={textareaRef}
        rows={2}
        value={prompt}
      />

      <div className="prompt-toolbar">
        <div className="prompt-left-actions">
          <UploadMenuButton
            buttonClassName="upload-control"
            disabled={isWorking}
            onFileSelected={onFileSelected}
            variant="home"
          />

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
