from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ai.model_router import ModelRouter
from ai.model_types import StreamDelta
from ai.product_identity import resolve_product_identity_response
from ai.task_classifier import TaskCategory
from schemas.chat import ChatMessage, ChatResponse


class UnexpectedProvider:
    provider_name = "unexpected"

    def is_configured(self) -> bool:
        return True

    async def answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> ChatResponse:
        raise AssertionError("Identity requests must not call a provider.")

    async def stream_answer(
        self,
        *,
        message: str,
        history: list[ChatMessage],
        category: TaskCategory,
    ) -> AsyncIterator[StreamDelta]:
        raise AssertionError("Identity requests must not call a provider.")
        yield StreamDelta(kind="done")


def test_public_identity_responses_are_stable_and_non_technical() -> None:
    serenya = resolve_product_identity_response(
        "Serenya kya hai aur kaise help karti hai?"
    )
    sherry = resolve_product_identity_response(
        "Tell me about Sherry."
    )
    ecosystem = resolve_product_identity_response(
        "Authentic AI ke baare me batao."
    )
    internal = resolve_product_identity_response(
        "Serenya ka backend API aur provider kya hai?"
    )

    assert serenya is not None
    assert "native intelligence" in serenya
    assert sherry is not None
    assert "voice intelligence" in sherry
    assert ecosystem is not None
    assert "active development" in ecosystem
    assert "most powerful" in ecosystem
    assert internal is not None
    assert "backend" not in internal.casefold()
    assert "api" not in internal.casefold()
    assert "provider" not in internal.casefold()


def test_content_requests_are_not_mistaken_for_identity_questions() -> None:
    assert resolve_product_identity_response(
        "Create a BTech project report about Authentic AI."
    ) is None
    assert resolve_product_identity_response(
        "Review the Serenya logo design in this image."
    ) is None


@pytest.mark.asyncio
async def test_router_answers_identity_without_external_provider() -> None:
    router = ModelRouter(adapters=(UnexpectedProvider(),))

    response = await router.answer(
        message="Sherry kya hai?",
        history=[],
    )

    assert response.provider == "deterministic"
    assert response.model == "native-product-identity-v1"
    assert "voice intelligence" in response.answer


@pytest.mark.asyncio
async def test_streaming_identity_response_is_complete_and_provider_free() -> None:
    router = ModelRouter(adapters=(UnexpectedProvider(),))
    deltas = [
        delta
        async for delta in router.stream_answer(
            message="Who are you?",
            history=[],
        )
    ]

    assert [delta.kind for delta in deltas] == ["token", "done"]
    assert "native intelligence" in deltas[0].content
    assert all(
        delta.model == "native-product-identity-v1"
        for delta in deltas
    )
