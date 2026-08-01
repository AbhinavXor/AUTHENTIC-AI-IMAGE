from __future__ import annotations

from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.artifacts as artifact_routes
from artifacts.composer import ArtifactCompositionError
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import ArtifactStorage
from schemas.chat import ChatResponse, TokenUsage


class FakeModelRouter:
    async def answer(self, *, message: str, history: list[object]) -> ChatResponse:
        return ChatResponse(
            answer="""
# Controlled Operations Report

## Executive Summary

This controlled operations report validates artifact revision through a deterministic test provider and preserves the original operational topic.

## Controls

- Validate requests.
- Record approvals.
- Preserve version history.

## Conclusion

The revised lifecycle remains controlled and auditable.
""".strip(),
            provider="test-provider",
            model="test-model",
            request_id="api-test-request",
            usage=TokenUsage(),
        )


class AllowAllRateLimiter:
    def check(self, _: str) -> None:
        return None


def test_composition_failures_keep_actionable_422_message() -> None:
    mapped = artifact_routes._creation_http_error(
        ArtifactCompositionError(
            "The requested revision could not preserve the source content."
        )
    )
    assert mapped.status_code == 422
    assert mapped.detail == (
        "The requested revision could not preserve the source content."
    )


def build_client(
    tmp_path: Path,
    monkeypatch,
) -> TestClient:
    storage = ArtifactStorage(
        tmp_path / "binary",
        retention_hours=1,
        maximum_file_bytes=20 * 1024 * 1024,
    )
    repository = ArtifactRepository(
        storage,
        root_directory=tmp_path / "records",
    )
    lifecycle = ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=FakeModelRouter(),  # type: ignore[arg-type]
    )

    artifact_routes.get_artifact_storage.cache_clear()
    artifact_routes.get_artifact_repository.cache_clear()
    artifact_routes.get_artifact_lifecycle_service.cache_clear()
    monkeypatch.setattr(
        artifact_routes,
        "get_artifact_storage",
        lambda: storage,
    )
    monkeypatch.setattr(
        artifact_routes,
        "get_artifact_repository",
        lambda: repository,
    )
    monkeypatch.setattr(
        artifact_routes,
        "get_artifact_lifecycle_service",
        lambda: lifecycle,
    )
    monkeypatch.setattr(
        artifact_routes,
        "artifact_operation_rate_limiter",
        AllowAllRateLimiter(),
    )

    app = FastAPI()
    app.include_router(
        artifact_routes.router,
        prefix="/api/v1",
    )
    return TestClient(app)


def create_payload() -> dict[str, object]:
    return {
        "content": (
            "# Controlled Operations Report\n\n"
            "## Executive Summary\n\n"
            "This report validates a controlled artifact lifecycle with "
            "private access, durable versions, safe downloads, and audit events.\n\n"
            "## Controls\n\n"
            "- Validate every operation.\n"
            "- Preserve version history.\n"
            "- Protect access tokens.\n\n"
            "## Conclusion\n\n"
            "The lifecycle is controlled, traceable, and suitable for validation."
        ),
        "format": "pdf",
        "title": "Controlled Operations Report",
        "filename": "Controlled Operations.pdf",
        "source_snapshot": {
            "kind": "explicit_prompt",
            "summary": "Controlled operations artifact lifecycle",
            "content": "Controlled operations, private access, version history and audit events.",
            "confidence": 1.0,
        },
        "idempotency_key": "api-create-controlled-0001",
    }


def test_design_only_revision_changes_the_rendered_architecture(
    tmp_path: Path,
    monkeypatch,
) -> None:
    payload = create_payload()
    payload["idempotency_key"] = "api-create-design-variation-0001"

    with build_client(tmp_path, monkeypatch) as client:
        created_response = client.post(
            "/api/v1/artifacts/generate",
            headers={"Idempotency-Key": "api-create-design-variation-0001"},
            json=payload,
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()
        artifact_id = created["artifact_id"]
        token = created["access_token"]

        version_one = client.get(
            f"/api/v1/artifacts/{artifact_id}/download?version=1",
            headers={"X-Artifact-Token": token},
        )
        assert version_one.status_code == 200

        revised_response = client.post(
            f"/api/v1/artifacts/{artifact_id}/revisions",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-revise-design-variation-0001",
            },
            json={
                "instruction": "Isko best professional design me final kar do.",
                "expected_version": 1,
                "idempotency_key": "api-revise-design-variation-0001",
            },
        )
        assert revised_response.status_code == 201, revised_response.text
        assert revised_response.json()["version"] == 2

        version_two = client.get(
            f"/api/v1/artifacts/{artifact_id}/download?version=2",
            headers={"X-Artifact-Token": token},
        )
        assert version_two.status_code == 200
        assert version_one.content != version_two.content

        metadata = client.get(
            f"/api/v1/artifacts/{artifact_id}",
            headers={"X-Artifact-Token": token},
        ).json()
        assert metadata["version"] == 2


