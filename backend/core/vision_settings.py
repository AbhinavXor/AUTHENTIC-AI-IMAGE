from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisionSettings:
    maximum_image_bytes: int
    maximum_image_pixels: int
    maximum_prompt_characters: int
    allowed_mime_types: frozenset[str]


vision_settings = VisionSettings(
    maximum_image_bytes=10 * 1024 * 1024,
    maximum_image_pixels=40_000_000,
    maximum_prompt_characters=4_000,
    allowed_mime_types=frozenset(
        {
            "image/jpeg",
            "image/png",
            "image/webp",
        }
    ),
)
