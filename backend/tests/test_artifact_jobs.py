from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.artifact_jobs as artifact_job_routes
from artifacts.job_store import (
    ArtifactJobAccessError,
    ArtifactJobCapacityError,
    ArtifactJobConflictError,
    ArtifactJobNotFoundError,
    ArtifactJobStore,
)
from schemas.artifact_jobs import (
    ArtifactJobCreateRequest,
)


def build_request(
    *,
    prompt: str = (
        "Create a professional operational report."
    ),
) -> ArtifactJobCreateRequest:
    return ArtifactJobCreateRequest(
        prompt=prompt,
        format="pdf",
        title="Artifact Job Test",
        tone="professional",
        length="brief",
        language="English",
    )


def build_store(
    root_directory: Path,
    *,
    maximum_queued_jobs: int = 10,
) -> ArtifactJobStore:
    return ArtifactJobStore(
        root_directory=root_directory,
        retention_hours=1,
        maximum_queued_jobs=(
            maximum_queued_jobs
        ),
        access_token_bytes=32,
        maximum_error_characters=200,
    )


def test_job_store_protects_token_and_lifecycle(
    tmp_path: Path,
) -> None:
    store = build_store(
        tmp_path / "jobs"
    )

    created, access_token = store.create(
        build_request()
    )

    assert created.status == "queued"
    assert len(created.job_id) == 32
    assert len(access_token) >= 32

    metadata_path = (
        tmp_path
        / "jobs"
        / created.job_id
        / "job.json"
    )

    metadata = metadata_path.read_text(
        encoding="utf-8",
    )

    assert access_token not in metadata

    loaded = store.get(
        created.job_id,
        access_token,
    )

    assert loaded.job_id == created.job_id

    with pytest.raises(
        ArtifactJobAccessError
    ):
        store.get(
            created.job_id,
            "incorrect-access-token",
        )

    running = store.update(
        created.job_id,
        status="running",
        progress_percent=40,
        stage="Rendering document",
    )

    assert running.status == "running"
    assert running.progress_percent == 40

    failed = store.update(
        created.job_id,
        status="failed",
        progress_percent=100,
        stage="Generation failed",
        error="Controlled test failure",
    )

    assert failed.status == "failed"
    assert failed.error == (
        "Controlled test failure"
    )

    assert store.delete(
        created.job_id,
        access_token,
    ) is True

    with pytest.raises(
        ArtifactJobNotFoundError
    ):
        store.get_internal(
            created.job_id
        )


def test_active_job_cannot_be_deleted(
    tmp_path: Path,
) -> None:
    store = build_store(
        tmp_path / "jobs"
    )

    created, access_token = store.create(
        build_request()
    )

    with pytest.raises(
        ArtifactJobConflictError
    ):
        store.delete(
            created.job_id,
            access_token,
        )


def test_job_store_enforces_capacity(
    tmp_path: Path,
) -> None:
    store = build_store(
        tmp_path / "jobs",
        maximum_queued_jobs=1,
    )

    store.create(
        build_request(
            prompt="Create the first report."
        )
    )

    with pytest.raises(
        ArtifactJobCapacityError
    ):
        store.create(
            build_request(
                prompt=(
                    "Create the second report."
                )
            )
        )


def test_interrupted_job_recovery(
    tmp_path: Path,
) -> None:
    store = build_store(
        tmp_path / "jobs"
    )

    created, _ = store.create(
        build_request()
    )

    recovered_count = (
        store.recover_interrupted_jobs()
    )

    recovered = store.get_internal(
        created.job_id
    )

    assert recovered_count == 1
    assert recovered.status == "failed"
    assert recovered.progress_percent == 100
    assert recovered.error is not None


class FakeJobRunner:
    def __init__(self) -> None:
        self.submitted_job_ids: list[str] = []

    def submit(
        self,
        job_id: str,
    ) -> None:
        self.submitted_job_ids.append(
            job_id
        )


class AllowAllRateLimiter:
    def check(
        self,
        _: str,
    ) -> None:
        return None


def test_artifact_job_api_token_and_delete_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = build_store(
        tmp_path / "jobs"
    )

    runner = FakeJobRunner()

    monkeypatch.setattr(
        artifact_job_routes,
        "get_artifact_job_store",
        lambda: store,
    )

    monkeypatch.setattr(
        artifact_job_routes,
        "get_artifact_job_runner",
        lambda: runner,
    )

    monkeypatch.setattr(
        artifact_job_routes,
        "artifact_job_rate_limiter",
        AllowAllRateLimiter(),
    )

    app = FastAPI()

    app.include_router(
        artifact_job_routes.router,
        prefix="/api/v1",
    )

    client = TestClient(app)

    create_response = client.post(
        "/api/v1/artifacts/jobs",
        json={
            "prompt": (
                "Create a professional test report."
            ),
            "format": "pdf",
            "title": "API Job Test",
            "tone": "professional",
            "length": "brief",
            "language": "English",
        },
    )

    assert create_response.status_code == 202

    create_payload = create_response.json()

    job_id = create_payload["job_id"]
    access_token = (
        create_payload["access_token"]
    )

    assert runner.submitted_job_ids == [
        job_id
    ]

    missing_token_response = client.get(
        f"/api/v1/artifacts/jobs/{job_id}"
    )

    assert (
        missing_token_response.status_code
        == 401
    )

    denied_response = client.get(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={
            "X-Artifact-Job-Token":
                "incorrect-access-token",
        },
    )

    assert denied_response.status_code == 403

    status_response = client.get(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={
            "X-Artifact-Job-Token":
                access_token,
        },
    )

    assert status_response.status_code == 200

    status_payload = status_response.json()

    assert status_payload["job_id"] == job_id
    assert status_payload["status"] == "queued"

    active_delete_response = client.delete(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={
            "X-Artifact-Job-Token":
                access_token,
        },
    )

    assert (
        active_delete_response.status_code
        == 409
    )

    store.update(
        job_id,
        status="failed",
        progress_percent=100,
        stage="Generation failed",
        error="Controlled API test failure",
    )

    delete_response = client.delete(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={
            "X-Artifact-Job-Token":
                access_token,
        },
    )

    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "job_id": job_id,
        "deleted": True,
    }
