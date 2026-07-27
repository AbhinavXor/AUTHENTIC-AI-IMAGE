import {
  AlertCircle,
  FileOutput,
  LoaderCircle,
  PenLine,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import {
  ArtifactFormatSelector,
} from '../components/Artifacts/ArtifactFormatSelector'
import {
  ArtifactResultCard,
} from '../components/Artifacts/ArtifactResultCard'
import {
  ArtifactPromptComposer,
} from '../components/Artifacts/ArtifactPromptComposer'
import {
  ArtifactJobProgress,
} from '../components/Artifacts/ArtifactJobProgress'
import {
  ArtifactApiError,
  deleteArtifact,
  downloadArtifact,
  generateArtifact,
} from '../services/artifacts'
import {
  createArtifactJob,
  deleteArtifactJob,
  getArtifactJobStatus,
} from '../services/artifact-jobs'
import type {
  ArtifactFormat,
  ArtifactRecord,
} from '../types/artifacts'
import type {
  ArtifactLength,
  ArtifactTone,
} from '../types/artifact-composer'
import type {
  ActiveArtifactJob,
  ArtifactJobStatusResponse,
} from '../types/artifact-jobs'

const maximumContentCharacters =
  500_000

const historyStorageKey =
  'authentic-ai.artifact-studio.history.v1'

const activeJobStorageKey =
  'authentic-ai.artifact-studio.active-job.v1'

type ArtifactCreationMode =
  | 'ai'
  | 'manual'

const initialContent = `# Authentic AI Report

## Executive Summary

Describe the purpose, main findings, and recommended action.

## Key Findings

- Add the first important finding.
- Add the second important finding.
- Add the third important finding.

## Evidence Table

| Area | Finding | Status |
|---|---|---|
| Product | Add evidence here | Ready |
| Operations | Add evidence here | Review |

## Recommendations

1. Add the highest-priority recommendation.
2. Add the next practical action.
`

function isArtifactFormat(
  value: unknown,
): value is ArtifactFormat {
  return (
    value === 'pdf' ||
    value === 'docx' ||
    value === 'pptx'
  )
}

function isArtifactRecord(
  value: unknown,
): value is ArtifactRecord {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const artifact =
    value as Record<string, unknown>

  return (
    typeof artifact.artifact_id ===
      'string' &&
    typeof artifact.filename ===
      'string' &&
    isArtifactFormat(
      artifact.format,
    ) &&
    typeof artifact.media_type ===
      'string' &&
    typeof artifact.size_bytes ===
      'number' &&
    typeof artifact.sha256 ===
      'string' &&
    typeof artifact.created_at ===
      'string' &&
    typeof artifact.expires_at ===
      'string' &&
    typeof artifact.download_url ===
      'string'
  )
}

function loadArtifactHistory():
  ArtifactRecord[] {
  try {
    const stored =
      window.localStorage.getItem(
        historyStorageKey,
      )

    if (!stored) {
      return []
    }

    const parsed: unknown =
      JSON.parse(stored)

    if (!Array.isArray(parsed)) {
      return []
    }

    return parsed
      .filter(isArtifactRecord)
      .slice(0, 8)
  } catch {
    return []
  }
}


function isArtifactJobStatus(
  value: unknown,
): value is ActiveArtifactJob['status'] {
  return (
    value === 'queued' ||
    value === 'running' ||
    value === 'succeeded' ||
    value === 'failed'
  )
}

function isActiveArtifactJob(
  value: unknown,
): value is ActiveArtifactJob {
  if (
    typeof value !== 'object' ||
    value === null
  ) {
    return false
  }

  const job =
    value as Record<string, unknown>

  const progress =
    job.progressPercent

  return (
    typeof job.jobId === 'string' &&
    typeof job.accessToken === 'string' &&
    isArtifactJobStatus(job.status) &&
    typeof progress === 'number' &&
    Number.isInteger(progress) &&
    progress >= 0 &&
    progress <= 100 &&
    typeof job.stage === 'string' &&
    typeof job.createdAt === 'string' &&
    typeof job.expiresAt === 'string' &&
    (
      job.artifact === null ||
      isArtifactRecord(job.artifact)
    ) &&
    (
      job.error === null ||
      typeof job.error === 'string'
    )
  )
}

function loadActiveArtifactJob():
  ActiveArtifactJob | null {
  try {
    const stored =
      window.sessionStorage.getItem(
        activeJobStorageKey,
      )

    if (!stored) {
      return null
    }

    const parsed: unknown =
      JSON.parse(stored)

    return isActiveArtifactJob(parsed)
      ? parsed
      : null
  } catch {
    return null
  }
}

function cleanOptionalValue(
  value: string,
): string | undefined {
  const normalized = value.trim()

  return normalized || undefined
}

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof DOMException &&
    error.name === 'AbortError'
  )
}

