import {
  Check,
  Copy,
  Sparkles,
} from 'lucide-react'
import { useState } from 'react'

interface AssistantAnswerProps {
  answer: string
  model: string
}

export function AssistantAnswer({
  answer,
  model,
}: AssistantAnswerProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(answer)

      setCopied(true)

      window.setTimeout(() => {
        setCopied(false)
      }, 1_500)
    } catch {
      setCopied(false)
    }
  }

  return (
    <section
      aria-live="polite"
      className="assistant-answer-card"
    >
      <header className="assistant-answer-header">
        <div>
          <span className="assistant-answer-icon">
            <Sparkles size={15} strokeWidth={1.9} />
          </span>

          <div>
            <strong>Serenya</strong>
            <span>Private preview</span>
          </div>
        </div>

        <button
          aria-label="Copy answer"
          className="copy-answer-button"
          onClick={handleCopy}
          type="button"
        >
          {copied ? (
            <Check size={16} />
          ) : (
            <Copy size={16} />
          )}

          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </header>

      <div className="assistant-answer-content">
        {answer}
      </div>

      <footer className="assistant-answer-footer">
        <span>AI-generated response</span>
        <span>{model}</span>
      </footer>
    </section>
  )
}
