from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from ai.spreadsheet_service import (
    SpreadsheetConfigurationError,
    SpreadsheetResponseError,
    SpreadsheetService,
    SpreadsheetValidationError,
)
from core.spreadsheet_settings import (
    spreadsheet_settings,
)
from schemas.spreadsheets import (
    SpreadsheetResponse,
)


router = APIRouter(
    prefix="/spreadsheets",
    tags=["spreadsheets"],
)


@lru_cache(maxsize=1)
def get_spreadsheet_service(
) -> SpreadsheetService:
    return SpreadsheetService()


def _validate_prompt(
    prompt: str,
) -> str:
    normalized = prompt.strip()

    if not normalized:
        return (
            "Summarize this spreadsheet, identify important "
            "metrics, missing values, duplicate rows, trends "
            "and anomalies, and cite the relevant sources."
        )

    if (
        len(normalized)
        > spreadsheet_settings
        .maximum_prompt_characters
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Spreadsheet prompt is too long."
            ),
        )

    return normalized


@router.post(
    "/analyze",
    response_model=SpreadsheetResponse,
)
async def analyze_spreadsheet(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "CSV or XLSX spreadsheet"
            ),
        ),
    ],
    prompt: Annotated[
        str,
        Form(),
    ] = (
        "Summarize this spreadsheet, identify important "
        "metrics, missing values, duplicate rows, trends "
        "and anomalies, and cite the relevant sources."
    ),
) -> SpreadsheetResponse:
    safe_filename = Path(
        file.filename
        or "spreadsheet.csv"
    ).name

    extension = Path(
        safe_filename
    ).suffix.lower()

    if (
        extension
        not in spreadsheet_settings
        .allowed_extensions
    ):
        await file.close()

        raise HTTPException(
            status_code=(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            ),
            detail=(
                "Only CSV and XLSX spreadsheets are supported."
            ),
        )

    try:
        file_bytes = await file.read(
            spreadsheet_settings
            .maximum_upload_bytes
            + 1
        )

    finally:
        await file.close()

    if not file_bytes:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Uploaded spreadsheet is empty."
            ),
        )

    if (
        len(file_bytes)
        > spreadsheet_settings
        .maximum_upload_bytes
    ):
        raise HTTPException(
            status_code=(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            ),
            detail=(
                "Spreadsheet exceeds the 20 MB limit."
            ),
        )

    normalized_prompt = _validate_prompt(
        prompt
    )

    try:
        result = (
            await get_spreadsheet_service()
            .analyze(
                file_bytes=file_bytes,
                extension=extension,
                prompt=normalized_prompt,
            )
        )

    except SpreadsheetValidationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=str(error),
        ) from error

    except SpreadsheetConfigurationError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=str(error),
        ) from error

    except SpreadsheetResponseError as error:
        raise HTTPException(
            status_code=(
                status.HTTP_502_BAD_GATEWAY
            ),
            detail=str(error),
        ) from error

    return SpreadsheetResponse(
        answer=result.answer,

        provider="gemini",
        model=result.model,

        filename=safe_filename,
        mime_type=(
            file.content_type
            or "application/octet-stream"
        ),
        size_bytes=len(
            file_bytes
        ),

        spreadsheet_type=(
            result.spreadsheet_type
        ),

        sheet_names=list(
            result.sheet_names
        ),
        sheet_count=len(
            result.sheet_names
        ),

        rows_scanned=(
            result.rows_scanned
        ),
        maximum_columns_seen=(
            result.maximum_columns_seen
        ),
        formula_count=(
            result.formula_count
        ),

        truncated=result.truncated,

        selected_sources=list(
            result.selected_sources
        ),
        citations=list(
            result.citations
        ),

        request_id=result.request_id,
        usage=result.usage,
    )
