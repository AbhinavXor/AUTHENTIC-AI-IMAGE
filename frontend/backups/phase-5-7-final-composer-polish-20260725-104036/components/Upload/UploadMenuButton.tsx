import {
  FileText,
  FolderOpen,
  ImagePlus,
  Plus,
} from 'lucide-react'
import type {
  ChangeEvent,
  CSSProperties,
} from 'react'
import {
  useEffect,
  useLayoutEffect,
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

const menuWidth = 264
const estimatedMenuHeight = 222
const viewportMargin = 12
const menuGap = 10

export function UploadMenuButton({
  buttonClassName,
  disabled,
  onFileSelected,
  variant,
}: UploadMenuButtonProps) {
  const [isOpen, setIsOpen] =
    useState(false)

  const [menuStyle, setMenuStyle] =
    useState<CSSProperties>({})

  const rootRef =
    useRef<HTMLDivElement>(null)

  const buttonRef =
    useRef<HTMLButtonElement>(null)

  const imageInputRef =
    useRef<HTMLInputElement>(null)

  const documentInputRef =
    useRef<HTMLInputElement>(null)

  const computerInputRef =
    useRef<HTMLInputElement>(null)

  const updateMenuPosition = () => {
    const button =
      buttonRef.current

    if (!button) {
      return
    }

    const rectangle =
      button.getBoundingClientRect()

    const maximumLeft =
      window.innerWidth -
      menuWidth -
      viewportMargin

    const left = Math.max(
      viewportMargin,
      Math.min(
        rectangle.left,
        maximumLeft,
      ),
    )

    const canOpenAbove =
      rectangle.top >
      estimatedMenuHeight +
        menuGap +
        viewportMargin

    const top = canOpenAbove
      ? rectangle.top -
        estimatedMenuHeight -
        menuGap
      : rectangle.bottom +
        menuGap

    setMenuStyle({
      position: 'fixed',
      top,
      left,
      bottom: 'auto',
      width: menuWidth,
    })
  }

  useLayoutEffect(() => {
    if (isOpen) {
      updateMenuPosition()
    }
  }, [isOpen])

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

    const handleViewportChange = () => {
      updateMenuPosition()
    }

    document.addEventListener(
      'pointerdown',
      handlePointerDown,
    )

    document.addEventListener(
      'keydown',
      handleKeyDown,
    )

    window.addEventListener(
      'resize',
      handleViewportChange,
    )

    window.addEventListener(
      'scroll',
      handleViewportChange,
      true,
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

      window.removeEventListener(
        'resize',
        handleViewportChange,
      )

      window.removeEventListener(
        'scroll',
        handleViewportChange,
        true,
      )
    }
  }, [isOpen])

  useEffect(() => {
    if (disabled) {
      setIsOpen(false)
    }
  }, [disabled])

  const handleSelectedFile = (
    event: ChangeEvent<HTMLInputElement>,
  ) => {
    const file =
      event.currentTarget.files?.[0]

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
        ref={buttonRef}
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
          className="attachment-upload-menu attachment-upload-menu-fixed"
          role="menu"
          style={menuStyle}
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
