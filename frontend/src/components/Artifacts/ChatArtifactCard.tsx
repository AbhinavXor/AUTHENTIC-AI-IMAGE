import {
  Activity,
  AlertCircle,
  Archive,
  CheckCircle2,
  Copy,
  Download,
  ExternalLink,
  FileText,
  History,
  LoaderCircle,
  MoreHorizontal,
  Pencil,
  Presentation,
  RefreshCw,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
} from 'react'

import {
  deleteArtifact,
  downloadArtifact,
  downloadArtifactVersion,
  duplicateArtifact,
  exportArtifact,
  listArtifactAuditEvents,
  listArtifactVersions,
  openArtifact,
  renameArtifact,
  restoreArtifact,
  reviseArtifact,
} from '../../services/artifacts'
import {
  cancelArtifactJob,
} from '../../services/artifact-jobs'
import type {
  ArtifactAuditEvent,
  ArtifactFormat,
  ArtifactRecord,
  ArtifactVersionRecord,
} from '../../types/artifacts'
import type {
  ChatArtifactMessage,
} from '../../types/chat-artifacts'

interface ArtifactStagePresentation {
  detail: string
  label: string
  phaseIndex: number
}

const artifactPhases = [
  'Understand',
  'Organise',
  'Render',
  'Compose',
  'Verify',
]

function artifactStagePresentation(
  artifact: ChatArtifactMessage,
): ArtifactStagePresentation {
  const stage = artifact.stage.trim()
  const normalized = stage.toLowerCase()
  const progressPhase = Math.min(
    artifactPhases.length - 1,
    Math.max(
      0,
      Math.floor(artifact.progressPercent / 20),
    ),
  )

  if (
    normalized.includes('queue')
    || normalized.includes('waiting')
  ) {
    return {
      detail: 'Waiting for the document worker to begin.',
      label: stage || 'Preparing document',
      phaseIndex: 0,
    }
  }

  if (
    normalized.includes('source')
    || normalized.includes('understand')
    || normalized.includes('read')
  ) {
    return {
      detail: 'Reading the supplied source and preserving its structure.',
      label: stage || 'Understanding source',
      phaseIndex: 0,
    }
  }

  if (
    normalized.includes('organ')
    || normalized.includes('outline')
    || normalized.includes('section')
  ) {
    return {
      detail: 'Building headings, sections, tables, and document flow.',
      label: stage || 'Organising sections',
      phaseIndex: 1,
    }
  }

  if (
    normalized.includes('render')
    || normalized.includes('equation')
    || normalized.includes('chart')
    || normalized.includes('visual')
    || normalized.includes('diagram')
  ) {
    return {
      detail: 'Rendering equations, charts, diagrams, and visual assets.',
      label: stage || 'Rendering visuals',
      phaseIndex: 2,
    }
  }

  if (
    normalized.includes('compose')
    || normalized.includes('page')
    || normalized.includes('pdf')
    || normalized.includes('export')
    || normalized.includes('build')
  ) {
    return {
      detail: 'Composing pages and preparing the final downloadable file.',
      label: stage || 'Building document',
      phaseIndex: 3,
    }
  }

  if (
    normalized.includes('valid')
    || normalized.includes('quality')
    || normalized.includes('check')
    || normalized.includes('final')
  ) {
    return {
      detail: 'Checking structure, page integrity, and download readiness.',
      label: stage || 'Final quality check',
      phaseIndex: 4,
    }
  }

  return {
    detail: 'Processing the document with verified job progress.',
    label: stage || 'Creating your document',
    phaseIndex: progressPhase,
  }
}



interface ChatArtifactCardProps {
  messageId: string
  artifact: ChatArtifactMessage
  onArtifactDeleted: (
    messageId: string,
  ) => void
  onArtifactDuplicated: (
    artifact: ArtifactRecord,
  ) => void
  onArtifactUpdated: (
    messageId: string,
    artifact: ArtifactRecord,
  ) => void
}

type ArtifactPanel =
  | 'rename'
  | 'revise'
  | 'versions'
  | 'activity'
  | 'delete'
  | null

function createIdempotencyKey(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }

  return `artifact-${Date.now()}-${Math.random()
    .toString(16)
    .slice(2)}`
}

