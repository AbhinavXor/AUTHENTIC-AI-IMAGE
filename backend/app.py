from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routes.chat import (
    get_model_router,
    router as chat_router,
)
from routes.vision import router as vision_router
from routes.documents import router as documents_router
from routes.text_documents import router as text_documents_router
from routes.spreadsheets import router as spreadsheets_router
from routes.image_generation import router as image_generation_router


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Private backend API for Authentic AI Image."
    ),
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
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
    ],
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


@app.get(
    "/api/v1/health",
    tags=["system"],
)
async def health_check() -> dict[str, Any]:
    model_router = get_model_router()

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
