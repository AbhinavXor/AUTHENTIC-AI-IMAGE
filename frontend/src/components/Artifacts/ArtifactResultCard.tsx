import {
  CalendarClock,
  CheckCircle2,
  Download,
  FileCheck2,
  Hash,
  Trash2,
} from 'lucide-react'
import type {
  ArtifactRecord,
} from '../../types/artifacts'

interface ArtifactResultCardProps {
  artifact: ArtifactRecord
  deleting: boolean
  downloading: boolean
  onDelete: () => void
  onDownload: () => void
}

function formatBytes(
  sizeBytes: number,
): string {
  if (sizeBytes < 1_024) {
    return `${sizeBytes} B`
  }

  if (sizeBytes < 1_024 * 1_024) {
    return `${(
      sizeBytes / 1_024
    ).toFixed(1)} KB`
  }

  return `${(
    sizeBytes /
    (1_024 * 1_024)
  ).toFixed(1)} MB`
}

function formatDateTime(
  value: string,
): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(date)
}

export function ArtifactResultCard({
  artifact,
  deleting,
  downloading,
  onDelete,
  onDownload,
}: ArtifactResultCardProps) {
  return (
    <section
      aria-live="polite"
      className="artifact-result-card"
    >
      <div className="artifact-result-heading">
        <span className="artifact-success-icon">
          <CheckCircle2
            size={23}
            strokeWidth={1.9}
          />
        </span>

        <div>
          <p>Artifact ready</p>

          <h2>{artifact.filename}</h2>
        </div>
      </div>

      <div className="artifact-result-metadata">
        <div>
          <FileCheck2
            size={16}
            strokeWidth={1.8}
          />

          <span>
            {artifact.format.toUpperCase()}
            {' · '}
            {formatBytes(
              artifact.size_bytes,
            )}
          </span>
        </div>

        <div>
          <CalendarClock
            size={16}
            strokeWidth={1.8}
          />

          <span>
            Expires{' '}
            {formatDateTime(
              artifact.expires_at,
            )}
          </span>
        </div>

        <div>
          <Hash
            size={16}
            strokeWidth={1.8}
          />

          <code>
            {artifact.sha256.slice(
              0,
              18,
            )}
            …
          </code>
        </div>
      </div>

      <div className="artifact-result-actions">
        <button
          className="artifact-download-button"
          disabled={
            downloading ||
            deleting
          }
          onClick={onDownload}
          type="button"
        >
          <Download
            size={17}
            strokeWidth={1.9}
          />

          <span>
            {downloading
              ? 'Preparing download…'
              : 'Download file'}
          </span>
        </button>

        <button
          aria-label="Delete generated artifact"
          className="artifact-delete-button"
          disabled={
            deleting ||
            downloading
          }
          onClick={onDelete}
          type="button"
        >
          <Trash2
            size={17}
            strokeWidth={1.8}
          />

          <span>
            {deleting
              ? 'Deleting…'
              : 'Delete'}
          </span>
        </button>
      </div>
    </section>
  )
}