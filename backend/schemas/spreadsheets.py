from typing import Literal

from pydantic import BaseModel

from schemas.chat import TokenUsage


SpreadsheetType = Literal[
    "csv",
    "xlsx",
]


SpreadsheetSourceKind = Literal[
    "profile",
    "csv_rows",
    "sheet_rows",
]


class SpreadsheetCitation(BaseModel):
    source_id: str
    label: str
    kind: SpreadsheetSourceKind


class SpreadsheetResponse(BaseModel):
    answer: str

    provider: str
    model: str

    filename: str
    mime_type: str
    size_bytes: int

    spreadsheet_type: SpreadsheetType

    sheet_names: list[str]
    sheet_count: int

    rows_scanned: int
    maximum_columns_seen: int
    formula_count: int

    truncated: bool

    selected_sources: list[str]
    citations: list[
        SpreadsheetCitation
    ]

    request_id: str | None = None
    usage: TokenUsage
