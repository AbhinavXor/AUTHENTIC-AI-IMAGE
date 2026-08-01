from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import shutil
from dataclasses import (
    dataclass,
    replace,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from core.artifact_job_settings import (
    artifact_job_settings,
)
from schemas.artifact_composer import (
    ArtifactComposeResponse,
)
from schemas.artifact_jobs import (
    ArtifactJobCreateRequest,
    ArtifactJobStatus,
)


_JOB_FILENAME = "job.json"
_TOKEN_SECRET_FILENAME = ".token-secret"
_IDEMPOTENCY_DIRECTORY = "_idempotency"
_JOB_ID_LENGTH = 32

_ALLOWED_JOB_ID_CHARACTERS = (
    frozenset(
        "0123456789abcdef"
    )
)

_ACTIVE_STATUSES = {
    "queued",
    "running",
}

_TERMINAL_STATUSES = {
    "succeeded",
    "failed",
    "cancelled",
}

_ALLOWED_TRANSITIONS: dict[
    ArtifactJobStatus,
    set[ArtifactJobStatus],
] = {
    "queued": {
        "running",
        "failed",
        "cancelled",
    },
    "running": {
        "succeeded",
        "failed",
        "cancelled",
    },
    "succeeded": set(),
    "failed": set(),
    "cancelled": set(),
}


class ArtifactJobNotFoundError(
    FileNotFoundError
):
    """
    Raised when a background artifact
    job cannot be found.
    """


class ArtifactJobExpiredError(
    ArtifactJobNotFoundError
):
    """
    Raised when a background artifact
    job has expired.
    """


class ArtifactJobAccessError(
    PermissionError
):
    """
    Raised when a job access token
    is missing or invalid.
    """


class ArtifactJobCapacityError(
    RuntimeError
):
    """
    Raised when the background job
    queue has reached its limit.
    """


class ArtifactJobConflictError(
    RuntimeError
):
    """
    Raised when an invalid job state
    transition is requested.
    """


class ArtifactJobStorageError(
    RuntimeError
):
    """
    Raised when job metadata cannot
    be safely persisted or read.
    """


@dataclass(
    frozen=True,
    slots=True,
)
class StoredArtifactJob:
    job_id: str
    access_token_hash: str
    status: ArtifactJobStatus
    progress_percent: int
    stage: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    request: ArtifactJobCreateRequest
    idempotency_key_hash: str | None = None
    artifact: (
        ArtifactComposeResponse
        | None
    ) = None
    error: str | None = None

    @property
    def expired(self) -> bool:
        return (
            datetime.now(timezone.utc)
            >= self.expires_at
        )

    @property
    def terminal(self) -> bool:
        return (
            self.status
            in _TERMINAL_STATUSES
        )


class ArtifactJobStore:
    """
    Private filesystem-backed storage for
    background artifact generation jobs.

    Plaintext access tokens are never stored.
    """

    def __init__(
        self,
        root_directory: Path | None = None,
        *,
        retention_hours: int | None = None,
        maximum_queued_jobs: int | None = None,
        access_token_bytes: int | None = None,
        maximum_error_characters: (
            int | None
        ) = None,
    ) -> None:
        self.root_directory = (
            root_directory
            or artifact_job_settings
            .storage_directory
        ).expanduser().resolve()

        self.retention_hours = (
            retention_hours
            if retention_hours is not None
            else artifact_job_settings
            .retention_hours
        )

        self.maximum_queued_jobs = (
            maximum_queued_jobs
            if maximum_queued_jobs is not None
            else artifact_job_settings
            .maximum_queued_jobs
        )

        self.access_token_bytes = (
            access_token_bytes
            if access_token_bytes is not None
            else artifact_job_settings
            .access_token_bytes
        )

        self.maximum_error_characters = (
            maximum_error_characters
            if maximum_error_characters
            is not None
            else artifact_job_settings
            .maximum_error_characters
        )

        if self.retention_hours < 1:
            raise ValueError(
                (
                    "Artifact job retention "
                    "must be at least one hour."
                )
            )

        if self.maximum_queued_jobs < 1:
            raise ValueError(
                (
                    "Maximum queued artifact "
                    "jobs must be positive."
                )
            )

        if self.access_token_bytes < 24:
            raise ValueError(
                (
                    "Artifact job access tokens "
                    "must use at least 24 bytes."
                )
            )

        if (
            self.maximum_error_characters
            < 100
        ):
            raise ValueError(
                (
                    "Maximum artifact job error "
                    "length is too small."
                )
            )

        self._lock = RLock()

        self._prepare_root()
        self._idempotency_directory = (
            self.root_directory
            / _IDEMPOTENCY_DIRECTORY
        ).resolve()
        self._idempotency_directory.mkdir(
            mode=0o700,
            parents=False,
            exist_ok=True,
        )
        self._token_secret = (
            self._load_or_create_token_secret()
        )

    def _prepare_root(self) -> None:
        self.root_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self.root_directory.chmod(
                0o700
            )
        except OSError:
            pass

        if not self.root_directory.is_dir():
            raise ArtifactJobStorageError(
                (
                    "Artifact job storage path "
                    "is not a directory."
                )
            )

    def _load_or_create_token_secret(self) -> bytes:
        path = (
            self.root_directory
            / _TOKEN_SECRET_FILENAME
        )

        try:
            if path.is_file():
                secret = path.read_bytes()
                if len(secret) < 32:
                    raise ArtifactJobStorageError(
                        "Artifact job token secret is invalid."
                    )
                return secret

            secret = secrets.token_bytes(32)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(secret)
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            temporary.replace(path)
            return secret
        except OSError as error:
            raise ArtifactJobStorageError(
                "Artifact job token secret could not be prepared."
            ) from error

    def _derive_access_token(
        self,
        job_id: str,
    ) -> str:
        digest = hmac.new(
            self._token_secret,
            job_id.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(
            digest
        ).decode("ascii").rstrip("=")

    @staticmethod
    def _request_fingerprint(
        request: ArtifactJobCreateRequest,
    ) -> str:
        payload = request.model_dump(
            mode="json",
            exclude={"idempotency_key"},
        )
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _idempotency_hash(
        idempotency_key: str,
    ) -> str:
        return hashlib.sha256(
            idempotency_key.strip().encode("utf-8")
        ).hexdigest()

    def _idempotency_path(
        self,
        key_hash: str,
    ) -> Path:
        if (
            len(key_hash) != 64
            or any(
                character
                not in _ALLOWED_JOB_ID_CHARACTERS
                for character in key_hash
            )
        ):
            raise ArtifactJobStorageError(
                "Artifact idempotency key is invalid."
            )
        return self._idempotency_directory / f"{key_hash}.json"

    def _write_idempotency_index(
        self,
        *,
        key_hash: str,
        job_id: str,
        request_fingerprint: str,
        expires_at: datetime,
    ) -> None:
        path = self._idempotency_path(key_hash)
        temporary = path.with_suffix(".tmp")
        payload = {
            "job_id": job_id,
            "request_fingerprint": request_fingerprint,
            "expires_at": expires_at.isoformat(),
        }
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            temporary.replace(path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise ArtifactJobStorageError(
                "Artifact idempotency metadata could not be stored."
            ) from error

    def _resolve_idempotent_job(
        self,
        *,
        key_hash: str,
        request_fingerprint: str,
    ) -> StoredArtifactJob | None:
        path = self._idempotency_path(key_hash)
        if not path.is_file():
            return None

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
            job_id = str(payload["job_id"])
            stored_fingerprint = str(
                payload["request_fingerprint"]
            )
            expires_at = self._parse_datetime(
                payload["expires_at"],
                field_name="expires_at",
            )
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            path.unlink(missing_ok=True)
            raise ArtifactJobStorageError(
                "Artifact idempotency metadata is invalid."
            ) from error

        if expires_at <= self._utc_now():
            path.unlink(missing_ok=True)
            return None

        if not hmac.compare_digest(
            stored_fingerprint,
            request_fingerprint,
        ):
            raise ArtifactJobConflictError(
                "Idempotency key was reused for a different artifact request."
            )

        try:
            return self._read_job(job_id)
        except ArtifactJobNotFoundError:
            path.unlink(missing_ok=True)
            return None

    def _delete_idempotency_index(
        self,
        job: StoredArtifactJob,
    ) -> None:
        if job.idempotency_key_hash:
            self._idempotency_path(
                job.idempotency_key_hash
            ).unlink(missing_ok=True)

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(
            timezone.utc
        )

    @staticmethod
    def _validate_job_id(
        job_id: str,
    ) -> str:
        normalized = (
            job_id.strip().lower()
        )

        if (
            len(normalized)
            != _JOB_ID_LENGTH
            or any(
                character
                not in (
                    _ALLOWED_JOB_ID_CHARACTERS
                )
                for character
                in normalized
            )
        ):
            raise ArtifactJobNotFoundError(
                "Artifact job was not found."
            )

        return normalized

    def _job_directory(
        self,
        job_id: str,
    ) -> Path:
        normalized = (
            self._validate_job_id(
                job_id
            )
        )

        directory = (
            self.root_directory
            / normalized
        ).resolve()

        if (
            directory.parent
            != self.root_directory
        ):
            raise ArtifactJobNotFoundError(
                "Artifact job was not found."
            )

        return directory

    @staticmethod
    def _hash_access_token(
        access_token: str,
    ) -> str:
        return hashlib.sha256(
            access_token.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def _parse_datetime(
        value: Any,
        *,
        field_name: str,
    ) -> datetime:
        if not isinstance(
            value,
            str,
        ):
            raise ArtifactJobStorageError(
                (
                    "Artifact job field "
                    f"{field_name!r} "
                    "is invalid."
                )
            )

        try:
            parsed = (
                datetime.fromisoformat(
                    value
                )
            )
        except ValueError as error:
            raise ArtifactJobStorageError(
                (
                    "Artifact job field "
                    f"{field_name!r} "
                    "is invalid."
                )
            ) from error

        if parsed.tzinfo is None:
            raise ArtifactJobStorageError(
                (
                    "Artifact job field "
                    f"{field_name!r} must "
                    "include a timezone."
                )
            )

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _serialize_job(
        job: StoredArtifactJob,
    ) -> dict[str, Any]:
        return {
            "job_id": job.job_id,
            "access_token_hash": (
                job.access_token_hash
            ),
            "status": job.status,
            "progress_percent": (
                job.progress_percent
            ),
            "stage": job.stage,
            "created_at": (
                job.created_at.isoformat()
            ),
            "updated_at": (
                job.updated_at.isoformat()
            ),
            "expires_at": (
                job.expires_at.isoformat()
            ),
            "request": (
                job.request.model_dump(
                    mode="json"
                )
            ),
            "idempotency_key_hash": (
                job.idempotency_key_hash
            ),
            "artifact": (
                job.artifact.model_dump(
                    mode="json"
                )
                if job.artifact
                is not None
                else None
            ),
            "error": job.error,
        }

    def _deserialize_job(
        self,
        payload: Any,
    ) -> StoredArtifactJob:
        if not isinstance(
            payload,
            dict,
        ):
            raise ArtifactJobStorageError(
                (
                    "Artifact job metadata "
                    "is invalid."
                )
            )

        try:
            job_id = (
                self._validate_job_id(
                    str(payload["job_id"])
                )
            )

            access_token_hash = str(
                payload[
                    "access_token_hash"
                ]
            )

            status = payload["status"]

            if status not in {
                "queued",
                "running",
                "succeeded",
                "failed",
                "cancelled",
            }:
                raise ValueError(
                    "Invalid job status."
                )

            progress_percent = int(
                payload[
                    "progress_percent"
                ]
            )

            if not (
                0
                <= progress_percent
                <= 100
            ):
                raise ValueError(
                    (
                        "Invalid job "
                        "progress."
                    )
                )

            stage = str(
                payload["stage"]
            ).strip()

            if not stage:
                raise ValueError(
                    "Invalid job stage."
                )

            created_at = (
                self._parse_datetime(
                    payload["created_at"],
                    field_name=(
                        "created_at"
                    ),
                )
            )

            updated_at = (
                self._parse_datetime(
                    payload["updated_at"],
                    field_name=(
                        "updated_at"
                    ),
                )
            )

            expires_at = (
                self._parse_datetime(
                    payload["expires_at"],
                    field_name=(
                        "expires_at"
                    ),
                )
            )

            request = (
                ArtifactJobCreateRequest
                .model_validate(
                    payload["request"]
                )
            )

            idempotency_value = payload.get(
                "idempotency_key_hash"
            )
            idempotency_key_hash = (
                str(idempotency_value)
                if idempotency_value is not None
                else None
            )

            if idempotency_key_hash is not None and (
                len(idempotency_key_hash) != 64
                or any(
                    character not in _ALLOWED_JOB_ID_CHARACTERS
                    for character in idempotency_key_hash
                )
            ):
                raise ValueError(
                    "Invalid artifact job idempotency key hash."
                )

            artifact_payload = (
                payload.get(
                    "artifact"
                )
            )

            artifact = (
                ArtifactComposeResponse
                .model_validate(
                    artifact_payload
                )
                if artifact_payload
                is not None
                else None
            )

            error_value = payload.get(
                "error"
            )

            error = (
                str(error_value)
                if error_value
                is not None
                else None
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as error:
            raise ArtifactJobStorageError(
                (
                    "Artifact job metadata "
                    "could not be validated."
                )
            ) from error

        if (
            len(access_token_hash) != 64
            or any(
                character
                not in (
                    _ALLOWED_JOB_ID_CHARACTERS
                )
                for character
                in access_token_hash
            )
        ):
            raise ArtifactJobStorageError(
                (
                    "Artifact job access-token "
                    "metadata is invalid."
                )
            )

        return StoredArtifactJob(
            job_id=job_id,
            access_token_hash=(
                access_token_hash
            ),
            status=status,
            progress_percent=(
                progress_percent
            ),
            stage=stage,
            created_at=created_at,
            updated_at=updated_at,
            expires_at=expires_at,
            request=request,
            idempotency_key_hash=(
                idempotency_key_hash
            ),
            artifact=artifact,
            error=error,
        )

    def _write_job(
        self,
        job: StoredArtifactJob,
    ) -> None:
        directory = (
            self._job_directory(
                job.job_id
            )
        )

        directory.mkdir(
            parents=False,
            exist_ok=True,
        )

        try:
            directory.chmod(
                0o700
            )
        except OSError:
            pass

        metadata_path = (
            directory
            / _JOB_FILENAME
        )

        temporary_path = (
            directory
            / f".{_JOB_FILENAME}.tmp"
        )

        payload = (
            self._serialize_job(
                job
            )
        )

        try:
            temporary_path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            try:
                temporary_path.chmod(
                    0o600
                )
            except OSError:
                pass

            temporary_path.replace(
                metadata_path
            )

        except OSError as error:
            temporary_path.unlink(
                missing_ok=True
            )

            raise ArtifactJobStorageError(
                (
                    "Artifact job metadata "
                    "could not be stored."
                )
            ) from error

    def _read_job(
        self,
        job_id: str,
    ) -> StoredArtifactJob:
        directory = (
            self._job_directory(
                job_id
            )
        )

        metadata_path = (
            directory
            / _JOB_FILENAME
        )

        if not metadata_path.is_file():
            raise ArtifactJobNotFoundError(
                "Artifact job was not found."
            )

        try:
            payload = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )
        except FileNotFoundError as error:
            raise ArtifactJobNotFoundError(
                "Artifact job was not found."
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise ArtifactJobStorageError(
                (
                    "Artifact job metadata "
                    "could not be read."
                )
            ) from error

        return self._deserialize_job(
            payload
        )

    def _delete_directory(
        self,
        job_id: str,
    ) -> None:
        directory = (
            self._job_directory(
                job_id
            )
        )

        if not directory.exists():
            return

        try:
            shutil.rmtree(
                directory
            )
        except OSError as error:
            raise ArtifactJobStorageError(
                (
                    "Artifact job record "
                    "could not be deleted."
                )
            ) from error

    def _active_job_count(self) -> int:
        count = 0

        for directory in (
            self.root_directory
            .iterdir()
        ):
            if (
                not directory.is_dir()
                or directory.name == _IDEMPOTENCY_DIRECTORY
            ):
                continue

            try:
                job = self._read_job(
                    directory.name
                )
            except (
                ArtifactJobNotFoundError,
                ArtifactJobStorageError,
            ):
                continue

            if (
                not job.expired
                and job.status
                in _ACTIVE_STATUSES
            ):
                count += 1

        return count

    def create(
        self,
        request: ArtifactJobCreateRequest,
    ) -> tuple[
        StoredArtifactJob,
        str,
    ]:
        with self._lock:
            self.cleanup_expired()

            key_hash: str | None = None
            fingerprint = self._request_fingerprint(
                request
            )

            if request.idempotency_key:
                key_hash = self._idempotency_hash(
                    request.idempotency_key
                )
                existing = self._resolve_idempotent_job(
                    key_hash=key_hash,
                    request_fingerprint=fingerprint,
                )
                if existing is not None:
                    return (
                        existing,
                        self._derive_access_token(
                            existing.job_id
                        ),
                    )

            if (
                self._active_job_count()
                >= self.maximum_queued_jobs
            ):
                raise ArtifactJobCapacityError(
                    "The artifact generation queue is currently full."
                )

            now = self._utc_now()

            while True:
                job_id = uuid4().hex
                if not self._job_directory(job_id).exists():
                    break

            access_token = self._derive_access_token(
                job_id
            )
            job = StoredArtifactJob(
                job_id=job_id,
                access_token_hash=(
                    self._hash_access_token(
                        access_token
                    )
                ),
                status="queued",
                progress_percent=0,
                stage="Queued for generation",
                created_at=now,
                updated_at=now,
                expires_at=(
                    now
                    + timedelta(
                        hours=self.retention_hours
                    )
                ),
                request=request,
                idempotency_key_hash=key_hash,
            )

            self._write_job(job)

            if key_hash:
                self._write_idempotency_index(
                    key_hash=key_hash,
                    job_id=job_id,
                    request_fingerprint=fingerprint,
                    expires_at=job.expires_at,
                )

            return job, access_token

    def get(
        self,
        job_id: str,
        access_token: str,
    ) -> StoredArtifactJob:
        with self._lock:
            job = self._read_job(
                job_id
            )

            if job.expired:
                self._delete_idempotency_index(job)
                self._delete_directory(
                    job.job_id
                )

                raise ArtifactJobExpiredError(
                    (
                        "Artifact job "
                        "has expired."
                    )
                )

            supplied_hash = (
                self._hash_access_token(
                    access_token
                )
            )

            if not hmac.compare_digest(
                supplied_hash,
                job.access_token_hash,
            ):
                raise ArtifactJobAccessError(
                    (
                        "Artifact job access "
                        "was denied."
                    )
                )

            return job

    def get_internal(
        self,
        job_id: str,
    ) -> StoredArtifactJob:
        with self._lock:
            job = self._read_job(
                job_id
            )

            if job.expired:
                self._delete_idempotency_index(job)
                self._delete_directory(
                    job.job_id
                )

                raise ArtifactJobExpiredError(
                    (
                        "Artifact job "
                        "has expired."
                    )
                )

            return job

    def update(
        self,
        job_id: str,
        *,
        status: ArtifactJobStatus,
        progress_percent: int,
        stage: str,
        artifact: (
            ArtifactComposeResponse
            | None
        ) = None,
        error: str | None = None,
    ) -> StoredArtifactJob:
        normalized_stage = stage.strip()

        if not normalized_stage:
            raise ValueError(
                (
                    "Artifact job stage "
                    "cannot be empty."
                )
            )

        if len(normalized_stage) > 160:
            raise ValueError(
                (
                    "Artifact job stage "
                    "is too long."
                )
            )

        if not (
            0
            <= progress_percent
            <= 100
        ):
            raise ValueError(
                (
                    "Artifact job progress "
                    "must be between 0 and 100."
                )
            )

        normalized_error = (
            error.strip()
            if error is not None
            else None
        )

        if normalized_error:
            normalized_error = (
                normalized_error[
                    :self
                    .maximum_error_characters
                ]
            )

        with self._lock:
            current = (
                self.get_internal(
                    job_id
                )
            )

            if (
                status
                != current.status
                and status
                not in (
                    _ALLOWED_TRANSITIONS[
                        current.status
                    ]
                )
            ):
                raise ArtifactJobConflictError(
                    (
                        "Artifact job cannot "
                        f"transition from "
                        f"{current.status!r} "
                        f"to {status!r}."
                    )
                )

            if (
                status == "succeeded"
                and artifact is None
            ):
                raise ArtifactJobConflictError(
                    (
                        "A successful artifact "
                        "job must include the "
                        "generated artifact."
                    )
                )

            if (
                status == "failed"
                and not normalized_error
            ):
                normalized_error = (
                    "Artifact generation failed."
                )

            if status == "succeeded":
                progress_percent = 100
                normalized_error = None
            elif status == "cancelled":
                normalized_error = None

            updated = replace(
                current,
                status=status,
                progress_percent=(
                    progress_percent
                ),
                stage=normalized_stage,
                updated_at=self._utc_now(),
                artifact=artifact,
                error=normalized_error,
            )

            self._write_job(
                updated
            )

            return updated

    def cancel(
        self,
        job_id: str,
        access_token: str,
    ) -> StoredArtifactJob:
        with self._lock:
            current = self.get(
                job_id,
                access_token,
            )

            if current.terminal:
                return current

            updated = replace(
                current,
                status="cancelled",
                progress_percent=(
                    current.progress_percent
                ),
                stage="Generation cancelled",
                updated_at=self._utc_now(),
                error=None,
            )
            self._write_job(updated)
            return updated

    def delete(
        self,
        job_id: str,
        access_token: str,
    ) -> bool:
        with self._lock:
            job = self.get(
                job_id,
                access_token,
            )

            if not job.terminal:
                raise ArtifactJobConflictError(
                    (
                        "An active artifact job "
                        "cannot be deleted."
                    )
                )

            self._delete_idempotency_index(job)
            self._delete_directory(
                job.job_id
            )

            return True

    def stats(self) -> dict[str, int]:
        counts = {
            "queued": 0,
            "running": 0,
            "succeeded": 0,
            "failed": 0,
            "cancelled": 0,
        }

        with self._lock:
            for directory in self.root_directory.iterdir():
                if (
                    directory.is_symlink()
                    or not directory.is_dir()
                    or directory.name == _IDEMPOTENCY_DIRECTORY
                ):
                    continue

                try:
                    job = self.get_internal(directory.name)
                except (
                    ArtifactJobNotFoundError,
                    ArtifactJobStorageError,
                ):
                    continue

                counts[job.status] += 1

        counts["total"] = sum(counts.values())
        return counts

    def cleanup_expired(self) -> int:
        deleted_count = 0
        now = self._utc_now()

        with self._lock:
            for directory in list(
                self.root_directory
                .iterdir()
            ):
                if (
                    not directory.is_dir()
                    or directory.name == _IDEMPOTENCY_DIRECTORY
                ):
                    continue

                try:
                    job = self._read_job(
                        directory.name
                    )
                except (
                    ArtifactJobNotFoundError,
                    ArtifactJobStorageError,
                ):
                    continue

                if now < job.expires_at:
                    continue

                self._delete_idempotency_index(job)
                self._delete_directory(
                    job.job_id
                )

                deleted_count += 1

        return deleted_count

    def recover_interrupted_jobs(
        self,
    ) -> int:
        """
        Mark queued or running jobs as failed
        after a process restart.

        In-process background tasks cannot
        safely continue after the worker exits.
        """

        recovered_count = 0

        with self._lock:
            self.cleanup_expired()

            for directory in list(
                self.root_directory
                .iterdir()
            ):
                if (
                    not directory.is_dir()
                    or directory.name == _IDEMPOTENCY_DIRECTORY
                ):
                    continue

                try:
                    job = self._read_job(
                        directory.name
                    )
                except (
                    ArtifactJobNotFoundError,
                    ArtifactJobStorageError,
                ):
                    continue

                if (
                    job.status
                    not in _ACTIVE_STATUSES
                ):
                    continue

                recovered = replace(
                    job,
                    status="failed",
                    progress_percent=100,
                    stage=(
                        "Generation interrupted"
                    ),
                    updated_at=self._utc_now(),
                    artifact=None,
                    error=(
                        "Artifact generation was "
                        "interrupted because the "
                        "server restarted."
                    ),
                )

                self._write_job(
                    recovered
                )

                recovered_count += 1

        return recovered_count