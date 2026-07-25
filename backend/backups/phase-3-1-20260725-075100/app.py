from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from routes.chat import router as chat_router


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Private backend API for Authentic AI Image."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
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


@app.get(
    "/api/v1/health",
    tags=["system"],
)
async def health_check() -> dict[str, Any]:
    return {
        "status": "ok",
        "application": settings.app_name,
        "environment": settings.environment,
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
