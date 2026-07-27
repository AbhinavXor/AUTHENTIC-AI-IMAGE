from __future__ import annotations

import asyncio
import logging

from ai.model_router import ModelRouter
from ai.provider_adapter import ProviderError
from artifacts.composer import (
    ArtifactCompositionError,
    ComposedArtifactDraft,
    compose_artifact_draft,
)
from artifacts.engine import (
    ArtifactGenerationError,
    ArtifactValidationError,
)
from artifacts.job_store import (
    ArtifactJobConflictError,
    ArtifactJobExpiredError,
    ArtifactJobNotFoundError,
    ArtifactJobStorageError,
    ArtifactJobStore,
)
from artifacts.parser import (
    parse_artifact_document,
)
from artifacts.storage import (
    ArtifactStorage,
    ArtifactStorageError,
    StoredArtifact,
)
from core.artifact_job_settings import (
    artifact_job_settings,
)
from schemas.artifact_composer import (
    ArtifactComposeResponse,
)


logger = logging.getLogger(__name__)


_PROVIDER_ERROR_MESSAGES = {
    "configuration": (
        "No AI provider is configured "
        "for artifact composition."
    ),
    "authentication": (
        "AI provider credentials are invalid."
    ),
    "billing": (
        "The selected AI provider has no "
        "available credits or billing access."
    ),
    "rate_limit": (
        "Available AI quota or rate limit "
        "was reached."
    ),
    "timeout": (
        "The artifact composition service "
        "took too long."
    ),
    "connection": (
        "Could not connect to the AI "
        "composition service."
    ),
    "request": (
        "The AI provider rejected the "
        "artifact request."
    ),
    "response": (
        "The AI provider returned an "
        "unusable artifact draft."
    ),
    "availability": (
        "All configured AI providers are "
        "temporarily unavailable."
    ),
    "unknown": (
        "The artifact draft could not "
        "be composed."
    ),
}


def _build_artifact_response(
    *,
    stored: StoredArtifact,
    draft: ComposedArtifactDraft,
) -> ArtifactComposeResponse:
    return ArtifactComposeResponse(
        artifact_id=stored.artifact_id,
        filename=stored.filename,
        format=stored.format,
        media_type=stored.media_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        created_at=stored.created_at,
        expires_at=stored.expires_at,
        download_url=(
            f"/api/v1/artifacts/"
            f"{stored.artifact_id}/download"
        ),
        provider=draft.provider,
        model=draft.model,
        request_id=draft.request_id,
        draft_character_count=len(
            draft.content
        ),
        composition_mode=(
            "ai_prompt_to_artifact"
        ),
    )


def _safe_error_message(
    error: Exception,
) -> str:
    if isinstance(
        error,
        ProviderError,
    ):
        return _PROVIDER_ERROR_MESSAGES.get(
            error.code,
            _PROVIDER_ERROR_MESSAGES[
                "unknown"
            ],
        )

    if isinstance(
        error,
        ArtifactCompositionError,
    ):
        return str(error)

    if isinstance(
        error,
        ArtifactValidationError,
    ):
        return str(error)

    if isinstance(
        error,
        ArtifactGenerationError,
    ):
        return (
            "The generated document could "
            "not be rendered."
        )

    if isinstance(
        error,
        ArtifactStorageError,
    ):
        return (
            "The generated artifact could "
            "not be stored."
        )

    if isinstance(
        error,
        ValueError,
    ):
        return (
            "The generated document content "
            "could not be processed."
        )

    return (
        "Artifact generation failed because "
        "of an unexpected server error."
    )


