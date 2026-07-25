from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageGenerationSettings:
    gemini_fast_models: tuple[str, ...]
    gemini_quality_models: tuple[str, ...]

    cloudflare_model: str

    maximum_prompt_characters: int
    maximum_cloudflare_prompt_characters: int

    maximum_output_bytes: int
    maximum_image_pixels: int

    gemini_timeout_seconds: float
    cloudflare_timeout_seconds: float

    allowed_aspect_ratios: frozenset[str]
    allowed_image_sizes: frozenset[str]


image_generation_settings = (
    ImageGenerationSettings(
        gemini_fast_models=(
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
        ),

        gemini_quality_models=(
            "gemini-3-pro-image",
            "gemini-3-pro-image-preview",
            "gemini-3.1-flash-image",
            "gemini-3.1-flash-image-preview",
            "gemini-2.5-flash-image",
        ),

        cloudflare_model=(
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        ),

        maximum_prompt_characters=4_000,
        maximum_cloudflare_prompt_characters=2_048,

        maximum_output_bytes=30 * 1024 * 1024,
        maximum_image_pixels=40_000_000,

        gemini_timeout_seconds=180.0,
        cloudflare_timeout_seconds=180.0,

        allowed_aspect_ratios=frozenset(
            {
                "1:1",
                "16:9",
                "9:16",
                "4:3",
                "3:4",
                "3:2",
                "2:3",
                "5:4",
                "4:5",
                "21:9",
            }
        ),

        allowed_image_sizes=frozenset(
            {
                "1K",
                "2K",
            }
        ),
    )
)
