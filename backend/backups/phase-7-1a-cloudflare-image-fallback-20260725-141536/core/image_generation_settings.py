from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ImageGenerationSettings:
    fast_model: str
    fast_preview_model: str
    legacy_model: str

    quality_model: str
    quality_preview_model: str

    maximum_prompt_characters: int
    maximum_output_bytes: int
    maximum_image_pixels: int

    allowed_aspect_ratios: frozenset[str]
    allowed_image_sizes: frozenset[str]


image_generation_settings = (
    ImageGenerationSettings(
        fast_model=(
            "gemini-3.1-flash-image"
        ),

        fast_preview_model=(
            "gemini-3.1-flash-image-preview"
        ),

        legacy_model=(
            "gemini-2.5-flash-image"
        ),

        quality_model=(
            "gemini-3-pro-image"
        ),

        quality_preview_model=(
            "gemini-3-pro-image-preview"
        ),

        maximum_prompt_characters=4_000,
        maximum_output_bytes=(
            30 * 1024 * 1024
        ),
        maximum_image_pixels=(
            40_000_000
        ),

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
