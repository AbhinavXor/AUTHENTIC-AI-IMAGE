from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from artifacts.engine import (
    ArtifactGenerationResult,
    ArtifactValidationError,
    generate_artifact,
)
from artifacts.models import ArtifactDocument
from core.artifact_settings import artifact_settings


_METADATA_FILENAME = "metadata.json"
_ID_LENGTH = 32
_ALLOWED_ID_CHARACTERS = frozenset(
    "0123456789abcdef"
)


class ArtifactNotFoundError(FileNotFoundError):
    """Raised when a stored artifact cannot be found."""


class ArtifactExpiredError(ArtifactNotFoundError):
    """Raised when a stored artifact has expired."""


class ArtifactStorageError(RuntimeError):
    """Raised when artifact persistence or integrity checks fail."""


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    artifact_id: str
    filename: str
    format: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime
    path: Path

    @property
    def expired(self) -> bool:
        return (
            datetime.now(timezone.utc)
            >= self.expires_at
        )


class ArtifactStorage:
    """Private filesystem storage for generated artifacts."""

    def __init__(
        self,
        root_directory: Path | None = None,
        *,
        retention_hours: int | None = None,
        maximum_file_bytes: int | None = None,
    ) -> None:
        self.root_directory = (
            root_directory
            or artifact_settings
            .storage_directory
        ).expanduser().resolve()

        self.retention_hours = (
            retention_hours
            if retention_hours is not None
            else artifact_settings.retention_hours
        )

        self.maximum_file_bytes = (
            maximum_file_bytes
            if maximum_file_bytes is not None
            else artifact_settings
            .maximum_generated_file_bytes
        )

        if self.retention_hours < 1:
            raise ValueError(
                "Artifact retention must be at least one hour."
            )

        if self.maximum_file_bytes < 1:
            raise ValueError(
                "Maximum artifact file size must be positive."
            )

        self._lock = RLock()
        self._prepare_root()

    def _prepare_root(self) -> None:
        self.root_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self.root_directory.chmod(0o700)
        except OSError:
            pass

        if not self.root_directory.is_dir():
            raise ArtifactStorageError(
                "Artifact storage path is not a directory."
            )

    @staticmethod
    def _validate_artifact_id(
        artifact_id: str,
    ) -> str:
        normalized = artifact_id.strip().lower()

        if (
            len(normalized) != _ID_LENGTH
            or any(
                character
                not in _ALLOWED_ID_CHARACTERS
                for character in normalized
            )
        ):
            raise ArtifactNotFoundError(
                "Artifact was not found."
            )

        return normalized

    def _artifact_directory(
        self,
        artifact_id: str,
    ) -> Path:
        normalized = self._validate_artifact_id(
            artifact_id
        )

        directory = (
            self.root_directory
            / normalized
        ).resolve()

        if directory.parent != self.root_directory:
            raise ArtifactNotFoundError(
                "Artifact was not found."
            )

        return directory

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(
            timezone.utc
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
        *,
        field_name: str,
    ) -> datetime:
        if not isinstance(value, str):
            raise ArtifactStorageError(
                f"Artifact metadata field "
                f"{field_name!r} is invalid."
            )

        try:
            parsed = datetime.fromisoformat(
                value
            )
        except ValueError as error:
            raise ArtifactStorageError(
                f"Artifact metadata field "
                f"{field_name!r} is invalid."
            ) from error

        if parsed.tzinfo is None:
            raise ArtifactStorageError(
                f"Artifact metadata field "
                f"{field_name!r} must include a timezone."
            )

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _metadata_payload(
        stored: StoredArtifact,
    ) -> dict[str, Any]:
        payload = asdict(stored)
        payload.pop("path", None)

        payload["created_at"] = (
            stored.created_at.isoformat()
        )
        payload["expires_at"] = (
            stored.expires_at.isoformat()
        )

        return payload

    def _write_metadata(
        self,
        directory: Path,
        stored: StoredArtifact,
    ) -> None:
        metadata_path = (
            directory
            / _METADATA_FILENAME
        )

        temporary_path = (
            directory
            / f".{_METADATA_FILENAME}.tmp"
        )

        payload = self._metadata_payload(
            stored
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

            raise ArtifactStorageError(
                "Artifact metadata could not be stored."
            ) from error

    def _read_metadata(
        self,
        artifact_id: str,
        directory: Path,
    ) -> StoredArtifact:
        metadata_path = (
            directory
            / _METADATA_FILENAME
        )

        try:
            raw_payload = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise ArtifactNotFoundError(
                "Artifact was not found."
            ) from error

        if not isinstance(
            raw_payload,
            dict,
        ):
            raise ArtifactStorageError(
                "Artifact metadata is invalid."
            )

        filename = raw_payload.get(
            "filename"
        )

        if (
            not isinstance(filename, str)
            or not filename
            or Path(filename).name
            != filename
        ):
            raise ArtifactStorageError(
                "Artifact metadata contains an unsafe filename."
            )

        file_path = (
            directory
            / filename
        ).resolve()

        if file_path.parent != directory:
            raise ArtifactStorageError(
                "Artifact file escaped its storage directory."
            )

        stored_id = raw_payload.get(
            "artifact_id"
        )

        if stored_id != artifact_id:
            raise ArtifactStorageError(
                "Artifact metadata identifier does not match."
            )

        try:
            size_bytes = int(
                raw_payload["size_bytes"]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise ArtifactStorageError(
                "Artifact metadata contains an invalid size."
            ) from error

        if size_bytes < 1:
            raise ArtifactStorageError(
                "Artifact metadata contains an invalid size."
            )

        required_text_fields = (
            "format",
            "media_type",
            "sha256",
        )

        for field_name in required_text_fields:
            if not isinstance(
                raw_payload.get(
                    field_name
                ),
                str,
            ):
                raise ArtifactStorageError(
                    f"Artifact metadata field "
                    f"{field_name!r} is invalid."
                )

        return StoredArtifact(
            artifact_id=artifact_id,
            filename=filename,
            format=raw_payload[
                "format"
            ],
            media_type=raw_payload[
                "media_type"
            ],
            size_bytes=size_bytes,
            sha256=raw_payload[
                "sha256"
            ],
            created_at=self._parse_datetime(
                raw_payload.get(
                    "created_at"
                ),
                field_name="created_at",
            ),
            expires_at=self._parse_datetime(
                raw_payload.get(
                    "expires_at"
                ),
                field_name="expires_at",
            ),
            path=file_path,
        )

    def _verify_file(
        self,
        stored: StoredArtifact,
    ) -> None:
        if (
            stored.path.is_symlink()
            or not stored.path.is_file()
        ):
            raise ArtifactNotFoundError(
                "Artifact was not found."
            )

        actual_size = (
            stored.path.stat().st_size
        )

        if (
            actual_size != stored.size_bytes
            or actual_size
            > self.maximum_file_bytes
        ):
            raise ArtifactStorageError(
                "Stored artifact failed its size integrity check."
            )

    def create(
        self,
        artifact: ArtifactDocument,
        *,
        format: object,
        filename: str | None = None,
    ) -> StoredArtifact:
        artifact_id = uuid4().hex
        directory = self._artifact_directory(
            artifact_id
        )

        created_at = self._utc_now()
        expires_at = (
            created_at
            + timedelta(
                hours=self.retention_hours
            )
        )

        with self._lock:
            try:
                directory.mkdir(
                    mode=0o700,
                    parents=False,
                    exist_ok=False,
                )

                generation_result = (
                    generate_artifact(
                        artifact,
                        format=format,
                        output_directory=directory,
                        filename=filename,
                        overwrite=False,
                    )
                )

                self._validate_generated_result(
                    generation_result
                )

                stored = StoredArtifact(
                    artifact_id=artifact_id,
                    filename=(
                        generation_result
                        .path.name
                    ),
                    format=(
                        generation_result
                        .format
                    ),
                    media_type=(
                        generation_result
                        .media_type
                    ),
                    size_bytes=(
                        generation_result
                        .size_bytes
                    ),
                    sha256=(
                        generation_result
                        .sha256
                    ),
                    created_at=created_at,
                    expires_at=expires_at,
                    path=(
                        generation_result
                        .path.resolve()
                    ),
                )

                try:
                    stored.path.chmod(
                        0o600
                    )
                except OSError:
                    pass

                self._write_metadata(
                    directory,
                    stored,
                )

                return stored

            except (
                ArtifactValidationError,
                ArtifactStorageError,
            ):
                shutil.rmtree(
                    directory,
                    ignore_errors=True,
                )
                raise

            except Exception:
                shutil.rmtree(
                    directory,
                    ignore_errors=True,
                )
                raise

    def _validate_generated_result(
        self,
        result: ArtifactGenerationResult,
    ) -> None:
        if (
            result.size_bytes < 1
            or result.size_bytes
            > self.maximum_file_bytes
        ):
            raise ArtifactStorageError(
                "Generated artifact exceeds the configured file limit."
            )

        if len(result.sha256) != 64:
            raise ArtifactStorageError(
                "Generated artifact checksum is invalid."
            )

    def get(
        self,
        artifact_id: str,
        *,
        delete_if_expired: bool = True,
    ) -> StoredArtifact:
        normalized = self._validate_artifact_id(
            artifact_id
        )

        directory = self._artifact_directory(
            normalized
        )

        if (
            not directory.is_dir()
            or directory.is_symlink()
        ):
            raise ArtifactNotFoundError(
                "Artifact was not found."
            )

        stored = self._read_metadata(
            normalized,
            directory,
        )

        if stored.expired:
            if delete_if_expired:
                self.delete(
                    normalized,
                    missing_ok=True,
                )

            raise ArtifactExpiredError(
                "Artifact has expired."
            )

        self._verify_file(
            stored
        )

        return stored

    def delete(
        self,
        artifact_id: str,
        *,
        missing_ok: bool = False,
    ) -> bool:
        normalized = self._validate_artifact_id(
            artifact_id
        )

        directory = self._artifact_directory(
            normalized
        )

        with self._lock:
            if not directory.exists():
                if missing_ok:
                    return False

                raise ArtifactNotFoundError(
                    "Artifact was not found."
                )

            if (
                directory.is_symlink()
                or not directory.is_dir()
            ):
                raise ArtifactStorageError(
                    "Artifact storage entry is unsafe."
                )

            try:
                shutil.rmtree(
                    directory
                )
            except OSError as error:
                raise ArtifactStorageError(
                    "Artifact could not be deleted."
                ) from error

        return True

    def cleanup_expired(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        current_time = (
            now.astimezone(timezone.utc)
            if now is not None
            else self._utc_now()
        )

        deleted_count = 0

        with self._lock:
            for candidate in (
                self.root_directory
                .iterdir()
            ):
                if (
                    candidate.is_symlink()
                    or not candidate.is_dir()
                ):
                    continue

                try:
                    artifact_id = (
                        self._validate_artifact_id(
                            candidate.name
                        )
                    )

                    stored = (
                        self._read_metadata(
                            artifact_id,
                            candidate.resolve(),
                        )
                    )

                except (
                    ArtifactNotFoundError,
                    ArtifactStorageError,
                ):
                    continue

                if (
                    current_time
                    >= stored.expires_at
                ):
                    shutil.rmtree(
                        candidate,
                        ignore_errors=True,
                    )
                    deleted_count += 1

        return deleted_count