class ArtifactJobRunner:
    """
    Runs prompt-to-artifact jobs in the
    current application process.

    A semaphore limits simultaneous AI and
    rendering work. Job metadata remains
    persisted in ArtifactJobStore.
    """

    def __init__(
        self,
        *,
        job_store: ArtifactJobStore,
        model_router: ModelRouter,
        artifact_storage: ArtifactStorage,
        maximum_concurrent_jobs: (
            int | None
        ) = None,
    ) -> None:
        self.job_store = job_store
        self.model_router = model_router
        self.artifact_storage = (
            artifact_storage
        )

        self.maximum_concurrent_jobs = (
            maximum_concurrent_jobs
            if maximum_concurrent_jobs
            is not None
            else artifact_job_settings
            .maximum_concurrent_jobs
        )

        if (
            self.maximum_concurrent_jobs
            < 1
        ):
            raise ValueError(
                (
                    "Maximum concurrent artifact "
                    "jobs must be positive."
                )
            )

        self._semaphore = (
            asyncio.Semaphore(
                self.maximum_concurrent_jobs
            )
        )

        self._tasks: dict[
            str,
            asyncio.Task[None],
        ] = {}

    @property
    def active_task_count(self) -> int:
        return len(self._tasks)

    def submit(
        self,
        job_id: str,
    ) -> None:
        """
        Schedule one persisted queued job on
        the currently running event loop.
        """

        existing_task = self._tasks.get(
            job_id
        )

        if (
            existing_task is not None
            and not existing_task.done()
        ):
            return

        loop = (
            asyncio.get_running_loop()
        )

        task = loop.create_task(
            self._run_job(job_id),
            name=(
                "artifact-job-"
                f"{job_id}"
            ),
        )

        self._tasks[job_id] = task

        task.add_done_callback(
            lambda completed_task: (
                self._handle_task_done(
                    job_id,
                    completed_task,
                )
            )
        )

    def _handle_task_done(
        self,
        job_id: str,
        task: asyncio.Task[None],
    ) -> None:
        current = self._tasks.get(
            job_id
        )

        if current is task:
            self._tasks.pop(
                job_id,
                None,
            )

        if task.cancelled():
            return

        try:
            error = task.exception()
        except asyncio.CancelledError:
            return

        if error is not None:
            logger.error(
                (
                    "Unhandled artifact job "
                    "task error: job_id=%s"
                ),
                job_id,
                exc_info=(
                    type(error),
                    error,
                    error.__traceback__,
                ),
            )

    async def _update_running(
        self,
        job_id: str,
        *,
        progress_percent: int,
        stage: str,
    ) -> None:
        await asyncio.to_thread(
            self.job_store.update,
            job_id,
            status="running",
            progress_percent=(
                progress_percent
            ),
            stage=stage,
        )

    async def _mark_failed(
        self,
        job_id: str,
        error: Exception,
    ) -> None:
        message = _safe_error_message(
            error
        )

        try:
            await asyncio.to_thread(
                self.job_store.update,
                job_id,
                status="failed",
                progress_percent=100,
                stage="Generation failed",
                error=message,
            )

        except (
            ArtifactJobNotFoundError,
            ArtifactJobExpiredError,
            ArtifactJobConflictError,
            ArtifactJobStorageError,
        ):
            logger.exception(
                (
                    "Artifact job failure "
                    "could not be persisted: "
                    "job_id=%s"
                ),
                job_id,
            )

    async def _run_job(
        self,
        job_id: str,
    ) -> None:
        async with self._semaphore:
            try:
                job = await asyncio.to_thread(
                    self.job_store.get_internal,
                    job_id,
                )

                if job.status != "queued":
                    return

                await self._update_running(
                    job_id,
                    progress_percent=10,
                    stage=(
                        "Composing document "
                        "content"
                    ),
                )

                draft = (
                    await compose_artifact_draft(
                        job.request,
                        model_router=(
                            self.model_router
                        ),
                    )
                )

                await self._update_running(
                    job_id,
                    progress_percent=55,
                    stage=(
                        "Preparing document "
                        "structure"
                    ),
                )

                artifact = (
                    parse_artifact_document(
                        draft.content,
                        title=(
                            job.request.title
                        ),
                        subtitle=(
                            job.request.subtitle
                        ),
                        author=(
                            job.request.author
                        ),
                    )
                )

                await self._update_running(
                    job_id,
                    progress_percent=70,
                    stage=(
                        "Rendering and "
                        "storing file"
                    ),
                )

                await asyncio.to_thread(
                    self.artifact_storage
                    .cleanup_expired
                )

                stored = await asyncio.to_thread(
                    self.artifact_storage.create,
                    artifact,
                    format=(
                        job.request.format
                    ),
                    filename=(
                        job.request.filename
                    ),
                )

                response = (
                    _build_artifact_response(
                        stored=stored,
                        draft=draft,
                    )
                )

                await asyncio.to_thread(
                    self.job_store.update,
                    job_id,
                    status="succeeded",
                    progress_percent=100,
                    stage="Artifact ready",
                    artifact=response,
                )

            except asyncio.CancelledError:
                try:
                    await asyncio.to_thread(
                        self.job_store.update,
                        job_id,
                        status="failed",
                        progress_percent=100,
                        stage=(
                            "Generation "
                            "interrupted"
                        ),
                        error=(
                            "Artifact generation "
                            "was interrupted."
                        ),
                    )
                except Exception:
                    logger.exception(
                        (
                            "Cancelled artifact "
                            "job could not be "
                            "updated: job_id=%s"
                        ),
                        job_id,
                    )

                raise

            except (
                ArtifactJobNotFoundError,
                ArtifactJobExpiredError,
            ):
                return

            except Exception as error:
                logger.exception(
                    (
                        "Artifact background "
                        "job failed: job_id=%s"
                    ),
                    job_id,
                )

                await self._mark_failed(
                    job_id,
                    error,
                )

    async def shutdown(self) -> None:
        """
        Cancel active in-process tasks during
        graceful application shutdown.
        """

        tasks = tuple(
            self._tasks.values()
        )

        if not tasks:
            return

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        self._tasks.clear()