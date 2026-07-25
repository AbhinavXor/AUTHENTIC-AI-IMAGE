import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(
    BASE_DIR / ".env",
    override=True,
)


def _boolean(
    name: str,
    default: bool,
) -> bool:
    return os.getenv(
        name,
        str(default),
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _positive_float(
    name: str,
    default: float,
) -> float:
    try:
        value = float(
            os.getenv(name, str(default))
        )
    except ValueError:
        return default

    return value if value > 0 else default


def _positive_integer(
    name: str,
    default: int,
) -> int:
    try:
        value = int(
            os.getenv(name, str(default))
        )
    except ValueError:
        return default

    return value if value > 0 else default


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    enabled: bool
    api_key: str
    base_url: str
    selected_model: str
    free_model: str
    timeout_seconds: float
    maximum_history_messages: int


openrouter_settings = OpenRouterSettings(
    enabled=_boolean(
        "OPENROUTER_ENABLED",
        False,
    ),
    api_key=os.getenv(
        "OPENROUTER_API_KEY",
        "",
    ).strip(),
    base_url=os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    ).strip().rstrip("/"),
    selected_model=os.getenv(
        "OPENROUTER_SELECTED_MODEL",
        "",
    ).strip(),
    free_model=os.getenv(
        "OPENROUTER_FREE_MODEL",
        "openrouter/free",
    ).strip(),
    timeout_seconds=_positive_float(
        "OPENROUTER_TIMEOUT_SECONDS",
        90.0,
    ),
    maximum_history_messages=_positive_integer(
        "OPENROUTER_MAXIMUM_HISTORY_MESSAGES",
        16,
    ),
)
