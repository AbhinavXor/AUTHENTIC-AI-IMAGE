from dataclasses import dataclass
from typing import Literal

from core.config import settings


TaskCategory = Literal[
    "general",
    "fast_chat",
    "deep_reasoning",
    "coding",
    "mathematics",
    "physics",
    "chemistry",
    "biology",
    "research",
]


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    """Static model metadata used by future routing decisions."""

    provider: str
    model_id: str
    priority: int
    capabilities: frozenset[TaskCategory]
    supports_streaming: bool = True
    free_first: bool = True


def get_model_registry() -> tuple[ModelDefinition, ...]:
    """Return the currently registered model definitions."""

    definitions: list[ModelDefinition] = []

    if settings.groq_quality_model:
        definitions.append(
            ModelDefinition(
                provider="groq",
                model_id=settings.groq_quality_model,
                priority=10,
                capabilities=frozenset(
                    {
                        "general",
                        "deep_reasoning",
                        "coding",
                        "mathematics",
                        "physics",
                        "chemistry",
                        "biology",
                        "research",
                    }
                ),
            )
        )

    if (
        settings.groq_fallback_model
        and settings.groq_fallback_model
        != settings.groq_quality_model
    ):
        definitions.append(
            ModelDefinition(
                provider="groq",
                model_id=settings.groq_fallback_model,
                priority=20,
                capabilities=frozenset(
                    {
                        "general",
                        "fast_chat",
                        "coding",
                        "mathematics",
                        "physics",
                        "chemistry",
                        "biology",
                    }
                ),
            )
        )

    return tuple(
        sorted(
            definitions,
            key=lambda item: item.priority,
        )
    )
