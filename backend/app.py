import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.artifact_request_limit import ArtifactRequestSizeLimitMiddleware
from core.artifact_settings import artifact_settings
from core.request_context import RequestContextMiddleware
from routes.chat import (
    get_model_router,
    router as chat_router,
)
from routes.vision import router as vision_router
from routes.documents import router as documents_router
from routes.text_documents import router as text_documents_router
from routes.spreadsheets import router as spreadsheets_router
from routes.image_generation import router as image_generation_router
from routes.artifacts import (
    get_artifact_repository,
    get_artifact_storage,
    router as artifacts_router,
)
from routes.artifact_composer import (
    router as artifact_composer_router,
)
from routes.artifact_jobs import (
    get_artifact_job_store,
    recover_interrupted_artifact_jobs,
    router as artifact_jobs_router,
    shutdown_artifact_job_runner,
)
from routes.artifact_sources import (
    get_artifact_source_vault,
    router as artifact_sources_router,
)
from routes.artifact_intent import router as artifact_intent_router


async def _artifact_cleanup_loop() -> None:
    while True:
        try:
            await asyncio.sleep(
                artifact_settings
                .cleanup_interval_seconds
            )
            await asyncio.to_thread(
                get_artifact_repository()
                .cleanup_expired
            )
            await asyncio.to_thread(
                get_artifact_job_store()
                .cleanup_expired
            )
            await asyncio.to_thread(
                get_artifact_storage()
                .cleanup_expired
            )
            await asyncio.to_thread(
                get_artifact_source_vault()
                .cleanup_expired
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Cleanup is best-effort; request handling must remain available.
            continue


@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    await asyncio.to_thread(
        recover_interrupted_artifact_jobs
    )
    await asyncio.to_thread(
        get_artifact_repository()
        .cleanup_expired
    )
    await asyncio.to_thread(
        get_artifact_source_vault()
        .cleanup_expired
    )
    cleanup_task = asyncio.create_task(
        _artifact_cleanup_loop(),
        name="artifact-cleanup-loop",
    )

    try:
        yield
    finally:
        cleanup_task.cancel()
        await asyncio.gather(
            cleanup_task,
            return_exceptions=True,
        )
        await shutdown_artifact_job_runner()


app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description=(
        "Private backend API for the Authentic AI workspace."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    RequestContextMiddleware,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(
        settings.frontend_origins
    ),
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
        "X-Artifact-Job-Token",
        "X-Artifact-Token",
        "Idempotency-Key",
        "X-Request-ID",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-Artifact-SHA256",
        "X-Artifact-Version",
    ],
)

app.add_middleware(
    ArtifactRequestSizeLimitMiddleware,
    maximum_request_bytes=(
        artifact_settings.maximum_request_bytes
    ),
)

app.include_router(
    chat_router,
    prefix="/api/v1",
)

app.include_router(
    vision_router,
    prefix="/api/v1",
)

app.include_router(
    documents_router,
    prefix="/api/v1",
)

app.include_router(
    text_documents_router,
    prefix="/api/v1",
)

app.include_router(
    spreadsheets_router,
    prefix="/api/v1",
)

app.include_router(
    image_generation_router,
    prefix="/api/v1",
)


app.include_router(
    artifacts_router,
    prefix="/api/v1",
)

app.include_router(
    artifact_composer_router,
    prefix="/api/v1",
)

app.include_router(
    artifact_jobs_router,
    prefix="/api/v1",
)

app.include_router(
    artifact_sources_router,
    prefix="/api/v1",
)

app.include_router(
    artifact_intent_router,
    prefix="/api/v1",
)

@app.get(
    "/api/v1/health",
    tags=["system"],
)
async def health_check() -> dict[str, Any]:
    model_router = get_model_router()

    artifact_repository_stats = await asyncio.to_thread(
        get_artifact_repository().stats
    )
    artifact_storage_stats = await asyncio.to_thread(
        get_artifact_storage().stats
    )
    artifact_job_stats = await asyncio.to_thread(
        get_artifact_job_store().stats
    )

    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.environment,
        "ai_configured": (
            model_router.is_configured()
        ),
        "providers": model_router.status(),
        "primary_model": (
            settings.groq_quality_model
        ),
        "artifacts": {
            "repository": artifact_repository_stats,
            "storage": artifact_storage_stats,
            "jobs": artifact_job_stats,
        },

        # Compatibility fields retained for
        # the existing frontend and tests.
        "groq_configured": bool(
            settings.groq_api_key
        ),
        "model": settings.groq_model,
    }


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
