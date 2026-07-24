interface SherryMarkProps {
  size?: number
  className?: string
}

export function SherryMark({
  size = 32,
  className = '',
}: SherryMarkProps) {
  return (
    <span
      aria-hidden="true"
      className={`sherry-mark ${className}`}
      style={{
        width: size,
        height: size,
      }}
    >
      <svg
        fill="none"
        viewBox="0 0 36 36"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M9.5 17V19"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="2.4"
        />

        <path
          d="M13.8 13.5V22.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="2.4"
        />

        <path
          d="M18 9.5V26.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="2.4"
        />

        <path
          d="M22.2 12.5V23.5"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="2.4"
        />

        <path
          d="M26.5 16V20"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="2.4"
        />
      </svg>
    </span>
  )
}
