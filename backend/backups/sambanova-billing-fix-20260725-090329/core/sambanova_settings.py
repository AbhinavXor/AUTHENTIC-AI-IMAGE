import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(
    BASE_DIR / ".env",
    override=True,
)


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
class SambaNovaSettings:
    api_key: str
    base_url: str
    quality_model: str
    fallback_model: str
    timeout_seconds: float
    maximum_history_messages: int


sambanova_settings = SambaNovaSettings(
    api_key=os.getenv(
        "SAMBANOVA_API_KEY",
        "",
    ).strip(),
    base_url=os.getenv(
        "SAMBANOVA_BASE_URL",
        "https://api.sambanova.ai/v1",
    ).strip().rstrip("/"),
    quality_model=os.getenv(
        "SAMBANOVA_QUALITY_MODEL",
        "gpt-oss-120b",
    ).strip(),
    fallback_model=os.getenv(
        "SAMBANOVA_FALLBACK_MODEL",
        "DeepSeek-V3.1",
    ).strip(),
    timeout_seconds=_positive_float(
        "SAMBANOVA_TIMEOUT_SECONDS",
        90.0,
    ),
    maximum_history_messages=_positive_integer(
        "SAMBANOVA_MAXIMUM_HISTORY_MESSAGES",
        16,
    ),
)
