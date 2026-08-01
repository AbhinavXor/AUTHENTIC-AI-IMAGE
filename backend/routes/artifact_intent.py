from __future__ import annotations

from fastapi import APIRouter

from artifacts.intent_classifier import classify_artifact_intent
from routes.chat import get_model_router
from schemas.artifact_intent import ArtifactIntentRequest, ArtifactIntentResponse


router = APIRouter(
    prefix="/artifacts/intent",
    tags=["artifact-intent"],
)


@router.post("", response_model=ArtifactIntentResponse)
async def resolve_artifact_intent(
    request: ArtifactIntentRequest,
) -> ArtifactIntentResponse:
    return await classify_artifact_intent(
        request,
        model_router=get_model_router(),
    )

