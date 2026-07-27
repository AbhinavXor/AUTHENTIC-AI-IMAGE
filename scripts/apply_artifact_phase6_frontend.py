from __future__ import annotations

from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]


def update_file(
    relative_path: str,
    transform: Callable[[str], str],
) -> None:
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    content = path.read_text(
        encoding="utf-8",
    )

    updated = transform(content)

    if updated == content:
        print(
            f"UNCHANGED: {relative_path}"
        )
        return

    path.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        f"UPDATED: {relative_path}"
    )


def replace_once(
    content: str,
    old: str,
    new: str,
    *,
    description: str,
) -> str:
    if new in content:
        return content

    if old not in content:
        raise RuntimeError(
            f"{description} marker was not found."
        )

    return content.replace(
        old,
        new,
        1,
    )


def patch_artifact_studio(
    content: str,
) -> str:
    content = replace_once(
        content,
        """import {
  useEffect,
  useMemo,
  useRef,
""",
        """import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
""",
        description=(
            "React useCallback import"
        ),
    )

    content = replace_once(
        content,
        """import {
  ArtifactPromptComposer,
} from '../components/Artifacts/ArtifactPromptComposer'
""",
        """import {
  ArtifactPromptComposer,
} from '../components/Artifacts/ArtifactPromptComposer'
import {
  ArtifactJobProgress,
} from '../components/Artifacts/ArtifactJobProgress'
""",
        description=(
            "Artifact Job Progress import"
        ),
    )

    content = replace_once(
        content,
        """import {
  composeArtifact,
} from '../services/artifact-composer'
""",
        """import {
  createArtifactJob,
  deleteArtifactJob,
  getArtifactJobStatus,
} from '../services/artifact-jobs'
""",
        description=(
            "Artifact background-job service import"
        ),
    )

    content = replace_once(
        content,
        """import type {
  ArtifactLength,
  ArtifactTone,
} from '../types/artifact-composer'
""",
        """import type {
  ArtifactLength,
  ArtifactTone,
} from '../types/artifact-composer'
import type {
  ActiveArtifactJob,
  ArtifactJobStatusResponse,
} from '../types/artifact-jobs'
""",
        description=(
            "Artifact background-job type import"
        ),
    )

    content = replace_once(
        content,
        """const historyStorageKey =
  'authentic-ai.artifact-studio.history.v1'

type ArtifactCreationMode =
""",
        """const historyStorageKey =
  'authentic-ai.artifact-studio.history.v1'

const activeJobStorageKey =
  'authentic-ai.artifact-studio.active-job.v1'

type ArtifactCreationMode =
""",
        description=(
            "Active artifact job storage key"
        ),
    )

    load_job_helpers = """
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

"""

    content = replace_once(
        content,
        """function cleanOptionalValue(
  value: string,
): string | undefined {
""",
        (
            load_job_helpers
            + """function cleanOptionalValue(
  value: string,
): string | undefined {
"""
        ),
        description=(
            "Active artifact job loader"
        ),
    )

    content = replace_once(
        content,
        """  const [
    isDeleting,
    setIsDeleting,
  ] = useState(false)

  const requestControllerRef =
""",
        """  const [
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
""",
        description=(
            "Active artifact job state"
        ),
    )

    content = replace_once(
        content,
        """  const requestControllerRef =
    useRef<AbortController | null>(
      null,
    )

  useEffect(() => {
""",
        """  const requestControllerRef =
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
""",
        description=(
            "Artifact job request references"
        ),
    )

    history_effect = """  useEffect(() => {
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

"""

    active_job_effect = history_effect + """  useEffect(() => {
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

"""

    content = replace_once(
        content,
        history_effect,
        active_job_effect,
        description=(
            "Active artifact job persistence"
        ),
    )

    content = replace_once(
        content,
        """  useEffect(() => {
    return () => {
      requestControllerRef.current
        ?.abort()
    }
  }, [])
""",
        """  useEffect(() => {
    return () => {
      requestControllerRef.current
        ?.abort()

      jobStatusControllerRef.current
        ?.abort()
    }
  }, [])
""",
        description=(
            "Artifact request cleanup"
        ),
    )

    content = replace_once(
        content,
        """  const canGenerate =
    !isGenerating &&
    (
      creationMode === 'ai'
""",
        """  const hasActiveArtifactJob =
    activeJob?.status === 'queued' ||
    activeJob?.status === 'running'

  const canGenerate =
    !isGenerating &&
    !hasActiveArtifactJob &&
    (
      creationMode === 'ai'
""",
        description=(
            "Background generation eligibility"
        ),
    )

    background_job_logic = """
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

"""

    content = replace_once(
        content,
        """  const handleGenerate = async (
    event:
      FormEvent<HTMLFormElement>,
  ) => {
""",
        (
            background_job_logic
            + """  const handleGenerate = async (
    event:
      FormEvent<HTMLFormElement>,
  ) => {
"""
        ),
        description=(
            "Background artifact job logic"
        ),
    )

    current_generation_block = """      const generated =
        creationMode === 'ai'
          ? await composeArtifact(
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
          : await generateArtifact(
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
"""

    background_generation_block = """      if (creationMode === 'ai') {
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
"""

    content = replace_once(
        content,
        current_generation_block,
        background_generation_block,
        description=(
            "Background artifact generation call"
        ),
    )

    output_marker = """          {artifact ? (
            <ArtifactResultCard
"""

    output_replacement = """          {activeJob && (
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
"""

    content = replace_once(
        content,
        output_marker,
        output_replacement,
        description=(
            "Artifact job progress output"
        ),
    )

    return content


def patch_app_styles(
    content: str,
) -> str:
    style_import = (
        "import "
        "'./styles/artifact-job-progress.css'\n"
    )

    if style_import in content:
        return content

    marker = (
        "import "
        "'./styles/artifact-ai-composer.css'\n"
    )

    if marker not in content:
        raise RuntimeError(
            (
                "Artifact AI Composer "
                "stylesheet marker "
                "was not found."
            )
        )

    return content.replace(
        marker,
        marker + style_import,
        1,
    )


def verify_phase6_frontend_files() -> None:
    required_files = [
        (
            "frontend/src/types/"
            "artifact-jobs.ts"
        ),
        (
            "frontend/src/services/"
            "artifact-jobs.ts"
        ),
        (
            "frontend/src/components/"
            "Artifacts/"
            "ArtifactJobProgress.tsx"
        ),
        (
            "frontend/src/styles/"
            "artifact-job-progress.css"
        ),
    ]

    missing_files = [
        relative_path
        for relative_path in required_files
        if not (
            ROOT / relative_path
        ).is_file()
    ]

    if missing_files:
        formatted = "\n".join(
            f"- {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            (
                "Phase 6 frontend files "
                "are missing:\n"
                f"{formatted}"
            )
        )

    print(
        (
            "PASS: All Phase 6 frontend "
            "files exist"
        )
    )


def main() -> None:
    verify_phase6_frontend_files()

    update_file(
        (
            "frontend/src/pages/"
            "ArtifactStudio.tsx"
        ),
        patch_artifact_studio,
    )

    update_file(
        "frontend/src/App.tsx",
        patch_app_styles,
    )

    print()
    print(
        (
            "PASS: Phase 6 frontend "
            "integration applied"
        )
    )


if __name__ == "__main__":
    main()