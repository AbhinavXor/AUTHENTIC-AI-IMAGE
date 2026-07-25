from dataclasses import dataclass

from ai.task_classifier import TaskCategory
from core.config import settings
from core.gemini_settings import gemini_settings


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    provider: str
    model_id: str
    priority: int
    capabilities: frozenset[TaskCategory]
    supports_streaming: bool = True
    free_first: bool = True


_GROQ_FAST_MODEL = "openai/gpt-oss-20b"
_GROQ_INSTANT_MODEL = "llama-3.1-8b-instant"


_PROVIDER_PRIORITY: dict[
    TaskCategory,
    tuple[str, ...],
] = {
    "general": (
        "groq",
        "gemini",
        "mistral",
        "sambanova",
        "cloudflare",
        "openrouter",
    ),
    "fast_chat": (
        "groq",
        "gemini",
        "mistral",
        "cloudflare",
        "openrouter",
    ),
    "deep_reasoning": (
        "groq",
        "gemini",
        "sambanova",
        "mistral",
        "cloudflare",
        "openrouter",
    ),
    "coding": (
        "groq",
        "mistral",
        "gemini",
        "sambanova",
        "cloudflare",
        "openrouter",
    ),
    "mathematics": (
        "groq",
        "gemini",
        "sambanova",
        "mistral",
        "cloudflare",
        "openrouter",
    ),
    "physics": (
        "groq",
        "gemini",
        "sambanova",
        "mistral",
        "cloudflare",
        "openrouter",
    ),
    "chemistry": (
        "groq",
        "gemini",
        "mistral",
        "sambanova",
        "cloudflare",
        "openrouter",
    ),
    "biology": (
        "gemini",
        "groq",
        "mistral",
        "sambanova",
        "cloudflare",
        "openrouter",
    ),
    "research": (
        "gemini",
        "groq",
        "mistral",
        "sambanova",
        "cloudflare",
        "openrouter",
    ),
}


_ALL_CATEGORIES: tuple[TaskCategory, ...] = (
    "general",
    "fast_chat",
    "deep_reasoning",
    "coding",
    "mathematics",
    "physics",
    "chemistry",
    "biology",
    "research",
)


def _unique(
    values: list[str],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value
            for value in values
            if value
        )
    )


def get_provider_priority(
    category: TaskCategory,
) -> tuple[str, ...]:
    return _PROVIDER_PRIORITY[category]


def get_provider_model_order(
    provider: str,
    category: TaskCategory,
) -> tuple[str, ...]:
    if provider == "groq":
        quality = settings.groq_quality_model
        fallback = settings.groq_fallback_model

        if category == "fast_chat":
            return _unique(
                [
                    _GROQ_FAST_MODEL,
                    _GROQ_INSTANT_MODEL,
                    quality,
                    fallback,
                ]
            )

        return _unique(
            [
                quality,
                fallback,
                _GROQ_FAST_MODEL,
                _GROQ_INSTANT_MODEL,
            ]
        )

    if provider == "gemini":
        quality = gemini_settings.quality_model
        fallback = gemini_settings.fallback_model
        fast = gemini_settings.fast_model
        preview = gemini_settings.preview_model

        if category == "fast_chat":
            return _unique(
                [
                    fast,
                    quality,
                    fallback,
                    preview,
                ]
            )

        return _unique(
            [
                quality,
                fallback,
                preview,
                fast,
            ]
        )

    return ()


def get_model_registry() -> tuple[ModelDefinition, ...]:
    capabilities: dict[
        tuple[str, str],
        set[TaskCategory],
    ] = {}

    priorities: dict[
        tuple[str, str],
        int,
    ] = {}

    for provider in (
        "groq",
        "gemini",
    ):
        for category in _ALL_CATEGORIES:
            models = get_provider_model_order(
                provider,
                category,
            )

            for index, model_id in enumerate(
                models,
                start=1,
            ):
                key = (
                    provider,
                    model_id,
                )

                capabilities.setdefault(
                    key,
                    set(),
                ).add(category)

                priorities[key] = min(
                    priorities.get(
                        key,
                        index * 10,
                    ),
                    index * 10,
                )

    definitions = (
        ModelDefinition(
            provider=provider,
            model_id=model_id,
            priority=priorities[
                (
                    provider,
                    model_id,
                )
            ],
            capabilities=frozenset(
                model_capabilities
            ),
        )
        for (
            provider,
            model_id,
        ), model_capabilities in capabilities.items()
    )

    return tuple(
        sorted(
            definitions,
            key=lambda item: (
                item.provider,
                item.priority,
                item.model_id,
            ),
        )
    )
