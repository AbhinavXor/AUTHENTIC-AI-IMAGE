import {
  FileText,
  FolderOpen,
  ImagePlus,
  Plus,
} from 'lucide-react'
import { createPortal } from 'react-dom'
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

interface MenuPosition {
  top: number
  left: number
  visibility:
    CSSProperties['visibility']
}

const imageAccept =
  'image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp'

const documentAccept = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown',
  'application/json',

  '.pdf',
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
].join(',')

const combinedAccept =
  `${imageAccept},${documentAccept}`

const viewportMargin = 12
const menuGap = 9

export function UploadMenuButton({
  buttonClassName,
  disabled,
  onFileSelected,
  variant,
}: UploadMenuButtonProps) {
  const [isOpen, setIsOpen] =
    useState(false)

  const [
    menuPosition,
    setMenuPosition,
  ] = useState<MenuPosition>({
    top: 0,
    left: 0,
    visibility: 'hidden',
  })

  const rootRef =
    useRef<HTMLDivElement>(null)

  const buttonRef =
    useRef<HTMLButtonElement>(null)

  const menuRef =
    useRef<HTMLDivElement>(null)

  const imageInputRef =
    useRef<HTMLInputElement>(null)

  const documentInputRef =
    useRef<HTMLInputElement>(null)

  const computerInputRef =
    useRef<HTMLInputElement>(null)

  const updatePosition = () => {
    const button =
      buttonRef.current

    const menu =
      menuRef.current

    if (!button || !menu) {
      return
    }

    const buttonRect =
      button.getBoundingClientRect()

    const menuRect =
      menu.getBoundingClientRect()

    const maximumLeft =
      window.innerWidth -
      menuRect.width -
      viewportMargin

    const left = Math.max(
      viewportMargin,
      Math.min(
        buttonRect.left,
        maximumLeft,
      ),
    )

    const availableAbove =
      buttonRect.top -
      viewportMargin

    const shouldOpenAbove =
      availableAbove >=
      menuRect.height +
        menuGap

    const top = shouldOpenAbove
      ? buttonRect.top -
        menuRect.height -
        menuGap
      : buttonRect.bottom +
        menuGap

    setMenuPosition({
      top,
      left,
      visibility: 'visible',
    })
  }

  useLayoutEffect(() => {
    if (!isOpen) {
      return
    }

    const animationFrame =
      window.requestAnimationFrame(
        updatePosition,
      )

    return () => {
      window.cancelAnimationFrame(
        animationFrame,
      )
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) {
      return
    }

    const handlePointerDown = (
      event: PointerEvent,
    ) => {
      const target =
        event.target

      if (!(target instanceof Node)) {
        return
      }

      const clickedButton =
        rootRef.current?.contains(
          target,
        )

      const clickedMenu =
        menuRef.current?.contains(
          target,
        )

      if (
        !clickedButton &&
        !clickedMenu
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

    const handleViewportChange =
      () => {
        updatePosition()
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
    event:
      ChangeEvent<HTMLInputElement>,
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

  const menu = isOpen ? (
    <div
      aria-label="Attachment options"
      className="attachment-upload-menu attachment-upload-menu-portal"
      ref={menuRef}
      role="menu"
      style={{
        position: 'fixed',
        top: menuPosition.top,
        left: menuPosition.left,
        visibility:
          menuPosition.visibility,
      }}
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
            PDF, DOCX, text or code
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
  ) : null

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
        onClick={() => {
          setMenuPosition({
            top: 0,
            left: 0,
            visibility: 'hidden',
          })

          setIsOpen(
            (current) => !current,
          )
        }}
        ref={buttonRef}
        title="Add photos and files"
        type="button"
      >
        <Plus
          size={19}
          strokeWidth={1.9}
        />
      </button>

      {typeof document !==
        'undefined' &&
        menu &&
        createPortal(
          menu,
          document.body,
        )}
    </div>
  )
}
