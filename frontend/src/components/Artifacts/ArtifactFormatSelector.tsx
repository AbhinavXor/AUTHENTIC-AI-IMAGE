import {
  FileText,
  Presentation,
  ScrollText,
  type LucideIcon,
} from 'lucide-react'
import type {
  ArtifactFormat,
} from '../../types/artifacts'

interface ArtifactFormatSelectorProps {
  disabled?: boolean
  value: ArtifactFormat
  onChange: (
    value: ArtifactFormat,
  ) => void
}

interface FormatOption {
  id: ArtifactFormat
  label: string
  description: string
  icon: LucideIcon
}

const formatOptions: FormatOption[] = [
  {
    id: 'pdf',
    label: 'PDF',
    description:
      'Polished, fixed-layout report',
    icon: ScrollText,
  },
  {
    id: 'docx',
    label: 'DOCX',
    description:
      'Editable Microsoft Word file',
    icon: FileText,
  },
  {
    id: 'pptx',
    label: 'PPTX',
    description:
      'Editable presentation deck',
    icon: Presentation,
  },
]

export function ArtifactFormatSelector({
  disabled = false,
  value,
  onChange,
}: ArtifactFormatSelectorProps) {
  return (
    <div
      aria-label="Artifact format"
      className="artifact-format-grid"
      role="radiogroup"
    >
      {formatOptions.map((option) => {
        const Icon = option.icon
        const isSelected =
          option.id === value

        return (
          <button
            aria-checked={isSelected}
            className={`artifact-format-card ${
              isSelected
                ? 'selected'
                : ''
            }`}
            disabled={disabled}
            key={option.id}
            onClick={() =>
              onChange(option.id)
            }
            role="radio"
            type="button"
          >
            <span className="artifact-format-icon">
              <Icon
                size={21}
                strokeWidth={1.8}
              />
            </span>

            <span className="artifact-format-copy">
              <strong>{option.label}</strong>

              <small>
                {option.description}
              </small>
            </span>
          </button>
        )
      })}
    </div>
  )
}
