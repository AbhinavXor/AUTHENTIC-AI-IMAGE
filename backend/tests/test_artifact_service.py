from __future__ import annotations

from pathlib import Path

import pytest

from artifacts.composer import ArtifactCompositionError
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import ArtifactStorage
from schemas.artifact_composer import ArtifactComposeRequest
from schemas.artifacts import (
    ArtifactDuplicateRequest,
    ArtifactRevisionRequest,
    ArtifactSourceSnapshot,
)
from schemas.chat import ChatResponse, TokenUsage


class FakeModelRouter:
    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        if "REVISION INSTRUCTION" in message:
            answer = """
# Serenya Logo Review

## Executive Summary

This revised document explains the current Serenya logo and adds a concise implementation recommendation for the brand team.

## Current Design

The logo uses a glossy spherical form, a curved S-shaped wave, and a violet, magenta, cyan, and blue gradient.

## Recommendations

- Prepare a simplified vector master.
- Validate contrast in light and dark interfaces.
- Preserve the recognizable S-shaped motion.

## Conclusion

The revised direction keeps the distinctive identity while improving scalability across product surfaces.
"""
        else:
            answer = """
# Serenya Logo Analysis

## Executive Summary

The Serenya logo uses a glossy spherical form and a curved S-shaped wave to communicate intelligence, motion, and continuity.

## Current Design

The visual identity combines violet, magenta, cyan, and deep blue gradients with translucent layering and a clean white background.

## Design Assessment

| Element | Strength | Risk |
|---|---|---|
| Sphere | Recognizable app icon | Detail may reduce at small sizes |
| Gradient | Premium and expressive | Requires controlled contrast |
| S wave | Strong brand cue | Needs a simplified vector variant |

## Recommendations

- Create a flat vector master for small interfaces.
- Prepare light and dark background variants.
- Retain the S-shaped motion as the core identifier.

## Conclusion

The identity is distinctive and can become more scalable through a controlled responsive logo system.
"""

        return ChatResponse(
            answer=answer.strip(),
            provider="test-provider",
            model="test-model",
            request_id="test-request",
            usage=TokenUsage(),
        )


