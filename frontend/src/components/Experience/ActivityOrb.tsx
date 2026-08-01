import type {
  CSSProperties,
} from 'react'

export type ActivityOrbVariant =
  | 'document'
  | 'voice'
  | 'thinking'
  | 'search'
  | 'visual'
  | 'success'

interface ActivityOrbProps {
  className?: string
  size?: number
  variant?: ActivityOrbVariant
}

interface OrbDot {
  delay: number
  opacity: number
  scale: number
  x: number
  y: number
}

const orbDots: OrbDot[] = Array.from(
  { length: 36 },
  (_, index) => {
    const ring = Math.floor(index / 12)
    const point = index % 12
    const angle = (
      point * 30
      + ring * 11
    ) * (Math.PI / 180)
    const radii = [24, 36, 47]
    const radius = radii[ring]
    const verticalScale = [0.64, 0.8, 0.96][ring]

    return {
      delay: -(index * 61),
      opacity: 0.32 + ring * 0.2,
      scale: 0.72 + ring * 0.16,
      x: 50 + Math.cos(angle) * radius,
      y: 50 + Math.sin(angle) * radius * verticalScale,
    }
  },
)

export function ActivityOrb({
  className = '',
  size = 46,
  variant = 'document',
}: ActivityOrbProps) {
  return (
    <span
      aria-hidden="true"
      className={[
        'activity-orb',
        `activity-orb-${variant}`,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        height: size,
        width: size,
      }}
    >
      <span className="activity-orb-halo" />
      <span className="activity-orb-sweep" />
      <span className="activity-orb-core" />

      {orbDots.map((dot, index) => (
        <span
          className="activity-orb-dot"
          key={index}
          style={
            {
              '--orb-delay': `${dot.delay}ms`,
              '--orb-opacity': dot.opacity,
              '--orb-scale': dot.scale,
              left: `${dot.x}%`,
              top: `${dot.y}%`,
            } as CSSProperties
          }
        />
      ))}
    </span>
  )
}
