from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.artifact_intent as artifact_intent_routes
from artifacts.intent_classifier import classify_artifact_intent
from schemas.artifact_intent import ArtifactIntentRequest
from schemas.chat import ChatResponse, TokenUsage


class IntentRouter:
    def __init__(self, answer: str) -> None:
        self.answer_text = answer
        self.messages: list[str] = []

    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        del history
        self.messages.append(message)
        return ChatResponse(
            answer=self.answer_text,
            provider="test",
            model="intent-test",
            usage=TokenUsage(),
        )


@pytest.mark.asyncio
async def test_explicit_pdf_creation_uses_fast_path_without_model() -> None:
    router = IntentRouter("not used")
    result = await classify_artifact_intent(
        ArtifactIntentRequest(message="Is answer ka PDF bana do."),
        model_router=router,
    )
    assert result.action == "create"
    assert result.format == "pdf"
    assert result.source == "deterministic"
    assert router.messages == []


@pytest.mark.asyncio
async def test_ambiguous_hinglish_submission_request_uses_ai_semantics() -> None:
    router = IntentRouter(
        '{"action":"create","format":null,"confidence":0.94,'
        '"reason":"The user wants a submission-ready project deliverable."}'
    )
    result = await classify_artifact_intent(
        ArtifactIntentRequest(
            message="Mera college project submission ke liye final ready kar do."
        ),
        model_router=router,
    )
    assert result.action == "create"
    assert result.format == "pdf"
    assert result.source == "ai"
    assert len(router.messages) == 1
    assert "strict document-action intent classifier" in router.messages[0]


@pytest.mark.asyncio
async def test_attached_source_redesign_is_new_file_not_artifact_revision() -> None:
    router = IntentRouter(
        "```json\n"
        '{"action":"revise","format":"pdf","confidence":0.96,'
        '"reason":"Redesign request."}\n```'
    )
    result = await classify_artifact_intent(
        ArtifactIntentRequest(
            message="Iska design professional kar do.",
            has_attachment=True,
            attachment_names=["project.pdf"],
        ),
        model_router=router,
    )
    assert result.action == "create"
    assert result.format == "pdf"


@pytest.mark.asyncio
async def test_revision_requires_an_existing_generated_artifact() -> None:
    router = IntentRouter(
        '{"action":"revise","format":"pdf","confidence":0.91,'
        '"reason":"Change request."}'
    )
    result = await classify_artifact_intent(
        ArtifactIntentRequest(
            message="Current report ka conclusion improve kar do.",
            has_generated_artifact=False,
        ),
        model_router=router,
    )
    assert result.action == "none"
    assert result.format is None


@pytest.mark.asyncio
async def test_classifier_failure_uses_safe_document_fallback() -> None:
    router = IntentRouter("not valid json")
    result = await classify_artifact_intent(
        ArtifactIntentRequest(
            message="Project report ko professionally submission ready kar do."
        ),
        model_router=router,
    )
    assert result.action == "create"
    assert result.format == "pdf"
    assert result.source == "fallback"


@pytest.mark.asyncio
async def test_ordinary_chat_skips_model_and_preserves_chat_flow() -> None:
    router = IntentRouter("not used")
    result = await classify_artifact_intent(
        ArtifactIntentRequest(message="Explain recursion with one example."),
        model_router=router,
    )
    assert result.action == "none"
    assert result.source == "deterministic"
    assert router.messages == []


def test_intent_route_returns_typed_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    router = IntentRouter(
        '{"action":"create","format":"pdf","confidence":0.9,'
        '"reason":"Downloadable assignment requested."}'
    )
    monkeypatch.setattr(
        artifact_intent_routes,
        "get_model_router",
        lambda: router,
    )
    app = FastAPI()
    app.include_router(artifact_intent_routes.router, prefix="/api/v1")
    response = TestClient(app).post(
        "/api/v1/artifacts/intent",
        json={
            "message": "Assignment ko final downloadable form me ready kar do.",
            "has_attachment": False,
            "attachment_names": [],
            "has_generated_artifact": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["action"] == "create"
    assert response.json()["format"] == "pdf"

