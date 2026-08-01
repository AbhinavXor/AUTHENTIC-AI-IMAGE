from __future__ import annotations

import asyncio
import logging

from ai.provider_adapter import ProviderError
from artifacts.composer import ArtifactCompositionError
from artifacts.contracts import ArtifactAnswerRouter
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
from artifacts.repository import ArtifactRepository
from artifacts.responses import artifact_response_payload
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import (
    ArtifactStorage,
    ArtifactStorageError,
)
from artifacts.source_vault import ArtifactSourceVault
from artifacts.source_vault import (
    ArtifactSourceAccessError,
    ArtifactSourceExpiredError,
    ArtifactSourceNotFoundError,
)
from core.artifact_job_settings import artifact_job_settings
from schemas.artifact_composer import ArtifactComposeResponse

logger = logging.getLogger(__name__)

_PROVIDER_ERROR_MESSAGES = {
    "configuration": "No AI provider is configured for artifact composition.",
    "authentication": "AI provider credentials are invalid.",
    "billing": "The selected AI provider has no available credits or billing access.",
    "rate_limit": "Available AI quota or rate limit was reached.",
    "timeout": "The artifact composition service took too long.",
    "connection": "Could not connect to the AI composition service.",
    "request": "The AI provider rejected the artifact request.",
    "response": "The AI provider returned an unusable artifact draft.",
    "availability": "All configured AI providers are temporarily unavailable.",
    "unknown": "The artifact draft could not be composed.",
}


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, ProviderError):
        return _PROVIDER_ERROR_MESSAGES.get(
            error.code,
            _PROVIDER_ERROR_MESSAGES["unknown"],
        )
    if isinstance(error, ArtifactCompositionError):
        return str(error)
    if isinstance(error, (ArtifactValidationError, ValueError)):
        return str(error)
    if isinstance(error, ArtifactGenerationError):
        return "The generated document could not be rendered."
    if isinstance(error, ArtifactStorageError):
        return "The generated artifact could not be stored."
    if isinstance(
        error,
        (
            ArtifactSourceAccessError,
            ArtifactSourceExpiredError,
            ArtifactSourceNotFoundError,
        ),
    ):
        return (
            "The durable document source is unavailable or expired. "
            "Upload the source again and retry."
        )
    return "Artifact generation failed because of an unexpected server error."


class ArtifactJobRunner:
    """Runs persisted prompt-to-artifact jobs with bounded concurrency."""

    def __init__(
        self,
        *,
        job_store: ArtifactJobStore,
        model_router: ArtifactAnswerRouter,
        artifact_storage: ArtifactStorage,
        artifact_repository: ArtifactRepository,
        source_vault: ArtifactSourceVault | None = None,
        maximum_concurrent_jobs: int | None = None,
    ) -> None:
        self.job_store = job_store
        self.model_router = model_router
        self.artifact_storage = artifact_storage
        self.artifact_repository = artifact_repository
        self.lifecycle_service = ArtifactLifecycleService(
            artifact_storage=artifact_storage,
            artifact_repository=artifact_repository,
            model_router=model_router,
            source_vault=source_vault,
        )
        self.maximum_concurrent_jobs = (
            maximum_concurrent_jobs
            if maximum_concurrent_jobs is not None
            else artifact_job_settings.maximum_concurrent_jobs
        )

        if self.maximum_concurrent_jobs < 1:
            raise ValueError(
                "Maximum concurrent artifact jobs must be positive."
            )

        self._semaphore = asyncio.Semaphore(
            self.maximum_concurrent_jobs
        )
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def active_task_count(self) -> int:
        return len(self._tasks)

    def submit(self, job_id: str) -> None:
        existing = self._tasks.get(job_id)
        if existing is not None and not existing.done():
            return

        loop = asyncio.get_running_loop()
        task = loop.create_task(
            self._run_job(job_id),
            name=f"artifact-job-{job_id}",
        )
        self._tasks[job_id] = task
        task.add_done_callback(
            lambda completed: self._handle_task_done(
                job_id,
                completed,
            )
        )

    def cancel(self, job_id: str) -> bool:
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True

    def _handle_task_done(
        self,
        job_id: str,
        task: asyncio.Task[None],
    ) -> None:
        if self._tasks.get(job_id) is task:
            self._tasks.pop(job_id, None)

        if task.cancelled():
            return

        try:
            error = task.exception()
        except asyncio.CancelledError:
            return

        if error is not None:
            logger.error(
                "Unhandled artifact job task error: job_id=%s",
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
            progress_percent=progress_percent,
            stage=stage,
        )

    async def _mark_failed(
        self,
        job_id: str,
        error: Exception,
    ) -> None:
        try:
            await asyncio.to_thread(
                self.job_store.update,
                job_id,
                status="failed",
                progress_percent=100,
                stage="Generation failed",
                error=_safe_error_message(error),
            )
        except (
            ArtifactJobNotFoundError,
            ArtifactJobExpiredError,
            ArtifactJobConflictError,
            ArtifactJobStorageError,
        ):
            logger.exception(
                "Artifact job failure could not be persisted: job_id=%s",
                job_id,
            )

    async def _run_job(self, job_id: str) -> None:
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
                    stage="Resolving source and planning document",
                )
                await self._update_running(
                    job_id,
                    progress_percent=25,
                    stage="Composing document content",
                )

                async def composition_progress(
                    completed: int,
                    total: int,
                    stage: str,
                ) -> None:
                    fraction = (
                        completed / total
                        if total > 0
                        else 0.0
                    )
                    await self._update_running(
                        job_id,
                        progress_percent=min(
                            80,
                            25 + int(fraction * 55),
                        ),
                        stage=stage,
                    )

                result = await self.lifecycle_service.compose_and_create(
                    job.request,
                    progress_callback=composition_progress,
                )

                await self._update_running(
                    job_id,
                    progress_percent=85,
                    stage="Validating rendered output",
                )

                token = result.view.access_token
                if not token:
                    raise ArtifactStorageError(
                        "Artifact capability token was not created."
                    )

                response = ArtifactComposeResponse(
                    **artifact_response_payload(
                        result.view,
                        access_token=token,
                    ),
                    provider=result.provider or "unknown",
                    model=result.model or "unknown",
                    request_id=result.request_id,
                    draft_character_count=(
                        result.draft_character_count
                    ),
                    composition_mode="ai_prompt_to_artifact",
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
                    current = await asyncio.to_thread(
                        self.job_store.get_internal,
                        job_id,
                    )
                    if current.status not in {
                        "cancelled",
                        "succeeded",
                        "failed",
                    }:
                        await asyncio.to_thread(
                            self.job_store.update,
                            job_id,
                            status="cancelled",
                            progress_percent=current.progress_percent,
                            stage="Generation cancelled",
                        )
                except Exception:
                    logger.exception(
                        "Cancelled artifact job could not be updated: job_id=%s",
                        job_id,
                    )
                raise
            except (ArtifactJobNotFoundError, ArtifactJobExpiredError):
                return
            except Exception as error:
                logger.exception(
                    "Artifact background job failed: job_id=%s",
                    job_id,
                )
                await self._mark_failed(job_id, error)

    async def shutdown(self) -> None:
        tasks = tuple(self._tasks.values())
        if not tasks:
            return

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )
        self._tasks.clear()
