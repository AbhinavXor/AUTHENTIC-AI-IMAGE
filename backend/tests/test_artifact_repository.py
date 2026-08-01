from __future__ import annotations

from pathlib import Path

import pytest

from artifacts.models import (
    ArtifactDocument,
    ArtifactSection,
    ParagraphBlock,
)
from artifacts.repository import (
    ArtifactAccessError,
    ArtifactConflictError,
    ArtifactRepository,
)
from artifacts.storage import ArtifactStorage


def build_document(title: str, body: str) -> ArtifactDocument:
    return ArtifactDocument(
        title=title,
        subtitle=None,
        author="Authentic AI",
        sections=(
            ArtifactSection(
                title="Summary",
                level=1,
                blocks=(ParagraphBlock(text=body),),
            ),
        ),
    )


def test_repository_lifecycle_access_versioning_and_idempotency(
    tmp_path: Path,
) -> None:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=20 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )

    first = storage.create(
        build_document(
            "Risk Review",
            "This is a sufficiently detailed first version of the risk review document used to validate version storage and access controls.",
        ),
        format="pdf",
        filename="Risk Review.pdf",
    )
    created = repository.register_new(
        first,
        title="Risk Review",
        source_content="# Risk Review\n\nInitial content",
        specification={"title": "Risk Review", "format": "pdf"},
        source_snapshot={"kind": "explicit_prompt", "summary": "Risk review"},
        validation={"status": "passed", "issues": []},
        page_or_slide_count=2,
        idempotency_key="create-risk-review-0001",
        operation_fingerprint="fingerprint-create",
    )
    token = created.access_token
    assert token is not None

    with pytest.raises(ArtifactAccessError):
        repository.get(created.record.artifact_id, "wrong-token")

    replay = repository.resolve_creation(
        idempotency_key="create-risk-review-0001",
        fingerprint="fingerprint-create",
    )
    assert replay is not None
    assert replay.record.artifact_id == created.record.artifact_id
    assert replay.access_token == token

    with pytest.raises(ArtifactConflictError):
        repository.resolve_creation(
            idempotency_key="create-risk-review-0001",
            fingerprint="different-fingerprint",
        )

    renamed = repository.rename(
        created.record.artifact_id,
        token,
        display_name="Final Risk Review.exe",
        expected_version=1,
        idempotency_key="rename-risk-review-0001",
    )
    assert renamed.record.display_name == "Final-Risk-Review.pdf"

    second = storage.create(
        build_document(
            "Risk Review",
            "This is the revised and expanded second version of the risk review with additional controls and implementation guidance.",
        ),
        format="docx",
        filename="Final Risk Review.docx",
    )
    updated = repository.add_version(
        created.record.artifact_id,
        token,
        second,
        source_content="# Risk Review\n\nRevised content",
        specification={"title": "Risk Review", "format": "docx"},
        validation={"status": "passed", "issues": []},
        page_or_slide_count=1,
        expected_version=1,
        action="exported",
        idempotency_key="export-risk-review-0001",
        operation_fingerprint="fingerprint-export",
    )

    assert updated.record.current_version == 2
    assert updated.record.version_count == 2
    assert updated.record.display_name.endswith(".docx")

    with pytest.raises(ArtifactConflictError):
        repository.rename(
            created.record.artifact_id,
            token,
            display_name="Stale.docx",
            expected_version=1,
        )

    restored = repository.restore(
        created.record.artifact_id,
        token,
        version=1,
        expected_version=2,
        idempotency_key="restore-risk-review-0001",
    )
    assert restored.record.current_version == 1
    assert restored.record.display_name.endswith(".pdf")

    events = repository.list_audit_events(
        created.record.artifact_id,
        token,
    )
    assert [event["action"] for event in events] == [
        "created",
        "renamed",
        "exported",
        "restored",
    ]
