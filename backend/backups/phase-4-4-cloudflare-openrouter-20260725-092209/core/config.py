import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env", override=True)


def _parse_origins(
    value: str,
) -> tuple[str, ...]:
    return tuple(
        origin.strip()
        for origin in value.split(",")
        if origin.strip()
    )


class Settings:
    """Application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.app_name = "Authentic AI Image API"

        self.environment = os.getenv(
            "APP_ENVIRONMENT",
            "development",
        )

        self.groq_api_key = os.getenv(
            "GROQ_API_KEY",
            "",
        ).strip()

        legacy_model = os.getenv(
            "GROQ_MODEL",
            "",
        ).strip()

        self.groq_quality_model = os.getenv(
            "GROQ_QUALITY_MODEL",
            legacy_model or "openai/gpt-oss-120b",
        ).strip()

        self.groq_fallback_model = os.getenv(
            "GROQ_FALLBACK_MODEL",
            "llama-3.3-70b-versatile",
        ).strip()

        # Compatibility alias for existing health checks.
        self.groq_model = self.groq_quality_model

        self.frontend_origins = _parse_origins(
            os.getenv(
                "FRONTEND_ORIGINS",
                (
                    "http://127.0.0.1:5173,"
                    "http://localhost:5173"
                ),
            )
        )

        self.groq_timeout_seconds = float(
            os.getenv(
                "GROQ_TIMEOUT_SECONDS",
                "45",
            )
        )

        self.maximum_history_messages = int(
            os.getenv(
                "MAXIMUM_HISTORY_MESSAGES",
                "16",
            )
        )


settings = Settings()
