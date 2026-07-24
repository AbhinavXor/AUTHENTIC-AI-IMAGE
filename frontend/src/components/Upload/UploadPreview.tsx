import {
  Download,
  FileText,
  PencilLine,
  ScanSearch,
  X,
} from 'lucide-react'

interface UploadPreviewProps {
  file: File
  previewUrl: string | null
  status: string
  isWorking: boolean
  onRemove: () => void
  onGenerateReport: () => void
  onEditPrompt: () => void
  onDownload: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function UploadPreview({
  file,
  previewUrl,
  status,
  isWorking,
  onRemove,
  onGenerateReport,
  onEditPrompt,
  onDownload,
}: UploadPreviewProps) {
  const isPdf =
    file.type === 'application/pdf' ||
    file.name.toLowerCase().endsWith('.pdf')

  return (
    <section className="upload-preview">
      <div className="preview-header">
        <div>
          <p>Uploaded file</p>
          <strong>{file.name}</strong>
          <span>{formatFileSize(file.size)}</span>
        </div>

        <button
          aria-label="Remove uploaded file"
          className="remove-file-button"
          onClick={onRemove}
          type="button"
        >
          <X size={18} />
        </button>
      </div>

      <div className="preview-content">
        {isPdf ? (
          <div className="pdf-preview">
            <div className="pdf-icon-container">
              <FileText size={34} strokeWidth={1.5} />
            </div>

            <div>
              <strong>PDF document ready</strong>
              <p>
                OCR and document verification will run through the
                FastAPI backend.
              </p>
            </div>
          </div>
        ) : previewUrl ? (
          <img
            alt={`Preview of ${file.name}`}
            className="uploaded-image-preview"
            src={previewUrl}
          />
        ) : (
          <div className="preview-unavailable">
            Preview is not available for this file.
          </div>
        )}
      </div>

      {status && <div className="frontend-status">{status}</div>}

      <div className="preview-actions">
        <button
          className="primary-preview-action"
          disabled={isWorking}
          onClick={onGenerateReport}
          type="button"
        >
          <ScanSearch size={17} />
          <span>
            {isWorking ? 'Preparing...' : 'Generate report'}
          </span>
        </button>

        <button
          className="secondary-preview-action"
          onClick={onEditPrompt}
          type="button"
        >
          <PencilLine size={17} />
          <span>Edit prompt</span>
        </button>

        <button
          className="secondary-preview-action"
          onClick={onDownload}
          type="button"
        >
          <Download size={17} />
          <span>Download</span>
        </button>
      </div>
    </section>
  )
}