def test_full_artifact_api_lifecycle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        created_response = client.post(
            "/api/v1/artifacts/generate",
            headers={"Idempotency-Key": "api-create-controlled-0001"},
            json=create_payload(),
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()
        artifact_id = created["artifact_id"]
        token = created["access_token"]

        assert created["version"] == 1
        assert created["filename"] == "Controlled-Operations.pdf"
        assert created["validation"]["status"] in {
            "passed",
            "passed_with_warnings",
        }

        assert client.get(
            f"/api/v1/artifacts/{artifact_id}"
        ).status_code == 401
        assert client.get(
            f"/api/v1/artifacts/{artifact_id}",
            headers={"X-Artifact-Token": "wrong-token"},
        ).status_code == 403

        metadata_response = client.get(
            f"/api/v1/artifacts/{artifact_id}",
            headers={"X-Artifact-Token": token},
        )
        assert metadata_response.status_code == 200

        source_response = client.get(
            f"/api/v1/artifacts/{artifact_id}/source",
            headers={"X-Artifact-Token": token},
        )
        assert source_response.status_code == 200
        source_payload = source_response.json()
        assert source_payload["recovered_from"] == "source_snapshot"
        assert "Controlled operations" in source_payload["content"]
        assert source_payload["version"] == 1

        rename_response = client.patch(
            f"/api/v1/artifacts/{artifact_id}",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-rename-controlled-0001",
            },
            json={
                "filename": "Final Controlled Operations.exe",
                "expected_version": 1,
                "idempotency_key": "api-rename-controlled-0001",
            },
        )
        assert rename_response.status_code == 200
        assert rename_response.json()["filename"] == "Final-Controlled-Operations.pdf"

        revise_response = client.post(
            f"/api/v1/artifacts/{artifact_id}/revisions",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-revise-controlled-0001",
            },
            json={
                "instruction": "Make the controls more concise.",
                "expected_version": 1,
                "idempotency_key": "api-revise-controlled-0001",
            },
        )
        assert revise_response.status_code == 201, revise_response.text
        assert revise_response.json()["version"] == 2

        export_response = client.post(
            f"/api/v1/artifacts/{artifact_id}/exports",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-export-controlled-0001",
            },
            json={
                "format": "docx",
                "expected_version": 2,
                "idempotency_key": "api-export-controlled-0001",
            },
        )
        assert export_response.status_code == 201, export_response.text
        assert export_response.json()["version"] == 3
        assert export_response.json()["format"] == "docx"

        versions_response = client.get(
            f"/api/v1/artifacts/{artifact_id}/versions",
            headers={"X-Artifact-Token": token},
        )
        assert versions_response.status_code == 200
        versions = versions_response.json()["versions"]
        assert len(versions) == 3
        assert all("download_url" in version for version in versions)

        historical_download = client.get(
            f"/api/v1/artifacts/{artifact_id}/download?version=1",
            headers={"X-Artifact-Token": token},
        )
        assert historical_download.status_code == 200
        assert historical_download.content.startswith(b"%PDF-")
        assert "-v1.pdf" in historical_download.headers["content-disposition"]

        restore_response = client.post(
            f"/api/v1/artifacts/{artifact_id}/restore",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-restore-controlled-0001",
            },
            json={
                "version": 1,
                "expected_version": 3,
                "idempotency_key": "api-restore-controlled-0001",
            },
        )
        assert restore_response.status_code == 200
        assert restore_response.json()["version"] == 1

        duplicate_response = client.post(
            f"/api/v1/artifacts/{artifact_id}/duplicate",
            headers={
                "X-Artifact-Token": token,
                "Idempotency-Key": "api-duplicate-controlled-0001",
            },
            json={
                "filename": "Controlled Operations Copy.pdf",
                "expected_version": 1,
                "idempotency_key": "api-duplicate-controlled-0001",
            },
        )
        assert duplicate_response.status_code == 201, duplicate_response.text
        assert duplicate_response.json()["artifact_id"] != artifact_id

        audit_response = client.get(
            f"/api/v1/artifacts/{artifact_id}/audit",
            headers={"X-Artifact-Token": token},
        )
        assert audit_response.status_code == 200
        actions = [
            event["action"]
            for event in audit_response.json()["events"]
        ]
        assert actions == ["created", "renamed", "revised", "exported", "restored"]

        stale_response = client.patch(
            f"/api/v1/artifacts/{artifact_id}",
            headers={"X-Artifact-Token": token},
            json={
                "filename": "Stale.pdf",
                "expected_version": 3,
            },
        )
        assert stale_response.status_code == 409

        deletion_response = client.delete(
            f"/api/v1/artifacts/{artifact_id}",
            headers={"X-Artifact-Token": token},
        )
        assert deletion_response.status_code == 200
        assert deletion_response.json()["deleted"] is True


