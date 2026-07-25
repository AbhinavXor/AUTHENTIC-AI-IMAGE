from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpreadsheetSettings:
    maximum_upload_bytes: int

    maximum_xlsx_uncompressed_bytes: int
    maximum_xlsx_archive_entries: int

    maximum_worksheets: int
    maximum_total_rows: int
    maximum_rows_per_sheet: int
    maximum_columns: int

    maximum_prompt_characters: int
    maximum_cell_characters: int
    maximum_context_columns: int

    row_chunk_size: int
    maximum_sources: int
    maximum_selected_sources: int
    maximum_context_characters: int

    maximum_parse_seconds: float

    allowed_extensions: frozenset[str]


spreadsheet_settings = SpreadsheetSettings(
    maximum_upload_bytes=20 * 1024 * 1024,

    maximum_xlsx_uncompressed_bytes=200 * 1024 * 1024,
    maximum_xlsx_archive_entries=5_000,

    maximum_worksheets=30,
    maximum_total_rows=100_000,
    maximum_rows_per_sheet=50_000,
    maximum_columns=100,

    maximum_prompt_characters=4_000,
    maximum_cell_characters=300,
    maximum_context_columns=40,

    row_chunk_size=60,
    maximum_sources=5_000,
    maximum_selected_sources=20,
    maximum_context_characters=100_000,

    maximum_parse_seconds=35.0,

    allowed_extensions=frozenset(
        {
            ".csv",
            ".xlsx",
        }
    ),
)
