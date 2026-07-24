interface BrandMarkProps {
  size?: number
  className?: string
}

export function BrandMark({
  size = 28,
  className = '',
}: BrandMarkProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="none"
      height={size}
      viewBox="0 0 32 32"
      width={size}
    >
      <path
        d="M16 4V15.4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3.2"
      />
      <path
        d="M16 15.4L6.5 22"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3.2"
      />
      <path
        d="M16 15.4L25.5 22"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="3.2"
      />
      <circle cx="16" cy="4" fill="currentColor" r="2" />
      <circle cx="6.5" cy="22" fill="currentColor" r="2" />
      <circle cx="25.5" cy="22" fill="currentColor" r="2" />
    </svg>
  )
}
