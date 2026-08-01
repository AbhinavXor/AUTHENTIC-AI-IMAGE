from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from artifacts.large_source import split_large_source
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import ArtifactStorage
from core.artifact_settings import artifact_settings
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.chat import ChatResponse, TokenUsage


class UnexpectedModelRouter:
    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        raise AssertionError(
            "Very large bundle generation should use deterministic preservation mode."
        )


def _service(tmp_path: Path) -> ArtifactLifecycleService:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=50 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )
    return ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )


def test_artifact_prompt_accepts_content_far_beyond_legacy_limit() -> None:
    source = "Mathematical explanation. " * 1_000
    request = ArtifactComposeRequest(
        prompt=source + "\n\nCreate a professional PDF.",
        format="pdf",
    )

    assert len(request.prompt) > 8_000
    chunks = split_large_source(request.prompt, target_characters=4_000)
    assert len(chunks) > 1
    assert "".join(chunks).replace("\n", "")


@pytest.mark.asyncio
async def test_very_large_pdf_automatically_becomes_pdf_volume_zip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        artifact_settings,
        "pdf_bundle_source_characters",
        12_000,
    )
    monkeypatch.setattr(
        artifact_settings,
        "maximum_pdf_bundle_volumes",
        4,
    )

    sections = []
    for index in range(1, 13):
        sections.append(
            "\n".join(
                [
                    f"## Chapter {index}",
                    (
                        f"Chapter {index} explains algebra, calculus, "
                        "probability, verification, examples, and limitations. "
                    )
                    * 55,
                ]
            )
        )

    source = "# Mathematics Master Document\n\n" + "\n\n".join(sections)
    assert len(source) > 12_000

    result = await _service(tmp_path).compose_and_create(
        ArtifactComposeRequest(
            prompt=(
                source
                + "\n\nOrganise all content and create a professional PDF."
            ),
            format="pdf",
            title="Mathematics Master Document",
            idempotency_key="large-pdf-bundle-test-0001",
        )
    )

    assert result.view.version.format == "zip"
    assert result.view.record.display_name.endswith(".zip")
    assert result.view.stored.path.suffix == ".zip"
    assert result.quality.error_count == 0
    assert result.quality.page_or_slide_count >= 2

    with ZipFile(result.view.stored.path) as archive:
        names = archive.namelist()
        pdf_names = [name for name in names if name.endswith(".pdf")]
        assert 2 <= len(pdf_names) <= 4
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8")
        )
        assert manifest["bundle_type"] == "multi_volume_pdf"
        assert manifest["volume_count"] == len(pdf_names)


@pytest.mark.asyncio
async def test_unstructured_large_source_still_creates_multiple_pdf_volumes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        artifact_settings,
        "pdf_bundle_source_characters",
        10_000,
    )
    monkeypatch.setattr(
        artifact_settings,
        "large_source_chunk_characters",
        3_000,
    )

    source = (
        "# One Long Mathematical Source\n\n"
        + (
            "This paragraph preserves equations, examples, assumptions, "
            "verification rules, graph requirements, and explanatory detail. "
        )
        * 260
    )
    assert len(source) > 10_000
    assert "\n## " not in source

    result = await _service(tmp_path).compose_and_create(
        ArtifactComposeRequest(
            prompt=source,
            format="pdf",
            title="One Long Mathematical Source",
            idempotency_key="unstructured-pdf-bundle-test-0001",
        )
    )

    assert result.view.version.format == "zip"
    with ZipFile(result.view.stored.path) as archive:
        pdf_names = [
            name
            for name in archive.namelist()
            if name.endswith(".pdf")
        ]
        assert len(pdf_names) >= 2
