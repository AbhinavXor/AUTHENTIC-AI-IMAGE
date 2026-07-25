from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentSettings:
    maximum_pdf_bytes: int
    maximum_pdf_pages: int
    maximum_prompt_characters: int

    maximum_page_characters: int
    maximum_context_characters: int
    maximum_selected_pages: int

    minimum_usable_text_characters: int

    allowed_mime_types: frozenset[str]


document_settings = DocumentSettings(
    maximum_pdf_bytes=20 * 1024 * 1024,
    maximum_pdf_pages=300,
    maximum_prompt_characters=4_000,

    maximum_page_characters=8_000,
    maximum_context_characters=80_000,
    maximum_selected_pages=16,

    minimum_usable_text_characters=40,

    allowed_mime_types=frozenset(
        {
            "application/pdf",
        }
    ),
)
