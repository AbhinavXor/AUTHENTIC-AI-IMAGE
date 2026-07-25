from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextDocumentSettings:
    maximum_upload_bytes: int
    maximum_docx_uncompressed_bytes: int
    maximum_docx_archive_entries: int

    maximum_prompt_characters: int
    maximum_section_characters: int
    maximum_context_characters: int
    maximum_selected_sections: int
    maximum_sections: int

    minimum_usable_characters: int
    code_chunk_lines: int
    code_chunk_overlap_lines: int

    docx_extensions: frozenset[str]
    text_extensions: frozenset[str]
    markdown_extensions: frozenset[str]
    json_extensions: frozenset[str]
    source_code_extensions: frozenset[str]


text_document_settings = TextDocumentSettings(
    maximum_upload_bytes=10 * 1024 * 1024,
    maximum_docx_uncompressed_bytes=40 * 1024 * 1024,
    maximum_docx_archive_entries=2_000,

    maximum_prompt_characters=4_000,
    maximum_section_characters=10_000,
    maximum_context_characters=90_000,
    maximum_selected_sections=18,
    maximum_sections=500,

    minimum_usable_characters=20,
    code_chunk_lines=120,
    code_chunk_overlap_lines=10,

    docx_extensions=frozenset(
        {
            ".docx",
        }
    ),

    text_extensions=frozenset(
        {
            ".txt",
        }
    ),

    markdown_extensions=frozenset(
        {
            ".md",
            ".markdown",
        }
    ),

    json_extensions=frozenset(
        {
            ".json",
        }
    ),

    source_code_extensions=frozenset(
        {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rs",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".kts",
            ".sql",
            ".sh",
            ".bash",
            ".zsh",
            ".yaml",
            ".yml",
            ".toml",
            ".xml",
            ".html",
            ".htm",
            ".css",
            ".scss",
        }
    ),
)
