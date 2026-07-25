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
class CloudflareSettings:
    enabled: bool
    account_id: str
    api_token: str
    base_url: str
    quality_model: str
    fast_model: str
    fallback_model: str
    timeout_seconds: float
    maximum_history_messages: int


cloudflare_settings = CloudflareSettings(
    enabled=_boolean(
        "CLOUDFLARE_ENABLED",
        False,
    ),
    account_id=os.getenv(
        "CLOUDFLARE_ACCOUNT_ID",
        "",
    ).strip(),
    api_token=os.getenv(
        "CLOUDFLARE_API_TOKEN",
        "",
    ).strip(),
    base_url=os.getenv(
        "CLOUDFLARE_BASE_URL",
        "https://api.cloudflare.com/client/v4",
    ).strip().rstrip("/"),
    quality_model=os.getenv(
        "CLOUDFLARE_QUALITY_MODEL",
        "@cf/openai/gpt-oss-120b",
    ).strip(),
    fast_model=os.getenv(
        "CLOUDFLARE_FAST_MODEL",
        "@cf/openai/gpt-oss-20b",
    ).strip(),
    fallback_model=os.getenv(
        "CLOUDFLARE_FALLBACK_MODEL",
        "@cf/meta/llama-3.1-8b-instruct",
    ).strip(),
    timeout_seconds=_positive_float(
        "CLOUDFLARE_TIMEOUT_SECONDS",
        90.0,
    ),
    maximum_history_messages=_positive_integer(
        "CLOUDFLARE_MAXIMUM_HISTORY_MESSAGES",
        16,
    ),
)