function formatFileSize(
  sizeBytes: number,
): string {
  if (sizeBytes < 1_024) {
    return `${sizeBytes} B`
  }

  const kilobytes = sizeBytes / 1_024
  if (kilobytes < 1_024) {
    return `${kilobytes.toFixed(1)} KB`
  }

  return `${(kilobytes / 1_024).toFixed(1)} MB`
}

function formatDateTime(
  value: string,
): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  )
}

function formatExpiry(
  value: string,
): string {
  return `Available until ${formatDateTime(value)}`
}

function formatLabel(
  format: ChatArtifactMessage['format'],
): string {
  if (format === 'zip') {
    return 'PDF BUNDLE'
  }

  return format.toUpperCase()
}

function statusDescription(
  artifact: ChatArtifactMessage,
): string {
  if (artifact.status === 'queued') {
    return artifact.stage || 'Waiting to start'
  }

  if (artifact.status === 'running') {
    return artifact.stage || 'Creating your document'
  }

  if (artifact.status === 'failed') {
    return artifact.error || 'The file could not be generated.'
  }

  if (artifact.status === 'cancelled') {
    return 'Document generation was cancelled.'
  }

  if (
    artifact.stage &&
    artifact.stage !== 'Artifact ready'
  ) {
    return artifact.stage
  }

  return 'Ready to open, download, or revise'
}

function qualityLabel(
  record: ArtifactRecord,
): string {
  if (
    record.validation.status ===
    'passed_with_warnings'
  ) {
    return 'Checked with warnings'
  }

  if (record.validation.status === 'failed') {
    return 'Quality check failed'
  }

  return 'Quality checked'
}

function activityLabel(
  event: ArtifactAuditEvent,
): string {
  const labels: Record<string, string> = {
    created: 'Artifact created',
    renamed: 'File renamed',
    revised: 'Content revised',
    exported: 'Format exported',
    restored: 'Version restored',
  }

  return labels[event.action] || event.action
}

function LoadingIcon() {
  return (
    <LoaderCircle
      className="chat-artifact-spinner"
      size={16}
      strokeWidth={1.9}
    />
  )
}