def test_artifact_source_recovery_falls_back_from_compact_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        payload = create_payload()
        payload["idempotency_key"] = "api-create-compact-preview-0001"

        created_response = client.post(
            "/api/v1/artifacts/generate",
            headers={
                "Idempotency-Key": "api-create-compact-preview-0001"
            },
            json=payload,
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()

        record_path = (
            tmp_path
            / "records"
            / created["artifact_id"]
            / "artifact.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["source_snapshot"] = {
            "kind": "conversation",
            "summary": "Compact mathematics preview",
            "content": (
                "Beginning of source.\n\n"
                "[Large source preserved for document generation: "
                "20,000 middle characters hidden in chat preview]\n\n"
                "End of source."
            ),
            "message_ids": [],
            "attachment_names": [],
            "confidence": 0.8,
        }
        record_path.write_text(
            json.dumps(record),
            encoding="utf-8",
        )

        source_response = client.get(
            f"/api/v1/artifacts/{created['artifact_id']}/source",
            headers={"X-Artifact-Token": created["access_token"]},
        )
        assert source_response.status_code == 200
        source_payload = source_response.json()
        assert source_payload["recovered_from"] == "artifact_version"
        assert "Controlled Operations Report" in source_payload["content"]
        assert "hidden in chat preview" not in source_payload["content"]



def test_artifact_source_recovery_prefers_clean_version_over_polluted_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with build_client(tmp_path, monkeypatch) as client:
        payload = create_payload()
        payload["idempotency_key"] = "api-create-polluted-snapshot-0001"
        created_response = client.post(
            "/api/v1/artifacts/generate",
            headers={"Idempotency-Key": "api-create-polluted-snapshot-0001"},
            json=payload,
        )
        assert created_response.status_code == 201, created_response.text
        created = created_response.json()

        record_path = (
            tmp_path / "records" / created["artifact_id"] / "artifact.json"
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["source_snapshot"] = {
            "kind": "conversation",
            "summary": "Polluted artifact recovery source",
            "content": (
                "# Add a Comparison Table and a New Version\n\n"
                "## Executive Overview\n\nSome content.\n\n"
                "[Large source preserved for document generation: 4,112 "
                "middle characters hidden in the chat preview]\n\n"
                "## Document Production Requirements\n\n"
                "- Create a PDF.\n- Preserve all chapters.\n"
            ),
            "message_ids": [],
            "attachment_names": [],
            "confidence": 0.8,
        }
        record_path.write_text(json.dumps(record), encoding="utf-8")

        response = client.get(
            f"/api/v1/artifacts/{created['artifact_id']}/source",
            headers={"X-Artifact-Token": created["access_token"]},
        )
        assert response.status_code == 200, response.text
        recovered = response.json()
        assert recovered["recovered_from"] == "artifact_version"
        assert "Controlled Operations Report" in recovered["content"]
        assert "hidden in the chat preview" not in recovered["content"]
        assert "Document Production Requirements" not in recovered["content"]
