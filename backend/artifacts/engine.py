from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
from uuid import uuid4

from artifacts.docx_renderer import render_docx
from artifacts.models import (
    ArtifactDocument,
    ChartBlock,
    DiagramBlock,
    EquationBlock,
    TableBlock,
)
from artifacts.parser import sanitize_filename
from artifacts.pdf_renderer import render_pdf
from artifacts.pptx_renderer import render_pptx
from artifacts.zip_renderer import render_pdf_bundle


class ArtifactGenerationError(RuntimeError):
    """Raised when artifact rendering or finalization fails."""


class ArtifactValidationError(ValueError):
    """Raised when an artifact document is structurally invalid."""


@dataclass(frozen=True, slots=True)
class ArtifactGenerationResult:
    path: Path
    format: str
    media_type: str
    size_bytes: int
    sha256: str


Renderer = Callable[
    [ArtifactDocument, Path],
    Path,
]


_RENDERERS: dict[str, Renderer] = {
    "pdf": render_pdf,
    "docx": render_docx,
    "pptx": render_pptx,
    "zip": render_pdf_bundle,
}

_MEDIA_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
    "pptx": (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    "zip": "application/zip",
}


def supported_artifact_formats() -> tuple[str, ...]:
    return tuple(_RENDERERS)


def normalize_artifact_format(
    value: object,
) -> str:
    raw_value = getattr(
        value,
        "value",
        value,
    )

    normalized = str(
        raw_value
    ).strip().lower().lstrip(".")

    if normalized not in _RENDERERS:
        supported = ", ".join(
            supported_artifact_formats()
        )
        raise ArtifactValidationError(
            f"Unsupported artifact format: {normalized!r}. "
            f"Supported formats: {supported}."
        )

    return normalized


def validate_artifact_document(
    artifact: ArtifactDocument,
) -> None:
    if not artifact.title.strip():
        raise ArtifactValidationError(
            "Artifact title cannot be empty."
        )

    if not artifact.sections:
        raise ArtifactValidationError(
            "Artifact must contain at least one section."
        )

    if len(artifact.title) > 240:
        raise ArtifactValidationError(
            "Artifact title cannot exceed 240 characters."
        )

    for section_index, section in enumerate(
        artifact.sections,
        start=1,
    ):
        if not section.title.strip():
            raise ArtifactValidationError(
                f"Section {section_index} has an empty title."
            )

        if section.level < 1:
            raise ArtifactValidationError(
                f"Section {section_index} has an invalid heading level."
            )

        for block_index, block in enumerate(
            section.blocks,
            start=1,
        ):
            location = (
                f"section {section_index}, "
                f"block {block_index}"
            )

            if isinstance(block, TableBlock):
                if not block.columns:
                    raise ArtifactValidationError(
                        f"Table at {location} has no columns."
                    )

                expected = len(
                    block.columns
                )

                for row_index, row in enumerate(
                    block.rows,
                    start=1,
                ):
                    if len(row) != expected:
                        raise ArtifactValidationError(
                            f"Table at {location}, row {row_index} "
                            f"has {len(row)} cells; expected {expected}."
                        )

            elif isinstance(block, DiagramBlock):
                if len(block.steps) < 2:
                    raise ArtifactValidationError(
                        f"Diagram at {location} must contain at least two steps."
                    )

                if any(not step.strip() for step in block.steps):
                    raise ArtifactValidationError(
                        f"Diagram at {location} contains an empty step."
                    )

            elif isinstance(block, EquationBlock):
                if not block.expression.strip():
                    raise ArtifactValidationError(
                        f"Equation at {location} cannot be empty."
                    )

            elif isinstance(block, ChartBlock):
                if not block.labels:
                    raise ArtifactValidationError(
                        f"Chart at {location} has no labels."
                    )

                if not block.series:
                    raise ArtifactValidationError(
                        f"Chart at {location} has no data series."
                    )

                expected = len(
                    block.labels
                )

                for series in block.series:
                    if len(series.values) != expected:
                        raise ArtifactValidationError(
                            f"Chart series {series.name!r} at {location} "
                            f"has {len(series.values)} values; "
                            f"expected {expected}."
                        )


def _safe_output_name(
    *,
    title: str,
    requested_filename: str | None,
    extension: str,
) -> str:
    source_name = (
        requested_filename
        or title
    )

    source_path = Path(
        source_name
    )

    stem = sanitize_filename(
        source_path.stem
    )

    if not stem:
        stem = (
            f"artifact-{uuid4().hex[:12]}"
        )

    return f"{stem}.{extension}"


def _file_sha256(
    path: Path,
) -> str:
    digest = sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def generate_artifact(
    artifact: ArtifactDocument,
    *,
    format: object,
    output_directory: Path,
    filename: str | None = None,
    overwrite: bool = False,
) -> ArtifactGenerationResult:
    validate_artifact_document(
        artifact
    )

    normalized_format = (
        normalize_artifact_format(
            format
        )
    )

    output_directory = (
        output_directory
        .expanduser()
        .resolve()
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_name = _safe_output_name(
        title=artifact.title,
        requested_filename=filename,
        extension=normalized_format,
    )

    final_path = (
        output_directory
        / output_name
    ).resolve()

    if final_path.parent != output_directory:
        raise ArtifactValidationError(
            "Artifact output path escaped the configured directory."
        )

    if (
        final_path.exists()
        and not overwrite
    ):
        raise ArtifactGenerationError(
            f"Artifact already exists: {final_path.name}"
        )

    renderer = _RENDERERS[
        normalized_format
    ]

    try:
        with TemporaryDirectory(
            prefix=".artifact-generation-",
            dir=output_directory,
        ) as temporary_directory:
            temporary_path = (
                Path(temporary_directory)
                / output_name
            )

            rendered_path = renderer(
                artifact,
                temporary_path,
            )

            if (
                not rendered_path.exists()
                or rendered_path.stat().st_size <= 0
            ):
                raise ArtifactGenerationError(
                    "Renderer returned an empty artifact."
                )

            rendered_path.replace(
                final_path
            )

    except (
        ArtifactGenerationError,
        ArtifactValidationError,
    ):
        raise

    except Exception as error:
        raise ArtifactGenerationError(
            f"Failed to generate {normalized_format.upper()} artifact."
        ) from error

    size_bytes = (
        final_path.stat().st_size
    )

    return ArtifactGenerationResult(
        path=final_path,
        format=normalized_format,
        media_type=_MEDIA_TYPES[
            normalized_format
        ],
        size_bytes=size_bytes,
        sha256=_file_sha256(
            final_path
        ),
    )