export function ChatArtifactCard({
  messageId,
  artifact,
  onArtifactDeleted,
  onArtifactDuplicated,
  onArtifactUpdated,
}: ChatArtifactCardProps) {
  const [menuOpen, setMenuOpen] =
    useState(false)
  const [activePanel, setActivePanel] =
    useState<ArtifactPanel>(null)
  const [activeAction, setActiveAction] =
    useState<string | null>(null)
  const [renameValue, setRenameValue] =
    useState('')
  const [revisionValue, setRevisionValue] =
    useState('')
  const [versions, setVersions] =
    useState<ArtifactVersionRecord[]>([])
  const [activity, setActivity] =
    useState<ArtifactAuditEvent[]>([])
  const [actionError, setActionError] =
    useState('')
  const [isResultRevealing, setIsResultRevealing] =
    useState(false)
  const previousStatusRef =
    useRef(artifact.status)
  const menuRef = useRef<HTMLDivElement>(null)

  const format = formatLabel(artifact.format)
  const isPending =
    artifact.status === 'queued' ||
    artifact.status === 'running'
  const record = artifact.artifact
  const isReady =
    artifact.status === 'succeeded' &&
    Boolean(record)
  const FileIcon =
    artifact.format === 'pptx'
      ? Presentation
      : artifact.format === 'zip'
        ? Archive
        : FileText

  useEffect(() => {
    const previousStatus = previousStatusRef.current

    if (
      previousStatus !== 'succeeded'
      && artifact.status === 'succeeded'
    ) {
      setIsResultRevealing(true)
      const timeoutId = window.setTimeout(
        () => setIsResultRevealing(false),
        900,
      )

      previousStatusRef.current = artifact.status
      return () => window.clearTimeout(timeoutId)
    }

    previousStatusRef.current = artifact.status
    return undefined
  }, [artifact.status])

  useEffect(() => {
    if (!menuOpen) {
      return
    }

    const handlePointerDown = (
      event: MouseEvent,
    ) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(
          event.target as Node,
        )
      ) {
        setMenuOpen(false)
      }
    }

    document.addEventListener(
      'mousedown',
      handlePointerDown,
    )

    return () => {
      document.removeEventListener(
        'mousedown',
        handlePointerDown,
      )
    }
  }, [menuOpen])

  const runAction = async <T,>(
    action: string,
    operation: () => Promise<T>,
  ): Promise<T | null> => {
    if (activeAction) {
      return null
    }

    setActionError('')
    setActiveAction(action)

    try {
      return await operation()
    } catch (error) {
      setActionError(
        error instanceof Error
          ? error.message
          : 'The artifact action could not be completed.',
      )
      return null
    } finally {
      setActiveAction(null)
    }
  }

  const handleCancel = async () => {
    if (!artifact.job) {
      return
    }

    await runAction(
      'cancel',
      () => cancelArtifactJob(
        artifact.job!.jobId,
        artifact.job!.accessToken,
      ),
    )
  }

  const handleDownload = async () => {
    if (!record) {
      return
    }

    await runAction(
      'download',
      () => downloadArtifact(record),
    )
  }

  const handleOpen = async () => {
    if (!record) {
      return
    }

    await runAction(
      'open',
      () => openArtifact(record),
    )
  }

  const handleRename = async () => {
    if (!record || !renameValue.trim()) {
      return
    }

    const updated = await runAction(
      'rename',
      () => renameArtifact(
        record,
        {
          filename: renameValue.trim(),
          expected_version: record.version,
          idempotency_key:
            createIdempotencyKey(),
        },
      ),
    )

    if (updated) {
      onArtifactUpdated(messageId, updated)
      setRenameValue('')
      setActivePanel(null)
    }
  }

  const handleRevision = async () => {
    if (!record || !revisionValue.trim()) {
      return
    }

    const updated = await runAction(
      'revise',
      () => reviseArtifact(
        record,
        {
          instruction: revisionValue.trim(),
          expected_version: record.version,
          idempotency_key:
            createIdempotencyKey(),
        },
      ),
    )

    if (updated) {
      onArtifactUpdated(messageId, updated)
      setRevisionValue('')
      setActivePanel(null)
    }
  }

  const handleExport = async (
    targetFormat: ArtifactFormat,
  ) => {
    if (!record) {
      return
    }

    const updated = await runAction(
      `export-${targetFormat}`,
      () => exportArtifact(
        record,
        {
          format: targetFormat,
          expected_version: record.version,
          idempotency_key:
            createIdempotencyKey(),
        },
      ),
    )

    if (updated) {
      onArtifactUpdated(messageId, updated)
      setMenuOpen(false)
    }
  }

  const handleDuplicate = async () => {
    if (!record) {
      return
    }

    const duplicate = await runAction(
      'duplicate',
      () => duplicateArtifact(
        record,
        {
          expected_version: record.version,
          idempotency_key:
            createIdempotencyKey(),
        },
      ),
    )

    if (duplicate) {
      onArtifactDuplicated(duplicate)
      setMenuOpen(false)
    }
  }

  const handleLoadVersions = async () => {
    if (!record) {
      return
    }

    setActivePanel('versions')
    setMenuOpen(false)
    const result = await runAction(
      'versions',
      () => listArtifactVersions(record),
    )

    if (result) {
      setVersions(result.versions)
    }
  }

  const handleLoadActivity = async () => {
    if (!record) {
      return
    }

    setActivePanel('activity')
    setMenuOpen(false)
    const result = await runAction(
      'activity',
      () => listArtifactAuditEvents(record),
    )

    if (result) {
      setActivity(
        [...result.events].reverse(),
      )
    }
  }

  const handleRestore = async (
    version: number,
  ) => {
    if (!record) {
      return
    }

    const updated = await runAction(
      'restore',
      () => restoreArtifact(
        record,
        {
          version,
          expected_version: record.version,
          idempotency_key:
            createIdempotencyKey(),
        },
      ),
    )

    if (updated) {
      onArtifactUpdated(messageId, updated)
      setActivePanel(null)
      setVersions([])
    }
  }

  const handleVersionDownload = async (
    version: ArtifactVersionRecord,
  ) => {
    if (!record) {
      return
    }

    await runAction(
      `version-download-${version.version}`,
      () => downloadArtifactVersion(
        record,
        version.version,
        version.download_url,
        version.filename,
      ),
    )
  }

  const handleDelete = async () => {
    if (!record) {
      return
    }

    const result = await runAction(
      'delete',
      () => deleteArtifact(record),
    )

    if (result?.deleted) {
      onArtifactDeleted(messageId)
    }
  }

  if (isPending) {
    const stagePresentation =
      artifactStagePresentation(artifact)

    return (
      <section
        aria-label={`${format} generation progress`}
        aria-live="polite"
        className="chat-artifact-card status-running artifact-generation-card"
        data-phase={stagePresentation.phaseIndex}
      >
        <div className="artifact-generation-header">
          <span className="artifact-generation-file-icon">
            <FileIcon size={20} strokeWidth={1.8} />
          </span>

          <div className="artifact-generation-copy">
            <div className="artifact-generation-eyebrow">
              <span>{format}</span>
              <small>Creating document</small>
            </div>

            <strong>{stagePresentation.label}</strong>
            <p>{stagePresentation.detail}</p>
          </div>

          <span className="artifact-generation-percent">
            {artifact.progressPercent}%
          </span>
        </div>

        <div className="artifact-generation-phases">
          {artifactPhases.map((phase, index) => {
            const isComplete =
              index < stagePresentation.phaseIndex
            const isActive =
              index === stagePresentation.phaseIndex

            return (
              <span
                className={[
                  isComplete ? 'is-complete' : '',
                  isActive ? 'is-active' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
                key={phase}
              >
                <span
                  aria-hidden="true"
                  className="artifact-phase-marker"
                />
                <span>{phase}</span>
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="artifact-stage-dots"
                  >
                    <i />
                    <i />
                    <i />
                  </span>
                )}
              </span>
            )
          })}
        </div>

        <div className="artifact-generation-footer">
          <div className="chat-artifact-progress-track">
            <span
              style={{
                width: `${Math.max(
                  4,
                  Math.min(
                    100,
                    artifact.progressPercent,
                  ),
                )}%`,
              }}
            />
          </div>

          {artifact.job && (
            <button
              className="chat-artifact-cancel"
              disabled={activeAction === 'cancel'}
              onClick={handleCancel}
              type="button"
            >
              {activeAction === 'cancel' ? (
                <LoadingIcon />
              ) : (
                <Square size={13} />
              )}
              Cancel
            </button>
          )}
        </div>
      </section>
    )
  }

  return (
    <section
      aria-label={`${format} artifact`}
      className={
        [
          'chat-artifact-card',
          `status-${artifact.status}`,
          isResultRevealing
            ? 'is-result-revealing'
            : '',
        ]
          .filter(Boolean)
          .join(' ')
      }
    >
      <div className="chat-artifact-card-main">
        <span className="chat-artifact-card-icon">
          {isPending ? (
            <LoaderCircle
              className="chat-artifact-spinner"
              size={22}
              strokeWidth={1.9}
            />
          ) : (
            <FileIcon
              size={22}
              strokeWidth={1.75}
            />
          )}
        </span>

        <div className="chat-artifact-card-copy">
          <div className="chat-artifact-card-heading">
            <span>{format}</span>
            {record && (
              <small>
                Version {record.version}
              </small>
            )}
          </div>

          <strong>
            {record?.title ||
              artifact.title ||
              artifact.filename ||
              `${format} document`}
          </strong>

          <p>{statusDescription(artifact)}</p>
        </div>

        {artifact.status === 'succeeded' && (
          <CheckCircle2
            className="chat-artifact-success-icon"
            size={21}
            strokeWidth={1.9}
          />
        )}

        {(
          artifact.status === 'failed' ||
          artifact.status === 'cancelled'
        ) && (
          <AlertCircle
            className="chat-artifact-failure-icon"
            size={21}
            strokeWidth={1.9}
          />
        )}

        {isReady && record && (
          <div
            className="chat-artifact-more-wrap"
            ref={menuRef}
          >
            <button
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              aria-label="Artifact actions"
              className="chat-artifact-more-button"
              onClick={() =>
                setMenuOpen(
                  (current) => !current,
                )
              }
              type="button"
            >
              <MoreHorizontal
                size={18}
                strokeWidth={1.9}
              />
            </button>

            {menuOpen && (
              <div
                className="chat-artifact-action-menu"
                role="menu"
              >
                <button
                  onClick={() => {
                    setRenameValue(record.filename)
                    setActivePanel('rename')
                    setMenuOpen(false)
                  }}
                  role="menuitem"
                  type="button"
                >
                  <Pencil size={15} />
                  Rename
                </button>

                <button
                  onClick={() => {
                    setActivePanel('revise')
                    setMenuOpen(false)
                  }}
                  role="menuitem"
                  type="button"
                >
                  <RefreshCw size={15} />
                  Edit content
                </button>

                <button
                  onClick={handleLoadVersions}
                  role="menuitem"
                  type="button"
                >
                  <History size={15} />
                  Version history
                </button>

                <button
                  onClick={handleLoadActivity}
                  role="menuitem"
                  type="button"
                >
                  <Activity size={15} />
                  Activity
                </button>

                <div className="chat-artifact-menu-label">
                  Export
                </div>

                {(['pdf', 'docx', 'pptx'] as const)
                  .filter(
                    (targetFormat) =>
                      targetFormat !== record.format,
                  )
                  .map((targetFormat) => (
                    <button
                      key={targetFormat}
                      onClick={() =>
                        handleExport(targetFormat)
                      }
                      role="menuitem"
                      type="button"
                    >
                      <FileText size={15} />
                      Export as{' '}
                      {targetFormat.toUpperCase()}
                    </button>
                  ))}

                <button
                  onClick={handleDuplicate}
                  role="menuitem"
                  type="button"
                >
                  <Copy size={15} />
                  Duplicate
                </button>

                <button
                  className="destructive"
                  onClick={() => {
                    setActivePanel('delete')
                    setMenuOpen(false)
                  }}
                  role="menuitem"
                  type="button"
                >
                  <Trash2 size={15} />
                  Delete
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {isReady && record && (
        <div className="chat-artifact-ready">
          <div className="chat-artifact-file-details">
            <strong>{record.filename}</strong>
            <span>
              {formatFileSize(record.size_bytes)}
              {' · '}Version {record.version} of{' '}
              {record.version_count}
              {record.page_or_slide_count > 0
                ? ` · ${record.page_or_slide_count} ${
                    record.format === 'pptx'
                      ? 'slides'
                      : record.format === 'zip'
                        ? 'pages across volumes'
                        : 'pages'
                  }`
                : ''}
            </span>
            <span>
              {qualityLabel(record)}
              {' · '}
              {formatExpiry(record.expires_at)}
            </span>
          </div>

          <div className="chat-artifact-primary-actions">
            {record.format === 'pdf' && (
              <button
                className="chat-artifact-open"
                disabled={Boolean(activeAction)}
                onClick={handleOpen}
                type="button"
              >
                {activeAction === 'open' ? (
                  <LoadingIcon />
                ) : (
                  <ExternalLink
                    size={17}
                    strokeWidth={1.9}
                  />
                )}
                <span>Open</span>
              </button>
            )}

            <button
              className={[
                'chat-artifact-download',
                activeAction === 'download'
                  ? 'is-downloading'
                  : '',
                isResultRevealing
                  ? 'is-newly-ready'
                  : '',
              ]
                .filter(Boolean)
                .join(' ')}
              disabled={Boolean(activeAction)}
              onClick={handleDownload}
              type="button"
            >
              {activeAction === 'download' ? (
                <LoadingIcon />
              ) : (
                <Download
                  size={17}
                  strokeWidth={1.9}
                />
              )}
              <span>
                {activeAction === 'download'
                  ? 'Downloading…'
                  : `Download ${format}`}
              </span>
            </button>
          </div>
        </div>
      )}

      {activePanel === 'rename' && record && (
        <div className="chat-artifact-inline-panel">
          <div className="chat-artifact-panel-header">
            <strong>Rename file</strong>
            <button
              aria-label="Close rename panel"
              onClick={() => setActivePanel(null)}
              type="button"
            >
              <X size={16} />
            </button>
          </div>

          <input
            autoFocus
            maxLength={180}
            onChange={(event) =>
              setRenameValue(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                void handleRename()
              }
            }}
            value={renameValue}
          />

          <button
            disabled={
              activeAction === 'rename' ||
              !renameValue.trim()
            }
            onClick={handleRename}
            type="button"
          >
            {activeAction === 'rename' && (
              <LoadingIcon />
            )}
            Save name
          </button>
        </div>
      )}

      {activePanel === 'revise' && record && (
        <div className="chat-artifact-inline-panel">
          <div className="chat-artifact-panel-header">
            <strong>Edit document</strong>
            <button
              aria-label="Close edit panel"
              onClick={() => setActivePanel(null)}
              type="button"
            >
              <X size={16} />
            </button>
          </div>

          <textarea
            autoFocus
            maxLength={8_000}
            onChange={(event) =>
              setRevisionValue(event.target.value)
            }
            placeholder="Describe the changes, for example: shorten the executive summary and add a comparison table."
            rows={3}
            value={revisionValue}
          />

          <button
            disabled={
              activeAction === 'revise' ||
              !revisionValue.trim()
            }
            onClick={handleRevision}
            type="button"
          >
            {activeAction === 'revise' && (
              <LoadingIcon />
            )}
            Create new version
          </button>
        </div>
      )}

      {activePanel === 'versions' && record && (
        <div className="chat-artifact-inline-panel">
          <div className="chat-artifact-panel-header">
            <strong>Version history</strong>
            <button
              aria-label="Close version history"
              onClick={() => setActivePanel(null)}
              type="button"
            >
              <X size={16} />
            </button>
          </div>

          {activeAction === 'versions' ? (
            <div className="chat-artifact-panel-loading">
              <LoadingIcon />
              Loading versions…
            </div>
          ) : (
            <div className="chat-artifact-version-list">
              {versions.map((version) => (
                <div key={version.version}>
                  <div>
                    <strong>
                      Version {version.version}
                    </strong>
                    <span>
                      {version.format.toUpperCase()}
                      {' · '}
                      {formatFileSize(version.size_bytes)}
                      {version.page_or_slide_count > 0
                        ? ` · ${version.page_or_slide_count}`
                        : ''}
                    </span>
                  </div>

                  <div className="chat-artifact-version-actions">
                    <button
                      disabled={Boolean(activeAction)}
                      onClick={() =>
                        handleVersionDownload(version)
                      }
                      type="button"
                    >
                      {activeAction ===
                      `version-download-${version.version}` ? (
                        <LoadingIcon />
                      ) : (
                        <Download size={14} />
                      )}
                      Download
                    </button>

                    {version.is_current ? (
                      <small>Current</small>
                    ) : (
                      <button
                        disabled={Boolean(activeAction)}
                        onClick={() =>
                          handleRestore(version.version)
                        }
                        type="button"
                      >
                        Restore
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activePanel === 'activity' && record && (
        <div className="chat-artifact-inline-panel">
          <div className="chat-artifact-panel-header">
            <strong>Artifact activity</strong>
            <button
              aria-label="Close artifact activity"
              onClick={() => setActivePanel(null)}
              type="button"
            >
              <X size={16} />
            </button>
          </div>

          {activeAction === 'activity' ? (
            <div className="chat-artifact-panel-loading">
              <LoadingIcon />
              Loading activity…
            </div>
          ) : (
            <div className="chat-artifact-activity-list">
              {activity.map((event, index) => (
                <div
                  key={`${event.timestamp}:${event.action}:${index}`}
                >
                  <strong>{activityLabel(event)}</strong>
                  <span>
                    {formatDateTime(event.timestamp)}
                  </span>
                </div>
              ))}
              {activity.length === 0 && (
                <p>No activity is available.</p>
              )}
            </div>
          )}
        </div>
      )}

      {activePanel === 'delete' && record && (
        <div className="chat-artifact-inline-panel destructive-panel">
          <div className="chat-artifact-panel-header">
            <strong>Delete this artifact?</strong>
            <button
              aria-label="Close delete confirmation"
              onClick={() => setActivePanel(null)}
              type="button"
            >
              <X size={16} />
            </button>
          </div>

          <p>
            This removes the file and every stored
            version. This action cannot be undone.
          </p>

          <button
            disabled={activeAction === 'delete'}
            onClick={handleDelete}
            type="button"
          >
            {activeAction === 'delete' && (
              <LoadingIcon />
            )}
            Delete permanently
          </button>
        </div>
      )}

      {actionError && (
        <p
          className="chat-artifact-download-error"
          role="alert"
        >
          {actionError}
        </p>
      )}
    </section>
  )
}