function formatHistoryDate(
  value: string,
): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return 'Unknown date'
  }

  return new Intl.DateTimeFormat(
    undefined,
    {
      dateStyle: 'medium',
      timeStyle: 'short',
    },
  ).format(date)
}

export function ArtifactStudio() {
  const [
    creationMode,
    setCreationMode,
  ] = useState<ArtifactCreationMode>(
    'ai',
  )

  const [format, setFormat] =
    useState<ArtifactFormat>('pdf')

  const [title, setTitle] =
    useState('Authentic AI Report')

  const [subtitle, setSubtitle] =
    useState('Professional Artifact')

  const [author, setAuthor] =
    useState('Authentic AI')

  const [filename, setFilename] =
    useState('Authentic AI Report')

  const [content, setContent] =
    useState(initialContent)

  const [prompt, setPrompt] =
    useState(
      (
        'Create a professional report '
        + 'about the requested subject. '
        + 'Explain the main findings, '
        + 'risks, recommendations and '
        + 'next actions.'
      ),
    )

  const [tone, setTone] =
    useState<ArtifactTone>(
      'professional',
    )

  const [length, setLength] =
    useState<ArtifactLength>(
      'standard',
    )

  const [language, setLanguage] =
    useState('English')

  const [
    includeExecutiveSummary,
    setIncludeExecutiveSummary,
  ] = useState(true)

  const [
    includeTable,
    setIncludeTable,
  ] = useState(true)

  const [
    includeRecommendations,
    setIncludeRecommendations,
  ] = useState(true)

  const [
    includeConclusion,
    setIncludeConclusion,
  ] = useState(true)

  const [artifact, setArtifact] =
    useState<ArtifactRecord | null>(
      null,
    )

  const [history, setHistory] =
    useState<ArtifactRecord[]>(
      loadArtifactHistory,
    )

  const [
    errorMessage,
    setErrorMessage,
  ] = useState<string | null>(null)

  const [
    isGenerating,
    setIsGenerating,
  ] = useState(false)

  const [
    isDownloading,
    setIsDownloading,
  ] = useState(false)

  const [
    isDeleting,
    setIsDeleting,
  ] = useState(false)

  const [
    activeJob,
    setActiveJob,
  ] = useState<ActiveArtifactJob | null>(
    loadActiveArtifactJob,
  )

  const [
    isCheckingJob,
    setIsCheckingJob,
  ] = useState(false)

  const requestControllerRef =
    useRef<AbortController | null>(
      null,
    )

  const jobStatusControllerRef =
    useRef<AbortController | null>(
      null,
    )

  const jobStatusInFlightRef =
    useRef(false)

  useEffect(() => {
    try {
      window.localStorage.setItem(
        historyStorageKey,
        JSON.stringify(history),
      )
    } catch {
      /*
       * Artifact history persistence is
       * optional and must not block the UI.
       */
    }
  }, [history])

  useEffect(() => {
    try {
      if (activeJob) {
        window.sessionStorage.setItem(
          activeJobStorageKey,
          JSON.stringify(activeJob),
        )
      } else {
        window.sessionStorage.removeItem(
          activeJobStorageKey,
        )
      }
    } catch {
      /*
       * Background-job recovery is optional
       * and must not block generation.
       */
    }
  }, [activeJob])

  useEffect(() => {
    return () => {
      requestControllerRef.current
        ?.abort()

      jobStatusControllerRef.current
        ?.abort()
    }
  }, [])

  const characterCount =
    content.length

  const contentPercentage =
    useMemo(
      () =>
        Math.min(
          100,
          Math.round(
            (
              characterCount /
              maximumContentCharacters
            ) * 100,
          ),
        ),
      [characterCount],
    )

  const hasActiveArtifactJob =
    activeJob?.status === 'queued' ||
    activeJob?.status === 'running'

  const canGenerate =
    !isGenerating &&
    !hasActiveArtifactJob &&
    (
      creationMode === 'ai'
        ? (
            prompt.trim().length > 0 &&
            prompt.length <= 8_000 &&
            language.trim().length > 0
          )
        : (
            content.trim().length > 0 &&
            characterCount <=
              maximumContentCharacters
          )
    )


  const applyArtifactJobStatus =
    useCallback(
      (
        jobStatus:
          ArtifactJobStatusResponse,
      ) => {
        setActiveJob((current) => {
          if (
            !current ||
            current.jobId !==
              jobStatus.job_id
          ) {
            return current
          }

          return {
            ...current,
            status: jobStatus.status,
            progressPercent:
              jobStatus.progress_percent,
            stage: jobStatus.stage,
            createdAt:
              jobStatus.created_at,
            expiresAt:
              jobStatus.expires_at,
            artifact:
              jobStatus.artifact,
            error: jobStatus.error,
          }
        })

        if (
          jobStatus.status ===
            'succeeded' &&
          jobStatus.artifact
        ) {
          const completedArtifact =
            jobStatus.artifact

          setArtifact(
            completedArtifact,
          )

          setHistory((current) =>
            [
              completedArtifact,
              ...current.filter(
                (item) =>
                  item.artifact_id !==
                  completedArtifact
                    .artifact_id,
              ),
            ].slice(0, 8),
          )

          setErrorMessage(null)
        }

        if (
          jobStatus.status ===
            'failed' &&
          jobStatus.error
        ) {
          setErrorMessage(
            jobStatus.error,
          )
        }
      },
      [],
    )

  const checkArtifactJob =
    useCallback(
      async (
        jobId: string,
        accessToken: string,
        signal?: AbortSignal,
      ) => {
        if (
          jobStatusInFlightRef.current
        ) {
          return
        }

        jobStatusInFlightRef.current =
          true

        setIsCheckingJob(true)

        try {
          const jobStatus =
            await getArtifactJobStatus(
              jobId,
              accessToken,
              signal,
            )

          applyArtifactJobStatus(
            jobStatus,
          )
        } catch (error) {
          if (isAbortError(error)) {
            return
          }

          setErrorMessage(
            error instanceof
              ArtifactApiError
              ? error.message
              : (
                  'The artifact job '
                  + 'status could not '
                  + 'be loaded.'
                ),
          )
        } finally {
          jobStatusInFlightRef.current =
            false

          setIsCheckingJob(false)
        }
      },
      [applyArtifactJobStatus],
    )

  useEffect(() => {
    if (
      !activeJob ||
      (
        activeJob.status !== 'queued' &&
        activeJob.status !== 'running'
      )
    ) {
      return
    }

    jobStatusControllerRef.current
      ?.abort()

    const controller =
      new AbortController()

    jobStatusControllerRef.current =
      controller

    const pollJobStatus = () => {
      void checkArtifactJob(
        activeJob.jobId,
        activeJob.accessToken,
        controller.signal,
      )
    }

    pollJobStatus()

    const intervalId =
      window.setInterval(
        pollJobStatus,
        2_500,
      )

    return () => {
      window.clearInterval(
        intervalId,
      )

      controller.abort()

      if (
        jobStatusControllerRef.current
        === controller
      ) {
        jobStatusControllerRef.current =
          null
      }
    }
  }, [
    activeJob?.accessToken,
    activeJob?.jobId,
    activeJob?.status,
    checkArtifactJob,
  ])

  const handleRefreshArtifactJob =
    () => {
      if (!activeJob) {
        return
      }

      jobStatusControllerRef.current
        ?.abort()

      const controller =
        new AbortController()

      jobStatusControllerRef.current =
        controller

      void checkArtifactJob(
        activeJob.jobId,
        activeJob.accessToken,
        controller.signal,
      )
    }

  const handleClearArtifactJob =
    async () => {
      if (!activeJob) {
        return
      }

      const jobToDelete =
        activeJob

      jobStatusControllerRef.current
        ?.abort()

      setIsCheckingJob(true)

      try {
        await deleteArtifactJob(
          jobToDelete.jobId,
          jobToDelete.accessToken,
        )
      } catch (error) {
        const canClearLocally =
          error instanceof
            ArtifactApiError &&
          (
            error.status === 404 ||
            error.status === 410
          )

        if (!canClearLocally) {
          setErrorMessage(
            error instanceof
              ArtifactApiError
              ? error.message
              : (
                  'The artifact job '
                  + 'record could not '
                  + 'be deleted.'
                ),
          )
        }
      } finally {
        setActiveJob(null)
        setIsCheckingJob(false)
      }
    }

  const handleGenerate = async (
    event:
      FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault()

    if (!canGenerate) {
      return
    }

    requestControllerRef.current
      ?.abort()

    const controller =
      new AbortController()

    requestControllerRef.current =
      controller

    setErrorMessage(null)
    setIsGenerating(true)

    try {
      if (creationMode === 'ai') {
        const createdJob =
          await createArtifactJob(
            {
              prompt,
              format,
              title:
                cleanOptionalValue(
                  title,
                ),
              subtitle:
                cleanOptionalValue(
                  subtitle,
                ),
              author:
                cleanOptionalValue(
                  author,
                ),
              filename:
                cleanOptionalValue(
                  filename,
                ),
              tone,
              length,
              language:
                language.trim(),
              include_executive_summary:
                includeExecutiveSummary,
              include_table:
                includeTable,
              include_recommendations:
                includeRecommendations,
              include_conclusion:
                includeConclusion,
            },
            controller.signal,
          )

        setArtifact(null)

        setActiveJob({
          jobId: createdJob.job_id,
          accessToken:
            createdJob.access_token,
          status: createdJob.status,
          progressPercent: 0,
          stage:
            'Queued for generation',
          createdAt:
            createdJob.created_at,
          expiresAt:
            createdJob.expires_at,
          artifact: null,
          error: null,
        })
      } else {
        const generated =
          await generateArtifact(
            {
              content,
              format,
              title:
                cleanOptionalValue(
                  title,
                ),
              subtitle:
                cleanOptionalValue(
                  subtitle,
                ),
              author:
                cleanOptionalValue(
                  author,
                ),
              filename:
                cleanOptionalValue(
                  filename,
                ),
            },
            controller.signal,
          )

        setArtifact(generated)

        setHistory((current) =>
          [
            generated,
            ...current.filter(
              (item) =>
                item.artifact_id !==
                generated.artifact_id,
            ),
          ].slice(0, 8),
        )
      }
    } catch (error) {
      if (isAbortError(error)) {
        return
      }

      setErrorMessage(
        error instanceof
          ArtifactApiError
          ? error.message
          : (
              'The artifact could '
              + 'not be generated.'
            ),
      )
    } finally {
      if (
        requestControllerRef
          .current === controller
      ) {
        requestControllerRef.current =
          null
      }

      setIsGenerating(false)
    }
  }

  const handleDownload =
    async () => {
      if (!artifact) {
        return
      }

      setErrorMessage(null)
      setIsDownloading(true)

      try {
        await downloadArtifact(
          artifact,
        )
      } catch (error) {
        setErrorMessage(
          error instanceof
            ArtifactApiError
            ? error.message
            : (
                'The artifact could '
                + 'not be downloaded.'
              ),
        )
      } finally {
        setIsDownloading(false)
      }
    }

  const handleDelete =
    async () => {
      if (!artifact) {
        return
      }

      const shouldDelete =
        window.confirm(
          (
            'Delete this generated '
            + 'artifact? The download '
            + 'will stop working.'
          ),
        )

      if (!shouldDelete) {
        return
      }

      setErrorMessage(null)
      setIsDeleting(true)

      try {
        await deleteArtifact(
          artifact.artifact_id,
        )

        setHistory((current) =>
          current.filter(
            (item) =>
              item.artifact_id !==
              artifact.artifact_id,
          ),
        )

        setArtifact(null)
      } catch (error) {
        setErrorMessage(
          error instanceof
            ArtifactApiError
            ? error.message
            : (
                'The artifact could '
                + 'not be deleted.'
              ),
        )
      } finally {
        setIsDeleting(false)
      }
    }

  const selectHistoryArtifact = (
    selected: ArtifactRecord,
  ) => {
    setArtifact(selected)
    setErrorMessage(null)
  }

  return (
    <div className="artifact-studio-page">
      <header className="artifact-studio-header">
        <div className="artifact-studio-title">
          <span className="artifact-studio-mark">
            <FileOutput
              size={25}
              strokeWidth={1.75}
            />
          </span>

          <div>
            <p>Authentic AI</p>
            <h1>Artifact Studio</h1>
          </div>
        </div>

        <div className="artifact-security-note">
          <ShieldCheck
            size={17}
            strokeWidth={1.8}
          />

          <span>
            Private files ·
            24-hour expiry
          </span>
        </div>
      </header>

      <div className="artifact-studio-layout">
        <form
          className="artifact-editor-panel"
          onSubmit={handleGenerate}
        >
          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 1</span>
                <h2>
                  Choose creation mode
                </h2>
              </div>
            </div>

            <div className="artifact-creation-mode-grid">
              <button
                aria-pressed={
                  creationMode === 'ai'
                }
                className={
                  (
                    'artifact-creation-mode-card '
                    + (
                      creationMode === 'ai'
                        ? 'active'
                        : ''
                    )
                  )
                }
                disabled={isGenerating}
                onClick={() =>
                  setCreationMode('ai')
                }
                type="button"
              >
                <span className="artifact-creation-mode-icon">
                  <Sparkles
                    size={20}
                    strokeWidth={1.8}
                  />
                </span>

                <span className="artifact-creation-mode-copy">
                  <strong>
                    Create with AI
                  </strong>

                  <small>
                    Describe the document and
                    Authentic AI will compose
                    and generate it.
                  </small>
                </span>
              </button>

              <button
                aria-pressed={
                  creationMode === 'manual'
                }
                className={
                  (
                    'artifact-creation-mode-card '
                    + (
                      creationMode === 'manual'
                        ? 'active'
                        : ''
                    )
                  )
                }
                disabled={isGenerating}
                onClick={() =>
                  setCreationMode('manual')
                }
                type="button"
              >
                <span className="artifact-creation-mode-icon">
                  <PenLine
                    size={20}
                    strokeWidth={1.8}
                  />
                </span>

                <span className="artifact-creation-mode-copy">
                  <strong>
                    Use prepared content
                  </strong>

                  <small>
                    Paste structured Markdown
                    content and generate the
                    selected file directly.
                  </small>
                </span>
              </button>
            </div>
          </section>

          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 2</span>
                <h2>
                  Select the output
                </h2>
              </div>
            </div>

            <ArtifactFormatSelector
              disabled={isGenerating}
              onChange={setFormat}
              value={format}
            />
          </section>

          <section className="artifact-panel-section">
            <div className="artifact-section-heading">
              <div>
                <span>Step 3</span>
                <h2>
                  Document details
                </h2>
              </div>
            </div>

            <div className="artifact-field-grid">
              <label className="artifact-field full">
                <span>Title</span>

                <input
                  disabled={isGenerating}
                  maxLength={240}
                  onChange={(event) =>
                    setTitle(
                      event.target.value,
                    )
                  }
                  placeholder="Artifact title"
                  value={title}
                />
              </label>

              <label className="artifact-field full">
                <span>Subtitle</span>

                <input
                  disabled={isGenerating}
                  maxLength={500}
                  onChange={(event) =>
                    setSubtitle(
                      event.target.value,
                    )
                  }
                  placeholder="Optional subtitle"
                  value={subtitle}
                />
              </label>

              <label className="artifact-field">
                <span>Author</span>

                <input
                  disabled={isGenerating}
                  maxLength={160}
                  onChange={(event) =>
                    setAuthor(
                      event.target.value,
                    )
                  }
                  placeholder="Author"
                  value={author}
                />
              </label>

              <label className="artifact-field">
                <span>Filename</span>

                <input
                  disabled={isGenerating}
                  maxLength={180}
                  onChange={(event) =>
                    setFilename(
                      event.target.value,
                    )
                  }
                  placeholder="Output filename"
                  value={filename}
                />
              </label>
            </div>
          </section>

          {creationMode === 'ai' ? (
            <section className="artifact-panel-section">
              <div className="artifact-section-heading">
                <div>
                  <span>Step 4</span>
                  <h2>
                    Compose with AI
                  </h2>
                </div>
              </div>

              <ArtifactPromptComposer
                disabled={isGenerating}
                includeConclusion={
                  includeConclusion
                }
                includeExecutiveSummary={
                  includeExecutiveSummary
                }
                includeRecommendations={
                  includeRecommendations
                }
                includeTable={
                  includeTable
                }
                language={language}
                length={length}
                onIncludeConclusionChange={
                  setIncludeConclusion
                }
                onIncludeExecutiveSummaryChange={
                  setIncludeExecutiveSummary
                }
                onIncludeRecommendationsChange={
                  setIncludeRecommendations
                }
                onIncludeTableChange={
                  setIncludeTable
                }
                onLanguageChange={
                  setLanguage
                }
                onLengthChange={
                  setLength
                }
                onPromptChange={
                  setPrompt
                }
                onToneChange={
                  setTone
                }
                prompt={prompt}
                tone={tone}
              />
            </section>
          ) : (
            <section className="artifact-panel-section">
              <div
                className={
                  'artifact-section-heading '
                  + 'artifact-content-heading'
                }
              >
                <div>
                  <span>Step 4</span>
                  <h2>
                    Add structured content
                  </h2>
                </div>

                <small>
                  {characterCount
                    .toLocaleString()}
                  {' / '}
                  {maximumContentCharacters
                    .toLocaleString()}
                </small>
              </div>

              <label className="artifact-content-field">
                <span className="sr-only">
                  Artifact content
                </span>

                <textarea
                  disabled={isGenerating}
                  maxLength={
                    maximumContentCharacters
                  }
                  onChange={(event) =>
                    setContent(
                      event.target.value,
                    )
                  }
                  spellCheck
                  value={content}
                />
              </label>

              <div className="artifact-content-meter">
                <span
                  style={{
                    width:
                      `${contentPercentage}%`,
                  }}
                />
              </div>

              <p className="artifact-markdown-note">
                Supports headings,
                paragraphs, lists,
                Markdown tables and
                code blocks.
              </p>
            </section>
          )}

          {errorMessage && (
            <div
              className="artifact-error-message"
              role="alert"
            >
              <AlertCircle
                size={18}
                strokeWidth={1.9}
              />

              <span>
                {errorMessage}
              </span>
            </div>
          )}

          <button
            className="artifact-generate-button"
            disabled={!canGenerate}
            type="submit"
          >
            {isGenerating ? (
              <LoaderCircle
                className="artifact-spinner"
                size={19}
                strokeWidth={1.9}
              />
            ) : (
              <Sparkles
                size={19}
                strokeWidth={1.9}
              />
            )}

            <span>
              {isGenerating
                ? (
                    creationMode === 'ai'
                      ? (
                          'Composing and '
                          + 'generating…'
                        )
                      : (
                          'Generating '
                          + 'professional file…'
                        )
                  )
                : (
                    creationMode === 'ai'
                      ? (
                          `Compose ${
                            format.toUpperCase()
                          } with AI`
                        )
                      : (
                          `Generate ${
                            format.toUpperCase()
                          }`
                        )
                  )}
            </span>
          </button>
        </form>

        <aside className="artifact-output-panel">
          <div className="artifact-output-header">
            <p>Output</p>
            <h2>Generated artifact</h2>
          </div>

          {activeJob && (
            <ArtifactJobProgress
              checking={isCheckingJob}
              job={activeJob}
              onClear={
                handleClearArtifactJob
              }
              onRefresh={
                handleRefreshArtifactJob
              }
            />
          )}

          {artifact ? (
            <ArtifactResultCard
              artifact={artifact}
              deleting={isDeleting}
              downloading={
                isDownloading
              }
              onDelete={handleDelete}
              onDownload={
                handleDownload
              }
            />
          ) : (
            <div className="artifact-empty-state">
              <span>
                <FileOutput
                  size={29}
                  strokeWidth={1.6}
                />
              </span>

              <h3>
                No artifact generated yet
              </h3>

              <p>
                Complete the form and
                generate a professional
                PDF, DOCX or PPTX file.
              </p>
            </div>
          )}

          {history.length > 0 && (
            <section className="artifact-history">
              <div className="artifact-history-heading">
                <h3>Recent artifacts</h3>

                <span>
                  {history.length}
                </span>
              </div>

              <div className="artifact-history-list">
                {history.map(
                  (historyArtifact) => (
                    <button
                      className={
                        (
                          historyArtifact
                            .artifact_id ===
                          artifact
                            ?.artifact_id
                        )
                          ? 'active'
                          : ''
                      }
                      key={
                        historyArtifact
                          .artifact_id
                      }
                      onClick={() =>
                        selectHistoryArtifact(
                          historyArtifact,
                        )
                      }
                      type="button"
                    >
                      <span>
                        {historyArtifact
                          .format
                          .toUpperCase()}
                      </span>

                      <div>
                        <strong>
                          {
                            historyArtifact
                              .filename
                          }
                        </strong>

                        <small>
                          {formatHistoryDate(
                            historyArtifact
                              .created_at,
                          )}
                        </small>
                      </div>
                    </button>
                  ),
                )}
              </div>
            </section>
          )}
        </aside>
      </div>
    </div>
  )
}