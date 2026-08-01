from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from schemas.artifacts import (
    ArtifactSourceReference,
    ArtifactSourceSnapshot,
)


class ArtifactSourceNotFoundError(FileNotFoundError):
    pass


class ArtifactSourceAccessError(PermissionError):
    pass


class ArtifactSourceExpiredError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredArtifactSource:
    source_id: str
    access_token_hash: str
    created_at: datetime
    expires_at: datetime
    snapshot: ArtifactSourceSnapshot


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactSourceVault:
    """Private durable source storage addressed by capability tokens.

    Model prompts receive source content only after the backend resolves this
    reference. The browser never needs to duplicate a large source inside the
    artifact job JSON payload.
    """

    def __init__(
        self,
        *,
        root_directory: Path,
        retention_hours: int,
    ) -> None:
        self.root_directory = root_directory.resolve()
        self.retention_hours = retention_hours
        self._lock = threading.RLock()
        self.root_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

    @staticmethod
    def _token_hash(access_token: str) -> str:
        return hashlib.sha256(
            access_token.encode("utf-8")
        ).hexdigest()

    def _record_path(self, source_id: str) -> Path:
        if (
            len(source_id) != 32
            or not all(character in "0123456789abcdef" for character in source_id)
        ):
            raise ArtifactSourceNotFoundError(
                "Artifact source was not found."
            )
        return self.root_directory / f"{source_id}.json"

    @staticmethod
    def _serialize(record: StoredArtifactSource) -> dict[str, object]:
        return {
            "source_id": record.source_id,
            "access_token_hash": record.access_token_hash,
            "created_at": record.created_at.isoformat(),
            "expires_at": record.expires_at.isoformat(),
            "snapshot": record.snapshot.model_dump(mode="json"),
        }

    @staticmethod
    def _deserialize(payload: dict[str, object]) -> StoredArtifactSource:
        return StoredArtifactSource(
            source_id=str(payload["source_id"]),
            access_token_hash=str(payload["access_token_hash"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            snapshot=ArtifactSourceSnapshot.model_validate(payload["snapshot"]),
        )

    def _write(self, record: StoredArtifactSource) -> None:
        path = self._record_path(record.source_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                self._serialize(record),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(path)

    def create(
        self,
        snapshot: ArtifactSourceSnapshot,
    ) -> tuple[ArtifactSourceReference, StoredArtifactSource]:
        if not snapshot.content:
            raise ValueError(
                "A durable artifact source requires content."
            )
        with self._lock:
            self.cleanup_expired()
            source_id = uuid4().hex
            access_token = secrets.token_urlsafe(32)
            created_at = _utc_now()
            record = StoredArtifactSource(
                source_id=source_id,
                access_token_hash=self._token_hash(access_token),
                created_at=created_at,
                expires_at=created_at + timedelta(hours=self.retention_hours),
                snapshot=snapshot,
            )
            self._write(record)
            return (
                ArtifactSourceReference(
                    source_id=source_id,
                    access_token=access_token,
                ),
                record,
            )

    def get(
        self,
        reference: ArtifactSourceReference,
    ) -> StoredArtifactSource:
        with self._lock:
            path = self._record_path(reference.source_id)
            if not path.is_file():
                raise ArtifactSourceNotFoundError(
                    "Artifact source was not found."
                )
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = self._deserialize(payload)
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise ArtifactSourceNotFoundError(
                    "Artifact source could not be loaded."
                ) from error

            if not hmac.compare_digest(
                record.access_token_hash,
                self._token_hash(reference.access_token),
            ):
                raise ArtifactSourceAccessError(
                    "Artifact source access was denied."
                )
            if record.expires_at <= _utc_now():
                path.unlink(missing_ok=True)
                raise ArtifactSourceExpiredError(
                    "Artifact source has expired."
                )
            return record

    def cleanup_expired(self) -> int:
        removed = 0
        now = _utc_now()
        with self._lock:
            for path in self.root_directory.glob("*.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    expires_at = datetime.fromisoformat(
                        str(payload["expires_at"])
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    path.unlink(missing_ok=True)
                    removed += 1
                    continue
                if expires_at <= now:
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed
