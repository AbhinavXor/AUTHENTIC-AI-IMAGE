from dataclasses import dataclass

from ai.task_classifier import TaskCategory
from core.cloudflare_settings import cloudflare_settings
from core.config import settings
from core.gemini_settings import gemini_settings
from core.openrouter_settings import openrouter_settings
from core.sambanova_settings import sambanova_settings


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
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "fast_chat": (
        "groq",
        "gemini",
        "cloudflare",
        "openrouter",
    ),
    "deep_reasoning": (
        "groq",
        "gemini",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "coding": (
        "groq",
        "gemini",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "mathematics": (
        "groq",
        "gemini",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "physics": (
        "groq",
        "gemini",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "chemistry": (
        "groq",
        "gemini",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "biology": (
        "gemini",
        "groq",
        "cloudflare",
        "sambanova",
        "openrouter",
    ),
    "research": (
        "gemini",
        "groq",
        "cloudflare",
        "sambanova",
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
        if category == "fast_chat":
            return _unique(
                [
                    gemini_settings.fast_model,
                    gemini_settings.quality_model,
                    gemini_settings.fallback_model,
                    gemini_settings.preview_model,
                ]
            )

        return _unique(
            [
                gemini_settings.quality_model,
                gemini_settings.fallback_model,
                gemini_settings.preview_model,
                gemini_settings.fast_model,
            ]
        )

    if provider == "cloudflare":
        if category == "fast_chat":
            return _unique(
                [
                    cloudflare_settings.fast_model,
                    cloudflare_settings.fallback_model,
                    cloudflare_settings.quality_model,
                ]
            )

        return _unique(
            [
                cloudflare_settings.quality_model,
                cloudflare_settings.fallback_model,
                cloudflare_settings.fast_model,
            ]
        )

    if provider == "sambanova":
        if category in {
            "coding",
            "fast_chat",
        }:
            return _unique(
                [
                    sambanova_settings.fallback_model,
                    sambanova_settings.quality_model,
                ]
            )

        return _unique(
            [
                sambanova_settings.quality_model,
                sambanova_settings.fallback_model,
            ]
        )

    if provider == "openrouter":
        return _unique(
            [
                openrouter_settings.selected_model,
                openrouter_settings.free_model,
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
        "cloudflare",
        "sambanova",
        "openrouter",
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