def build_service(tmp_path: Path) -> ArtifactLifecycleService:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=20 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )
    return ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=FakeModelRouter(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_generic_create_without_source_is_rejected(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    with pytest.raises(ArtifactCompositionError):
        await service.compose_and_create(
            ArtifactComposeRequest(
                prompt="create a pdf",
                format="pdf",
            )
        )


@pytest.mark.asyncio
async def test_compose_revise_export_duplicate_lifecycle(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    request = ArtifactComposeRequest(
        prompt="Create a professional PDF from the Serenya logo analysis.",
        format="pdf",
        tone="professional",
        length="brief",
        source_snapshot=ArtifactSourceSnapshot(
            kind="previous_response",
            summary="Serenya logo analysis",
            content=(
                "The Serenya logo is a glossy sphere with an S-shaped wave, "
                "violet, magenta, cyan, and deep blue gradients."
            ),
            confidence=0.98,
        ),
        idempotency_key="compose-serenya-logo-0001",
    )

    created = await service.compose_and_create(request)
    token = created.view.access_token
    assert token is not None
    assert "Serenya" in created.view.record.title
    assert created.view.record.current_version == 1
    assert created.quality.error_count == 0

    revised = await service.revise(
        created.view.record.artifact_id,
        token,
        ArtifactRevisionRequest(
            instruction="Make it shorter and keep the recommendations.",
            expected_version=1,
            idempotency_key="revise-serenya-logo-0001",
        ),
    )
    assert revised.view.record.current_version == 2
    assert revised.view.version.format == "pdf"

    exported = service.export(
        created.view.record.artifact_id,
        token,
        format="docx",
        expected_version=2,
        idempotency_key="export-serenya-logo-0001",
    )
    assert exported.view.record.current_version == 3
    assert exported.view.version.format == "docx"

    duplicate = service.duplicate(
        created.view.record.artifact_id,
        token,
        request=ArtifactDuplicateRequest(
            filename="Serenya Logo Review Copy.docx",
            expected_version=3,
            idempotency_key="duplicate-serenya-logo-0001",
        ),
    )
    assert duplicate.view.record.artifact_id != created.view.record.artifact_id
    assert duplicate.view.access_token is not None
    assert duplicate.view.record.display_name == "Serenya-Logo-Review-Copy.docx"


@pytest.mark.asyncio
async def test_source_visualization_is_preserved_when_model_omits_it(
    tmp_path: Path,
) -> None:
    service = build_service(tmp_path)
    chart_block = """
```authentic-chart
{"version":"1.0","title":"Manual versus Automated Workload","description":"Comparison of modeled processing hours.","source":"User-provided scenario","estimated":false,"limitations":[],"option":{"xAxis":{"type":"category","data":["Manual","Automated"]},"yAxis":{"type":"value","name":"Hours"},"series":[{"name":"Hours","type":"bar","data":[100,35]}]},"table":{"columns":["Mode","Hours"],"rows":[["Manual",100],["Automated",35]]}}
```
""".strip()

    created = await service.compose_and_create(
        ArtifactComposeRequest(
            prompt="Create a professional PDF from the workload analysis and include the graph.",
            format="pdf",
            source_snapshot=ArtifactSourceSnapshot(
                kind="previous_response",
                summary="University automation workload comparison",
                content=(
                    "Automation can reduce repetitive processing workload.\n\n"
                    + chart_block
                ),
                confidence=0.99,
            ),
            idempotency_key="compose-chart-preservation-0001",
        )
    )

    assert "```authentic-chart" in created.source_content
    assert "Manual versus Automated Workload" in created.source_content
    assert created.quality.error_count == 0
    assert created.view.stored.path.is_file()


@pytest.mark.asyncio
async def test_create_and_design_revision_repair_visible_markup_but_preserve_code(
    tmp_path: Path,
) -> None:
    service = build_service(tmp_path)
    request = ArtifactComposeRequest(
        prompt=(
            "Create a polished BTech project report and automatically select "
            "the most suitable professional architecture."
        ),
        format="pdf",
        title="Campus Systems Project",
        filename="Campus Systems Project.pdf",
        source_snapshot=ArtifactSourceSnapshot(
            kind="explicit_prompt",
            summary="Campus systems BTech project report",
            content=(
                "A campus systems project with a technical implementation "
                "example and faculty-ready conclusions."
            ),
            confidence=1.0,
        ),
        idempotency_key="create-markup-repair-0001",
    )
    malformed_provider_draft = """```markdown
# Campus Systems Project

<div><h2>Executive Summary</h2><p>The **campus platform improves <strong>service reliability</strong>.</p></div>

The proposed system centralizes student requests, validates each submitted
record, routes approved work to the responsible department, and preserves an
auditable completion history for faculty and operations teams.

## Implementation Example

```html
<section class="status">**literal source-code token**</section>
```

<table><tr><th>Measure</th><th>Result</th></tr><tr><td>Availability</td><td>Improved</td></tr></table>

## Conclusion

The project is complete and ready for faculty review.**

Its final design presents the implementation, measurable operational result,
and technical evidence in a structure suitable for a BTech submission.
```"""

    created = service.create_from_markdown(
        request,
        source_content=malformed_provider_draft,
        provider="test-provider",
        model="test-model",
        request_id="markup-repair-create",
    )

    assert created.quality.error_count == 0, created.quality.to_dict()
    assert created.view.record.current_version == 1
    assert created.view.stored.path.is_file()
    assert "<div" not in created.source_content
    assert "<table" not in created.source_content
    assert "```html" in created.source_content
    assert '<section class="status">' in created.source_content

    token = created.view.access_token
    assert token is not None
    revised = await service.revise(
        created.view.record.artifact_id,
        token,
        ArtifactRevisionRequest(
            instruction="Isko best professional design me final kar do.",
            expected_version=1,
            idempotency_key="revise-markup-repair-0001",
        ),
    )

    assert revised.quality.error_count == 0, revised.quality.to_dict()
    assert revised.view.record.current_version == 2
    assert revised.view.stored.path.is_file()
    assert "```html" in revised.source_content
    assert '<section class="status">' in revised.source_content
