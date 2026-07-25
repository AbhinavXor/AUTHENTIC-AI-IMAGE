import {
  FileText,
  FolderOpen,
  ImagePlus,
  Plus,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
} from 'react'

interface UploadMenuButtonProps {
  buttonClassName: string
  disabled: boolean
  onFileSelected: (file: File) => void
  variant:
    | 'home'
    | 'conversation'
}

const imageAccept =
  'image/png,image/jpeg,image/webp'

const documentAccept =
  'application/pdf,.pdf'

const combinedAccept =
  `${imageAccept},${documentAccept}`

export function UploadMenuButton({
  buttonClassName,
  disabled,
  onFileSelected,
  variant,
}: UploadMenuButtonProps) {
  const [isOpen, setIsOpen] =
    useState(false)

  const rootRef =
    useRef<HTMLDivElement>(null)

  const imageInputRef =
    useRef<HTMLInputElement>(null)

  const documentInputRef =
    useRef<HTMLInputElement>(null)

  const computerInputRef =
    useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const handlePointerDown = (
      event: PointerEvent,
    ) => {
      if (
        rootRef.current &&
        event.target instanceof Node &&
        !rootRef.current.contains(
          event.target,
        )
      ) {
        setIsOpen(false)
      }
    }

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
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
  }, [isOpen])

  useEffect(() => {
    if (disabled) {
      setIsOpen(false)
    }
  }, [disabled])

  const handleSelectedFile = (
    event:
      React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file =
      event.currentTarget.files?.[0]

    /*
     * Reset the native input so the same file may
     * be selected again after it is removed.
     */
    event.currentTarget.value = ''

    if (!file) {
      return
    }

    setIsOpen(false)
    onFileSelected(file)
  }

  return (
    <div
      className={`attachment-picker attachment-picker-${variant}`}
      ref={rootRef}
    >
      <input
        accept={imageAccept}
        className="attachment-native-input"
        onChange={handleSelectedFile}
        ref={imageInputRef}
        type="file"
      />

      <input
        accept={documentAccept}
        className="attachment-native-input"
        onChange={handleSelectedFile}
        ref={documentInputRef}
        type="file"
      />

      <input
        accept={combinedAccept}
        className="attachment-native-input"
        onChange={handleSelectedFile}
        ref={computerInputRef}
        type="file"
      />

      <button
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-label="Add photos and files"
        className={buttonClassName}
        disabled={disabled}
        onClick={() =>
          setIsOpen(
            (current) => !current,
          )
        }
        title="Add photos and files"
        type="button"
      >
        <Plus
          size={19}
          strokeWidth={1.9}
        />
      </button>

      {isOpen && (
        <div
          aria-label="Attachment options"
          className="attachment-upload-menu"
          role="menu"
        >
          <button
            onClick={() =>
              imageInputRef.current?.click()
            }
            role="menuitem"
            type="button"
          >
            <span className="attachment-menu-icon">
              <ImagePlus
                size={18}
                strokeWidth={1.75}
              />
            </span>

            <span className="attachment-menu-copy">
              <strong>
                Upload image
              </strong>

              <small>
                PNG, JPEG or WEBP
              </small>
            </span>
          </button>

          <button
            onClick={() =>
              documentInputRef.current?.click()
            }
            role="menuitem"
            type="button"
          >
            <span className="attachment-menu-icon">
              <FileText
                size={18}
                strokeWidth={1.75}
              />
            </span>

            <span className="attachment-menu-copy">
              <strong>
                Upload document
              </strong>

              <small>
                PDF document
              </small>
            </span>
          </button>

          <div className="attachment-menu-separator" />

          <button
            onClick={() =>
              computerInputRef.current?.click()
            }
            role="menuitem"
            type="button"
          >
            <span className="attachment-menu-icon">
              <FolderOpen
                size={18}
                strokeWidth={1.75}
              />
            </span>

            <span className="attachment-menu-copy">
              <strong>
                Choose from computer
              </strong>

              <small>
                Browse supported files
              </small>
            </span>
          </button>
        </div>
      )}
    </div>
  )
}
