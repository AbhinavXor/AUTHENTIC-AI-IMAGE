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
from schemas.artifact_jobs import ArtifactJobCreateRequest


def build_request(
    *,
    prompt: str = "Create a professional operational report.",
    idempotency_key: str | None = None,
) -> ArtifactJobCreateRequest:
    return ArtifactJobCreateRequest(
        prompt=prompt,
        format="pdf",
        title="Artifact Job Test",
        tone="professional",
        length="brief",
        language="English",
        source_snapshot={
            "kind": "explicit_prompt",
            "summary": "Professional operational report",
            "content": "Operational report with controlled validation and audit requirements.",
            "confidence": 1.0,
        },
        idempotency_key=idempotency_key,
    )


def build_store(
    root_directory: Path,
    *,
    maximum_queued_jobs: int = 10,
) -> ArtifactJobStore:
    return ArtifactJobStore(
        root_directory=root_directory,
        retention_hours=1,
        maximum_queued_jobs=maximum_queued_jobs,
        access_token_bytes=32,
        maximum_error_characters=200,
    )


def test_job_store_protects_token_idempotency_and_lifecycle(
    tmp_path: Path,
) -> None:
    store = build_store(tmp_path / "jobs")
    request = build_request(
        idempotency_key="job-create-controlled-0001"
    )

    created, access_token = store.create(request)
    replayed, replayed_token = store.create(request)

    assert replayed.job_id == created.job_id
    assert replayed_token == access_token
    assert access_token not in (
        tmp_path / "jobs" / created.job_id / "job.json"
    ).read_text(encoding="utf-8")

    with pytest.raises(ArtifactJobConflictError):
        store.create(
            build_request(
                prompt="Create a different report.",
                idempotency_key="job-create-controlled-0001",
            )
        )

    with pytest.raises(ArtifactJobAccessError):
        store.get(created.job_id, "incorrect-token")

    running = store.update(
        created.job_id,
        status="running",
        progress_percent=40,
        stage="Rendering document",
    )
    assert running.status == "running"

    cancelled = store.cancel(
        created.job_id,
        access_token,
    )
    assert cancelled.status == "cancelled"
    assert cancelled.progress_percent == 40

    assert store.delete(
        created.job_id,
        access_token,
    ) is True

    with pytest.raises(ArtifactJobNotFoundError):
        store.get_internal(created.job_id)


def test_job_store_enforces_capacity_and_recovers_interrupted(
    tmp_path: Path,
) -> None:
    store = build_store(
        tmp_path / "jobs",
        maximum_queued_jobs=1,
    )
    first, _ = store.create(
        build_request(prompt="Create the first report.")
    )

    with pytest.raises(ArtifactJobCapacityError):
        store.create(
            build_request(prompt="Create the second report.")
        )

    recovered_count = store.recover_interrupted_jobs()
    recovered = store.get_internal(first.job_id)
    assert recovered_count == 1
    assert recovered.status == "failed"
    assert recovered.progress_percent == 100


class FakeJobRunner:
    def __init__(self) -> None:
        self.submitted_job_ids: list[str] = []
        self.cancelled_job_ids: list[str] = []

    def submit(self, job_id: str) -> None:
        if job_id not in self.submitted_job_ids:
            self.submitted_job_ids.append(job_id)

    def cancel(self, job_id: str) -> None:
        self.cancelled_job_ids.append(job_id)


class AllowAllRateLimiter:
    def check(self, _: str) -> None:
        return None


def test_artifact_job_api_idempotency_token_cancel_and_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = build_store(tmp_path / "jobs")
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

    payload = build_request(
        idempotency_key="job-api-controlled-0001"
    ).model_dump(mode="json")
    create_response = client.post(
        "/api/v1/artifacts/jobs",
        headers={"Idempotency-Key": "job-api-controlled-0001"},
        json=payload,
    )
    assert create_response.status_code == 202, create_response.text
    created = create_response.json()
    job_id = created["job_id"]
    token = created["access_token"]

    replay_response = client.post(
        "/api/v1/artifacts/jobs",
        headers={"Idempotency-Key": "job-api-controlled-0001"},
        json=payload,
    )
    assert replay_response.status_code == 202
    assert replay_response.json()["job_id"] == job_id
    assert runner.submitted_job_ids == [job_id]

    assert client.get(
        f"/api/v1/artifacts/jobs/{job_id}"
    ).status_code == 401
    assert client.get(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={"X-Artifact-Job-Token": "incorrect"},
    ).status_code == 403

    status_response = client.get(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={"X-Artifact-Job-Token": token},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"

    cancel_response = client.post(
        f"/api/v1/artifacts/jobs/{job_id}/cancel",
        headers={"X-Artifact-Job-Token": token},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    assert runner.cancelled_job_ids == [job_id]

    delete_response = client.delete(
        f"/api/v1/artifacts/jobs/{job_id}",
        headers={"X-Artifact-Job-Token": token},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted"] is True
