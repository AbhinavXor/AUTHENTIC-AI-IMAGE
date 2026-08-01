import {
  ActivityOrb,
  type ActivityOrbVariant,
} from './ActivityOrb'

interface ActivityPillProps {
  className?: string
  compact?: boolean
  label: string
  state?: 'active' | 'complete' | 'idle'
  variant?: ActivityOrbVariant
}

export function ActivityPill({
  className = '',
  compact = false,
  label,
  state = 'active',
  variant = 'thinking',
}: ActivityPillProps) {
  return (
    <span
      aria-live="polite"
      className={[
        'natural-activity-pill',
        compact ? 'is-compact' : '',
        `is-${state}`,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      role="status"
    >
      <ActivityOrb
        size={compact ? 18 : 24}
        variant={variant}
      />

      <span>{label}</span>
      <i aria-hidden="true" />
    </span>
  )
}
