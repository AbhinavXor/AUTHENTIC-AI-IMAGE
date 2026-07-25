from dataclasses import dataclass

from ai.task_classifier import TaskCategory
from core.config import settings


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    provider: str
    model_id: str
    priority: int
    capabilities: frozenset[TaskCategory]
    supports_streaming: bool = True
    free_first: bool = True


_DEFAULT_GROQ_FAST_MODEL = "openai/gpt-oss-20b"
_DEFAULT_GROQ_INSTANT_MODEL = "llama-3.1-8b-instant"


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
    if provider != "groq":
        return ()

    quality = settings.groq_quality_model
    fallback = settings.groq_fallback_model

    orders: dict[
        TaskCategory,
        list[str],
    ] = {
        "fast_chat": [
            _DEFAULT_GROQ_FAST_MODEL,
            _DEFAULT_GROQ_INSTANT_MODEL,
            quality,
            fallback,
        ],
        "general": [
            quality,
            _DEFAULT_GROQ_FAST_MODEL,
            fallback,
            _DEFAULT_GROQ_INSTANT_MODEL,
        ],
        "deep_reasoning": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "coding": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "mathematics": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "physics": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "chemistry": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "biology": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
        "research": [
            quality,
            fallback,
            _DEFAULT_GROQ_FAST_MODEL,
        ],
    }

    return _unique(
        orders[category]
    )


def get_model_registry() -> tuple[ModelDefinition, ...]:
    model_capabilities: dict[
        str,
        set[TaskCategory],
    ] = {}

    model_priority: dict[str, int] = {}

    categories: tuple[TaskCategory, ...] = (
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

    for category in categories:
        for index, model_id in enumerate(
            get_provider_model_order(
                "groq",
                category,
            ),
            start=1,
        ):
            model_capabilities.setdefault(
                model_id,
                set(),
            ).add(category)

            model_priority[model_id] = min(
                model_priority.get(
                    model_id,
                    index * 10,
                ),
                index * 10,
            )

    return tuple(
        sorted(
            (
                ModelDefinition(
                    provider="groq",
                    model_id=model_id,
                    priority=model_priority[
                        model_id
                    ],
                    capabilities=frozenset(
                        capabilities
                    ),
                )
                for model_id, capabilities
                in model_capabilities.items()
            ),
            key=lambda item: (
                item.priority,
                item.model_id,
            ),
        )
    )
