import type {
  ReactNode,
} from 'react'
import {
  ArrowUp,
  LoaderCircle,
} from 'lucide-react'
import {
  type ChangeEvent,
  type FormEvent,
  type KeyboardEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import {
  SherryMark,
} from '../Brand/SherryMark'
import {
  UploadMenuButton,
} from '../Upload/UploadMenuButton'

interface PromptBoxProps {
  attachment?: ReactNode
  prompt: string
  selectedFile: File | null
  isWorking: boolean
  variant?:
    | 'landing'
    | 'conversation'
  onPromptChange: (
    value: string,
  ) => void
  onFileSelected: (
    file: File,
  ) => void
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
  const sherryLaunchTimerRef =
    useRef<number | null>(null)
  const submitMotionTimerRef =
    useRef<number | null>(null)
  const [isSherryLaunching, setIsSherryLaunching] =
    useState(false)
  const [isSubmitAnimating, setIsSubmitAnimating] =
    useState(false)

  useLayoutEffect(() => {
    const textarea = textareaRef.current

    if (!textarea) {
      return
    }

    const computedStyle =
      window.getComputedStyle(textarea)
    const minimumHeight =
      Number.parseFloat(
        computedStyle.minHeight,
      ) || (
        variant === 'conversation'
          ? 42
          : 64
      )
    const maximumHeight =
      Number.parseFloat(
        computedStyle.maxHeight,
      ) || (
        variant === 'conversation'
          ? 180
          : 190
      )

    // Measuring from zero avoids a grid feedback loop where the previous
    // stretched height becomes the next scrollHeight. That loop made a
    // one-line conversation prompt look like a large empty panel.
    textarea.style.setProperty(
      'height',
      '0px',
      'important',
    )
    const contentHeight =
      textarea.scrollHeight
    const nextHeight = Math.min(
      maximumHeight,
      Math.max(
        minimumHeight,
        contentHeight,
      ),
    )

    textarea.style.setProperty(
      'height',
      `${nextHeight}px`,
      'important',
    )
    textarea.style.setProperty(
      'overflow-y',
      contentHeight > maximumHeight
        ? 'auto'
        : 'hidden',
      'important',
    )
  }, [prompt, variant])


  useEffect(() => {
    return () => {
      if (sherryLaunchTimerRef.current !== null) {
        window.clearTimeout(sherryLaunchTimerRef.current)
      }

      if (submitMotionTimerRef.current !== null) {
        window.clearTimeout(submitMotionTimerRef.current)
      }
    }
  }, [])

  const handleSherryLaunch = () => {
    if (isWorking || isSherryLaunching) {
      return
    }

    setIsSherryLaunching(true)

    if (sherryLaunchTimerRef.current !== null) {
      window.clearTimeout(sherryLaunchTimerRef.current)
    }

    sherryLaunchTimerRef.current = window.setTimeout(
      () => {
        sherryLaunchTimerRef.current = null
        onSherryClick()
        setIsSherryLaunching(false)
      },
      220,
    )
  }

  const playSubmitMotion = () => {
    setIsSubmitAnimating(true)

    if (submitMotionTimerRef.current !== null) {
      window.clearTimeout(submitMotionTimerRef.current)
    }

    submitMotionTimerRef.current = window.setTimeout(
      () => {
        submitMotionTimerRef.current = null
        setIsSubmitAnimating(false)
      },
      360,
    )
  }

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    if (submitDisabled) {
      return
    }

    playSubmitMotion()
    onSubmit()
  }

  const handleKeyDown = (
    event: KeyboardEvent<
      HTMLTextAreaElement
    >,
  ) => {
    if (
      event.key === 'Enter' &&
      !event.shiftKey
    ) {
      event.preventDefault()

      if (submitDisabled) {
        return
      }

      playSubmitMotion()
      onSubmit()
    }
  }

  const handleFileChange = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file =
      event.target.files?.[0]

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
      accept={
        '.pdf,.png,.jpg,.jpeg,.webp,'
        + '.docx,.txt,.md,.markdown,'
        + '.json,.csv,.xlsx,'
        + '.py,.js,.jsx,.ts,.tsx,'
        + 'application/pdf,'
        + 'image/png,image/jpeg,'
        + 'image/webp'
      }
      className="hidden-file-input"
      onChange={handleFileChange}
      ref={fileInputRef}
      type="file"
    />
  )

  if (variant === 'conversation') {
    return (
      <form
        className={
          [
            'conversation-prompt-box',
            attachment
              ? 'has-attachment'
              : '',
            prompt.trim()
              ? 'has-content'
              : '',
            isWorking
              ? 'is-working'
              : '',
            isSherryLaunching
              ? 'is-sherry-launching'
              : '',
          ]
            .filter(Boolean)
            .join(' ')
        }
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
            onPromptChange(
              event.target.value,
            )
          }
          onKeyDown={handleKeyDown}
          placeholder="Ask Serenya anything, or paste content to analyse, organise, or turn into a file…"
          ref={textareaRef}
          rows={1}
          value={prompt}
        />

        <button
          aria-label="Talk to Sherry"
          aria-pressed={isSherryLaunching}
          className={[
            'conversation-sherry-button',
            isSherryLaunching
              ? 'is-launching'
              : '',
          ]
            .filter(Boolean)
            .join(' ')}
          disabled={isWorking || isSherryLaunching}
          onClick={handleSherryLaunch}
          title="Talk to Sherry"
          type="button"
        >
          <SherryMark size={29} />
        </button>

        {isSherryLaunching && (
          <div
            aria-live="polite"
            className="sherry-launch-dock"
            role="status"
          >
            <span
              aria-hidden="true"
              className="inline-progress-dots"
            >
              <i />
              <i />
              <i />
            </span>

            <span>Opening Sherry…</span>
          </div>
        )}

        <button
          aria-label={
            isWorking
              ? 'Generating response'
              : 'Send message'
          }
          className={[
            'conversation-send-button',
            isSubmitAnimating
              ? 'is-submit-animating'
              : '',
          ]
            .filter(Boolean)
            .join(' ')}
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
      className={
        [
          'prompt-box',
          attachment
            ? 'has-attachment'
            : '',
          prompt.trim()
            ? 'has-content'
            : '',
          isWorking
            ? 'is-working'
            : '',
          isSherryLaunching
            ? 'is-sherry-launching'
            : '',
        ]
          .filter(Boolean)
          .join(' ')
      }
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
          onPromptChange(
            event.target.value,
          )
        }
        onKeyDown={handleKeyDown}
        placeholder={
          'Ask Serenya a question '
          + 'or upload a file...'
        }
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
            aria-pressed={isSherryLaunching}
            className={[
              'sherry-control',
              isSherryLaunching
                ? 'is-launching'
                : '',
            ]
              .filter(Boolean)
              .join(' ')}
            disabled={isWorking || isSherryLaunching}
            onClick={handleSherryLaunch}
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
          className={[
            'send-button',
            isSubmitAnimating
              ? 'is-submit-animating'
              : '',
          ]
            .filter(Boolean)
            .join(' ')}
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
