import {
  AlertCircle,
  CheckCircle2,
  Clock3,
  LoaderCircle,
  RefreshCw,
  X,
} from 'lucide-react'
import type {
  ActiveArtifactJob,
} from '../../types/artifact-jobs'

interface ArtifactJobProgressProps {
  job: ActiveArtifactJob
  checking: boolean
  onClear: () => void
  onRefresh: () => void
}

function resolveStatusLabel(
  status: ActiveArtifactJob['status'],
): string {
  const labels = {
    queued: 'Queued',
    running: 'Generating',
    succeeded: 'Completed',
    failed: 'Failed',
  }

  return labels[status]
}

export function ArtifactJobProgress({
  job,
  checking,
  onClear,
  onRefresh,
}: ArtifactJobProgressProps) {
  const isActive =
    job.status === 'queued' ||
    job.status === 'running'

  const isSuccessful =
    job.status === 'succeeded'

  const isFailed =
    job.status === 'failed'

  return (
    <section
      aria-live="polite"
      className={`artifact-job-progress ${
        isSuccessful
          ? 'succeeded'
          : isFailed
            ? 'failed'
            : 'active'
      }`}
    >
      <div className="artifact-job-progress-header">
        <div className="artifact-job-status-heading">
          <span className="artifact-job-status-icon">
            {isSuccessful ? (
              <CheckCircle2
                size={21}
                strokeWidth={1.9}
              />
            ) : isFailed ? (
              <AlertCircle
                size={21}
                strokeWidth={1.9}
              />
            ) : job.status === 'queued' ? (
              <Clock3
                size={21}
                strokeWidth={1.9}
              />
            ) : (
              <LoaderCircle
                className="artifact-job-spinner"
                size={21}
                strokeWidth={1.9}
              />
            )}
          </span>

          <div>
            <p>Background generation</p>

            <h3>
              {resolveStatusLabel(
                job.status,
              )}
            </h3>
          </div>
        </div>

        {!isActive && (
          <button
            aria-label="Clear artifact job status"
            className="artifact-job-clear-button"
            onClick={onClear}
            type="button"
          >
            <X
              size={17}
              strokeWidth={1.9}
            />
          </button>
        )}
      </div>

      <div className="artifact-job-stage">
        <span>{job.stage}</span>

        <strong>
          {job.progressPercent}%
        </strong>
      </div>

      <div
        aria-label={
          `Artifact generation progress: ${
            job.progressPercent
          } percent`
        }
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={
          job.progressPercent
        }
        className="artifact-job-progress-track"
        role="progressbar"
      >
        <span
          style={{
            width:
              `${job.progressPercent}%`,
          }}
        />
      </div>

      {job.error && (
        <p
          className="artifact-job-error"
          role="alert"
        >
          {job.error}
        </p>
      )}

      <div className="artifact-job-progress-footer">
        <code>
          Job {job.jobId.slice(0, 12)}…
        </code>

        <button
          disabled={checking}
          onClick={onRefresh}
          type="button"
        >
          <RefreshCw
            className={
              checking
                ? 'artifact-job-refreshing'
                : undefined
            }
            size={15}
            strokeWidth={1.9}
          />

          <span>
            {checking
              ? 'Checking…'
              : 'Refresh'}
          </span>
        </button>
      </div>
    </section>
  )
}