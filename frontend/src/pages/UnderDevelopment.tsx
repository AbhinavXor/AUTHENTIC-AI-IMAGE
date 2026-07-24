import {
  ArrowLeft,
  LockKeyhole,
  Sparkles,
} from 'lucide-react'

interface UnderDevelopmentProps {
  title: string
  onBack: () => void
}

export function UnderDevelopment({
  title,
  onBack,
}: UnderDevelopmentProps) {
  return (
    <div className="under-development-page">
      <section className="development-card">
        <div className="development-icon">
          <LockKeyhole size={30} strokeWidth={1.6} />
        </div>

        <div className="development-status-row">
          <span>
            <Sparkles size={13} />
            Private Preview
          </span>

          <span>Not Publicly Released</span>
        </div>

        <p className="development-label">Authentic AI</p>

        <h1>{title}</h1>

        <h2>Under Development</h2>

        <p className="private-preview-note">
          This private system is currently configured only for
          your use and has not been launched publicly.
        </p>

        <p className="development-supporting-note">
          This capability is still being developed and will become
          available after it is secure, reliable and
          production-ready. The Home verification experience
          remains available while this module is being prepared.
        </p>

        <button onClick={onBack} type="button">
          <ArrowLeft size={17} />
          <span>Return to Home</span>
        </button>
      </section>
    </div>
  )
}
