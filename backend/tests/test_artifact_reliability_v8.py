from __future__ import annotations

from pathlib import Path

import pytest

from artifacts.composer import compose_artifact_draft
from artifacts.parser import parse_artifact_document
from artifacts.quality import normalize_markdown_source, validate_document_quality
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.source_fidelity import (
    normalize_recovered_artifact_markdown,
    organize_source_losslessly,
    recovered_source_contamination,
    resolve_source_fidelity,
    sanitize_recovered_source_payload,
)
from artifacts.storage import ArtifactStorage
from schemas.artifact_composer import ArtifactComposeRequest


FIXTURE = Path(__file__).parent / "fixtures" / "mathematics_authoritative_source.txt"


class UnexpectedModelRouter:
    async def answer(self, *, message: str, history: list[object]):
        raise AssertionError("Recovered artifact repair must remain deterministic.")


def _canonical() -> str:
    source = FIXTURE.read_text(encoding="utf-8")
    request = ArtifactComposeRequest(
        prompt=source,
        format="pdf",
        title="Add a Comparison Table and a New Version",
    )
    return organize_source_losslessly(
        resolve_source_fidelity(request, source),
        fallback_title=request.title or "Mathematics",
    )


def _contaminated() -> str:
    canonical = _canonical()
    canonical = canonical.replace(
        "# Mathematics: Foundations, Algebra, Calculus, Probability and Modelling",
        "# Add a Comparison Table and a New Version",
        1,
    )
    insertion = """

[Large source preserved for document generation: 4,112
middle characters hidden in the chat preview]

## Document Production Requirements

- Create a polished professional PDF.
- Preserve all chapters, equations, graphs, glossary and conclusion.
- Do not include internal instructions or preview markers.

"""
    marker = "## Source-Derived Mathematical Visualizations"
    if marker in canonical:
        canonical = canonical.replace(marker, insertion + marker, 1)
    else:
        canonical += insertion
    return canonical


def _service(tmp_path: Path) -> ArtifactLifecycleService:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=80 * 1024 * 1024,
    )
    repository = ArtifactRepository(storage, root_directory=tmp_path / "records")
    return ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )


def test_transport_and_instruction_contamination_is_removed_idempotently() -> None:
    contaminated = _contaminated()
    assert set(recovered_source_contamination(contaminated)) == {
        "command_title",
        "compact_preview",
        "internal_production_section",
    }

    cleaned = sanitize_recovered_source_payload(contaminated)
    repaired = normalize_recovered_artifact_markdown(
        cleaned,
        fallback_title="Add a Comparison Table and a New Version",
    )

    assert repaired.startswith(
        "# Mathematics: Foundations, Algebra, Calculus, Probability and Modelling"
    )
    assert "Add a Comparison Table and a New Version" not in repaired
    assert "hidden in the chat preview" not in repaired
    assert "Document Production Requirements" not in repaired
    assert "Create a polished professional PDF" not in repaired
    assert repaired.count("### 1. Mathematical Thinking") == 1
    assert repaired.count("### 37. Final Verification Checklist") == 1

    second_pass = normalize_recovered_artifact_markdown(
        repaired,
        fallback_title="Create a PDF",
    )
    assert second_pass == repaired

    artifact = parse_artifact_document(
        normalize_markdown_source(repaired),
        title=None,
        subtitle=None,
        author="Authentic AI",
    )
    quality = validate_document_quality(
        artifact,
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Recovered mathematics artifact",
            "content": repaired,
        },
    )
    assert quality.error_count == 0, quality.to_dict()


@pytest.mark.asyncio
async def test_contaminated_artifact_version_is_repaired_before_composition() -> None:
    request = ArtifactComposeRequest(
        prompt=(
            "Stored mathematics artifact ko recover karke clean professional "
            "PDF create karo."
        ),
        format="pdf",
        title="Add a Comparison Table and a New Version",
        source_snapshot={
            "kind": "artifact_version",
            "summary": "Recovered mathematics artifact",
            "content": _contaminated(),
            "message_ids": [],
            "attachment_names": [],
            "confidence": 0.92,
        },
    )

    draft = await compose_artifact_draft(
        request,
        model_router=UnexpectedModelRouter(),  # type: ignore[arg-type]
    )

    assert draft.provider == "deterministic"
    assert draft.model == "canonical-artifact-recovery-v8"
    assert draft.content.startswith(
        "# Mathematics: Foundations, Algebra, Calculus, Probability and Modelling"
    )
    assert "hidden in the chat preview" not in draft.content
    assert "Document Production Requirements" not in draft.content
    assert draft.content.count("### 37. Final Verification Checklist") == 1


@pytest.mark.asyncio
async def test_contaminated_artifact_version_renders_without_user_retry(
    tmp_path: Path,
) -> None:
    result = await _service(tmp_path).compose_and_create(
        ArtifactComposeRequest(
            prompt="Recover and re-render the stored mathematics artifact.",
            format="pdf",
            filename="Recovered-Mathematics-V8.pdf",
            title="Add a Comparison Table and a New Version",
            source_snapshot={
                "kind": "artifact_version",
                "summary": "Recovered mathematics artifact",
                "content": _contaminated(),
                "message_ids": [],
                "attachment_names": [],
                "confidence": 0.92,
            },
            idempotency_key="artifact-reliability-v8-render-0001",
        )
    )

    assert result.quality.error_count == 0, result.quality.to_dict()
    assert result.quality.page_or_slide_count >= 20
    assert "hidden in the chat preview" not in result.source_content
    assert "Document Production Requirements" not in result.source_content
    assert result.view.record.title.startswith("Mathematics:")
