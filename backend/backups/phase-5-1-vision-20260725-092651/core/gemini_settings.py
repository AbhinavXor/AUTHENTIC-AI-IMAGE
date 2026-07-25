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
    raw_value = os.getenv(
        name,
        str(default),
    )

    try:
        value = float(raw_value)
    except ValueError:
        return default

    return value if value > 0 else default


def _positive_integer(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(
        name,
        str(default),
    )

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return value if value > 0 else default


@dataclass(frozen=True, slots=True)
class GeminiSettings:
    api_key: str
    quality_model: str
    fallback_model: str
    fast_model: str
    preview_model: str
    timeout_seconds: float
    maximum_history_messages: int


gemini_settings = GeminiSettings(
    api_key=os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip(),
    quality_model=os.getenv(
        "GEMINI_QUALITY_MODEL",
        "gemini-3.6-flash",
    ).strip(),
    fallback_model=os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.5-flash",
    ).strip(),
    fast_model=os.getenv(
        "GEMINI_FAST_MODEL",
        "gemini-3.5-flash-lite",
    ).strip(),
    preview_model=os.getenv(
        "GEMINI_PREVIEW_MODEL",
        "gemini-3-flash-preview",
    ).strip(),
    timeout_seconds=_positive_float(
        "GEMINI_TIMEOUT_SECONDS",
        60.0,
    ),
    maximum_history_messages=_positive_integer(
        "GEMINI_MAXIMUM_HISTORY_MESSAGES",
        16,
    ),
)
