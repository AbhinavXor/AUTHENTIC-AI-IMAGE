from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from artifacts.parser import sanitize_filename
from artifacts.storage import (
    ArtifactNotFoundError,
    ArtifactStorage,
    ArtifactStorageError,
    StoredArtifact,
)

_RECORD_FILENAME = "artifact.json"
_RECORD_SCHEMA_VERSION = 3
_TOKEN_SECRET_FILENAME = ".artifact-token-secret"
_CREATION_IDEMPOTENCY_DIRECTORY = "_creation_idempotency"


class ArtifactRepositoryError(RuntimeError):
    """Raised when durable artifact metadata cannot be persisted."""


class ArtifactAccessError(PermissionError):
    """Raised when an artifact capability token is missing or invalid."""


class ArtifactConflictError(RuntimeError):
    """Raised when an artifact version precondition fails."""


@dataclass(frozen=True, slots=True)
class ArtifactVersionRecord:
    version: int
    physical_artifact_id: str
    filename: str
    format: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime
    page_or_slide_count: int
    source_content: str
    specification: dict[str, Any]
    validation: dict[str, Any]
    provider: str | None = None
    model: str | None = None
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "physical_artifact_id": self.physical_artifact_id,
            "filename": self.filename,
            "format": self.format,
            "media_type": self.media_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "page_or_slide_count": self.page_or_slide_count,
            "source_content": self.source_content,
            "specification": self.specification,
            "validation": self.validation,
            "provider": self.provider,
            "model": self.model,
            "request_id": self.request_id,
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "ArtifactVersionRecord":
        return cls(
            version=int(payload["version"]),
            physical_artifact_id=str(
                payload["physical_artifact_id"]
            ),
            filename=str(payload["filename"]),
            format=str(payload["format"]),
            media_type=str(payload["media_type"]),
            size_bytes=int(payload["size_bytes"]),
            sha256=str(payload["sha256"]),
            created_at=_parse_datetime(
                payload["created_at"]
            ),
            expires_at=_parse_datetime(
                payload["expires_at"]
            ),
            page_or_slide_count=int(
                payload.get(
                    "page_or_slide_count",
                    0,
                )
            ),
            source_content=str(
                payload.get("source_content", "")
            ),
            specification=dict(
                payload.get("specification", {})
            ),
            validation=dict(
                payload.get("validation", {})
            ),
            provider=_optional_string(
                payload.get("provider")
            ),
            model=_optional_string(
                payload.get("model")
            ),
            request_id=_optional_string(
                payload.get("request_id")
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    access_token_hash: str
    title: str
    display_name: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    current_version: int
    versions: tuple[ArtifactVersionRecord, ...]
    source_snapshot: dict[str, Any] = field(
        default_factory=dict
    )
    operation_receipts: tuple[dict[str, Any], ...] = ()
    audit_events: tuple[dict[str, Any], ...] = ()

    @property
    def version_count(self) -> int:
        return len(self.versions)

    @property
    def current(self) -> ArtifactVersionRecord:
        for version in self.versions:
            if version.version == self.current_version:
                return version

        raise ArtifactRepositoryError(
            "Artifact current version is missing."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": _RECORD_SCHEMA_VERSION,
            "artifact_id": self.artifact_id,
            "access_token_hash": self.access_token_hash,
            "title": self.title,
            "display_name": self.display_name,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "current_version": self.current_version,
            "versions": [
                version.to_dict()
                for version in self.versions
            ],
            "source_snapshot": self.source_snapshot,
            "operation_receipts": list(
                self.operation_receipts
            ),
            "audit_events": list(self.audit_events),
        }

    @classmethod
    def from_dict(
        cls,
        payload: dict[str, Any],
    ) -> "ArtifactRecord":
        versions = tuple(
            ArtifactVersionRecord.from_dict(item)
            for item in payload.get("versions", [])
            if isinstance(item, dict)
        )

        if not versions:
            raise ArtifactRepositoryError(
                "Artifact record contains no versions."
            )

        return cls(
            artifact_id=str(payload["artifact_id"]),
            access_token_hash=str(
                payload["access_token_hash"]
            ),
            title=str(payload.get("title", "Artifact")),
            display_name=str(payload["display_name"]),
            created_at=_parse_datetime(
                payload["created_at"]
            ),
            updated_at=_parse_datetime(
                payload["updated_at"]
            ),
            expires_at=_parse_datetime(
                payload["expires_at"]
            ),
            current_version=int(
                payload["current_version"]
            ),
            versions=versions,
            source_snapshot=dict(
                payload.get("source_snapshot", {})
            ),
            operation_receipts=tuple(
                receipt
                for receipt in payload.get(
                    "operation_receipts",
                    [],
                )
                if isinstance(receipt, dict)
            ),
            audit_events=tuple(
                event
                for event in payload.get(
                    "audit_events",
                    [],
                )
                if isinstance(event, dict)
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactView:
    record: ArtifactRecord
    version: ArtifactVersionRecord
    stored: StoredArtifact
    access_token: str | None = None


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ArtifactRepositoryError(
            "Artifact record datetime is invalid."
        )

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ArtifactRepositoryError(
            "Artifact record datetime is invalid."
        ) from error

    if parsed.tzinfo is None:
        raise ArtifactRepositoryError(
            "Artifact record datetime must include a timezone."
        )

    return parsed.astimezone(timezone.utc)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _token_hash(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def normalize_display_filename(
    value: str,
    *,
    format: str,
) -> str:
    raw = value.strip()
    suffix = f".{format.lower()}"
    stem = Path(raw).stem
    safe_stem = sanitize_filename(stem).strip(".-_") or "artifact"
    maximum_stem_length = max(1, 180 - len(suffix))
    normalized_stem = safe_stem[:maximum_stem_length].rstrip(".-_") or "artifact"
    return f"{normalized_stem}{suffix}"


class ArtifactRepository:
    """Durable logical artifact and version repository."""

    def __init__(
        self,
        artifact_storage: ArtifactStorage,
        root_directory: Path | None = None,
    ) -> None:
        self.artifact_storage = artifact_storage
        self.root_directory = (
            root_directory
            or artifact_storage.root_directory
            / "_records"
        ).expanduser().resolve()
        self._lock = RLock()
        self.root_directory.mkdir(
            mode=0o700,
            parents=True,
            exist_ok=True,
        )
        self._creation_idempotency_directory = (
            self.root_directory
            / _CREATION_IDEMPOTENCY_DIRECTORY
        ).resolve()
        self._creation_idempotency_directory.mkdir(
            mode=0o700,
            parents=False,
            exist_ok=True,
        )
        self._token_secret = self._load_or_create_token_secret()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    def _load_or_create_token_secret(self) -> bytes:
        path = self.root_directory / _TOKEN_SECRET_FILENAME
        try:
            if path.is_file():
                secret = path.read_bytes()
                if len(secret) < 32:
                    raise ArtifactRepositoryError(
                        "Artifact token secret is invalid."
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
            raise ArtifactRepositoryError(
                "Artifact token secret could not be prepared."
            ) from error

    def _derive_access_token(self, artifact_id: str) -> str:
        digest = hmac.new(
            self._token_secret,
            artifact_id.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _creation_key_hash(idempotency_key: str) -> str:
        normalized = idempotency_key.strip()
        if not normalized:
            raise ArtifactConflictError(
                "Idempotency key cannot be empty."
            )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _creation_index_path(self, key_hash: str) -> Path:
        if (
            len(key_hash) != 64
            or any(character not in "0123456789abcdef" for character in key_hash)
        ):
            raise ArtifactRepositoryError(
                "Artifact creation idempotency key is invalid."
            )
        return self._creation_idempotency_directory / f"{key_hash}.json"

    def _write_creation_receipt(
        self,
        *,
        idempotency_key: str,
        fingerprint: str,
        artifact_id: str,
        expires_at: datetime,
    ) -> None:
        key_hash = self._creation_key_hash(idempotency_key)
        path = self._creation_index_path(key_hash)
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    {
                        "artifact_id": artifact_id,
                        "fingerprint": fingerprint,
                        "expires_at": expires_at.isoformat(),
                    },
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
            raise ArtifactRepositoryError(
                "Artifact creation idempotency receipt could not be stored."
            ) from error

    def resolve_creation(
        self,
        *,
        idempotency_key: str | None,
        fingerprint: str,
    ) -> ArtifactView | None:
        if not idempotency_key:
            return None

        path = self._creation_index_path(
            self._creation_key_hash(idempotency_key)
        )
        if not path.is_file():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            artifact_id = str(payload["artifact_id"])
            stored_fingerprint = str(payload["fingerprint"])
            expires_at = _parse_datetime(payload["expires_at"])
        except (
            OSError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ArtifactRepositoryError,
        ) as error:
            path.unlink(missing_ok=True)
            raise ArtifactRepositoryError(
                "Artifact creation idempotency receipt is invalid."
            ) from error

        if expires_at <= self._utc_now():
            path.unlink(missing_ok=True)
            return None

        if not hmac.compare_digest(stored_fingerprint, fingerprint):
            raise ArtifactConflictError(
                "Idempotency key was reused for a different artifact creation request."
            )

        try:
            view = self.get_internal(artifact_id)
        except ArtifactNotFoundError:
            path.unlink(missing_ok=True)
            return None

        return ArtifactView(
            record=view.record,
            version=view.version,
            stored=view.stored,
            access_token=self._derive_access_token(artifact_id),
        )

    def _record_directory(
        self,
        artifact_id: str,
    ) -> Path:
        normalized = (
            self.artifact_storage
            ._validate_artifact_id(artifact_id)
        )
        path = (
            self.root_directory
            / normalized
        ).resolve()

        if path.parent != self.root_directory:
            raise ArtifactNotFoundError(
                "Artifact was not found."
            )

        return path

    def _record_path(
        self,
        artifact_id: str,
    ) -> Path:
        return (
            self._record_directory(artifact_id)
            / _RECORD_FILENAME
        )

    def _write(
        self,
        record: ArtifactRecord,
    ) -> None:
        directory = self._record_directory(
            record.artifact_id
        )
        directory.mkdir(
            mode=0o700,
            parents=False,
            exist_ok=True,
        )
        path = directory / _RECORD_FILENAME
        temporary = directory / f".{_RECORD_FILENAME}.tmp"

        try:
            temporary.write_text(
                json.dumps(
                    record.to_dict(),
                    ensure_ascii=False,
                    indent=2,
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
            raise ArtifactRepositoryError(
                "Artifact record could not be stored."
            ) from error

    def _read(
        self,
        artifact_id: str,
    ) -> ArtifactRecord:
        path = self._record_path(artifact_id)

        try:
            payload = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ArtifactNotFoundError(
                "Artifact was not found."
            ) from error

        if not isinstance(payload, dict):
            raise ArtifactRepositoryError(
                "Artifact record is invalid."
            )

        record = ArtifactRecord.from_dict(payload)

        if record.artifact_id != artifact_id:
            raise ArtifactRepositoryError(
                "Artifact record identifier mismatch."
            )

        return record

    @staticmethod
    def _verify_access(
        record: ArtifactRecord,
        access_token: str | None,
    ) -> None:
        if not access_token or not access_token.strip():
            raise ArtifactAccessError(
                "Artifact access token is required."
            )

        supplied_hash = _token_hash(
            access_token.strip()
        )

        if not hmac.compare_digest(
            supplied_hash,
            record.access_token_hash,
        ):
            raise ArtifactAccessError(
                "Artifact access was denied."
            )

    @staticmethod
    def _audit_event(
        action: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "action": action,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "detail": detail or {},
        }

    def register_new(
        self,
        stored: StoredArtifact,
        *,
        title: str,
        source_content: str,
        specification: dict[str, Any],
        source_snapshot: dict[str, Any],
        validation: dict[str, Any],
        page_or_slide_count: int,
        provider: str | None = None,
        model: str | None = None,
        request_id: str | None = None,
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> ArtifactView:
        access_token = self._derive_access_token(stored.artifact_id)
        now = self._utc_now()
        version = ArtifactVersionRecord(
            version=1,
            physical_artifact_id=stored.artifact_id,
            filename=stored.filename,
            format=stored.format,
            media_type=stored.media_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            created_at=stored.created_at,
            expires_at=stored.expires_at,
            page_or_slide_count=page_or_slide_count,
            source_content=source_content,
            specification=specification,
            validation=validation,
            provider=provider,
            model=model,
            request_id=request_id,
        )
        record = ArtifactRecord(
            artifact_id=stored.artifact_id,
            access_token_hash=_token_hash(access_token),
            title=title.strip() or "Artifact",
            display_name=stored.filename,
            created_at=stored.created_at,
            updated_at=now,
            expires_at=stored.expires_at,
            current_version=1,
            versions=(version,),
            source_snapshot=source_snapshot,
            operation_receipts=(),
            audit_events=(
                self._audit_event(
                    "created",
                    detail={"version": 1},
                ),
            ),
        )

        with self._lock:
            if idempotency_key:
                if not operation_fingerprint:
                    raise ArtifactConflictError(
                        "Operation fingerprint is required for idempotent artifact creation."
                    )
                existing = self.resolve_creation(
                    idempotency_key=idempotency_key,
                    fingerprint=operation_fingerprint,
                )
                if existing is not None:
                    self.artifact_storage.delete(
                        stored.artifact_id,
                        missing_ok=True,
                    )
                    return existing

            self._write(record)
            if idempotency_key and operation_fingerprint:
                self._write_creation_receipt(
                    idempotency_key=idempotency_key,
                    fingerprint=operation_fingerprint,
                    artifact_id=record.artifact_id,
                    expires_at=record.expires_at,
                )

        return ArtifactView(
            record=record,
            version=version,
            stored=stored,
            access_token=access_token,
        )

    def get(
        self,
        artifact_id: str,
        access_token: str,
        *,
        version: int | None = None,
    ) -> ArtifactView:
        record = self._read(artifact_id)
        self._verify_access(record, access_token)
        return self._view(record, version=version)

    def get_internal(
        self,
        artifact_id: str,
        *,
        version: int | None = None,
    ) -> ArtifactView:
        return self._view(
            self._read(artifact_id),
            version=version,
        )

    def _view(
        self,
        record: ArtifactRecord,
        *,
        version: int | None = None,
    ) -> ArtifactView:
        target_version = (
            record.current_version
            if version is None
            else version
        )
        version_record = next(
            (
                item
                for item in record.versions
                if item.version == target_version
            ),
            None,
        )

        if version_record is None:
            raise ArtifactNotFoundError(
                "Artifact version was not found."
            )

        stored = self.artifact_storage.get(
            version_record.physical_artifact_id
        )

        return ArtifactView(
            record=record,
            version=version_record,
            stored=stored,
        )

    def rename(
        self,
        artifact_id: str,
        access_token: str,
        *,
        display_name: str,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactView:
        with self._lock:
            record = self._read(artifact_id)
            self._verify_access(record, access_token)

            if (
                expected_version is not None
                and expected_version
                != record.current_version
            ):
                raise ArtifactConflictError(
                    "Artifact version changed before rename."
                )

            normalized_name = normalize_display_filename(
                display_name,
                format=record.current.format,
            )
            fingerprint = self._operation_fingerprint(
                "renamed",
                {
                    "display_name": normalized_name,
                    "expected_version": expected_version,
                },
            )
            if idempotency_key:
                receipt = self._matching_receipt(
                    record,
                    idempotency_key=idempotency_key,
                )
                if receipt is not None:
                    if (
                        receipt.get("action") != "renamed"
                        or receipt.get("fingerprint") != fingerprint
                    ):
                        raise ArtifactConflictError(
                            "Idempotency key was reused for a different artifact operation."
                        )
                    return self._view(record)

            now = self._utc_now()
            updated_receipts = record.operation_receipts
            if idempotency_key:
                updated_receipts = (
                    *record.operation_receipts[-99:],
                    {
                        "key_hash": self._operation_key_hash(idempotency_key),
                        "action": "renamed",
                        "fingerprint": fingerprint,
                        "version": record.current_version,
                        "timestamp": now.isoformat(),
                    },
                )
            updated = ArtifactRecord(
                artifact_id=record.artifact_id,
                access_token_hash=record.access_token_hash,
                title=record.title,
                display_name=normalized_name,
                created_at=record.created_at,
                updated_at=now,
                expires_at=record.expires_at,
                current_version=record.current_version,
                versions=record.versions,
                source_snapshot=record.source_snapshot,
                operation_receipts=updated_receipts,
                audit_events=(
                    *record.audit_events,
                    self._audit_event(
                        "renamed",
                        detail={
                            "from": record.display_name,
                            "to": normalized_name,
                        },
                    ),
                ),
            )
            self._write(updated)

        return self._view(updated)

    @staticmethod
    def _operation_key_hash(
        idempotency_key: str,
    ) -> str:
        normalized = idempotency_key.strip()
        if not normalized:
            raise ArtifactConflictError(
                "Idempotency key cannot be empty."
            )
        return hashlib.sha256(
            normalized.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _operation_fingerprint(
        action: str,
        payload: dict[str, Any],
    ) -> str:
        encoded = json.dumps(
            {"action": action, "payload": payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _matching_receipt(
        record: ArtifactRecord,
        *,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        key_hash = ArtifactRepository._operation_key_hash(
            idempotency_key
        )
        return next(
            (
                receipt
                for receipt in record.operation_receipts
                if receipt.get("key_hash") == key_hash
            ),
            None,
        )

    def resolve_operation(
        self,
        artifact_id: str,
        access_token: str,
        *,
        idempotency_key: str | None,
        action: str,
        fingerprint: str,
    ) -> ArtifactView | None:
        if not idempotency_key:
            return None

        record = self._read(artifact_id)
        self._verify_access(record, access_token)
        receipt = self._matching_receipt(
            record,
            idempotency_key=idempotency_key,
        )

        if receipt is None:
            return None

        if (
            receipt.get("action") != action
            or receipt.get("fingerprint") != fingerprint
        ):
            raise ArtifactConflictError(
                "Idempotency key was reused for a different artifact operation."
            )

        return self._view(
            record,
            version=int(receipt["version"]),
        )

    def add_version(
        self,
        artifact_id: str,
        access_token: str,
        stored: StoredArtifact,
        *,
        source_content: str,
        specification: dict[str, Any],
        validation: dict[str, Any],
        page_or_slide_count: int,
        provider: str | None = None,
        model: str | None = None,
        request_id: str | None = None,
        expected_version: int | None = None,
        action: str = "revised",
        idempotency_key: str | None = None,
        operation_fingerprint: str | None = None,
    ) -> ArtifactView:
        with self._lock:
            record = self._read(artifact_id)
            self._verify_access(record, access_token)

            if idempotency_key:
                existing_receipt = self._matching_receipt(
                    record,
                    idempotency_key=idempotency_key,
                )
                if existing_receipt is not None:
                    if (
                        existing_receipt.get("action") != action
                        or existing_receipt.get("fingerprint")
                        != operation_fingerprint
                    ):
                        raise ArtifactConflictError(
                            "Idempotency key was reused for a different artifact operation."
                        )
                    self.artifact_storage.delete(
                        stored.artifact_id,
                        missing_ok=True,
                    )
                    return self._view(
                        record,
                        version=int(
                            existing_receipt["version"]
                        ),
                    )

            if (
                expected_version is not None
                and expected_version
                != record.current_version
            ):
                raise ArtifactConflictError(
                    "Artifact version changed before the operation completed."
                )

            new_version_number = record.version_count + 1
            version = ArtifactVersionRecord(
                version=new_version_number,
                physical_artifact_id=stored.artifact_id,
                filename=stored.filename,
                format=stored.format,
                media_type=stored.media_type,
                size_bytes=stored.size_bytes,
                sha256=stored.sha256,
                created_at=stored.created_at,
                expires_at=stored.expires_at,
                page_or_slide_count=page_or_slide_count,
                source_content=source_content,
                specification=specification,
                validation=validation,
                provider=provider,
                model=model,
                request_id=request_id,
            )
            display_name = normalize_display_filename(
                record.display_name,
                format=stored.format,
            )
            now = self._utc_now()
            updated_receipts = record.operation_receipts
            if idempotency_key:
                if not operation_fingerprint:
                    raise ArtifactConflictError(
                        "Operation fingerprint is required for idempotency."
                    )
                updated_receipts = (
                    *record.operation_receipts[-99:],
                    {
                        "key_hash": self._operation_key_hash(
                            idempotency_key
                        ),
                        "action": action,
                        "fingerprint": operation_fingerprint,
                        "version": new_version_number,
                        "timestamp": now.isoformat(),
                    },
                )

            updated = ArtifactRecord(
                artifact_id=record.artifact_id,
                access_token_hash=record.access_token_hash,
                title=(
                    str(specification.get("title", "")).strip()
                    or record.title
                ),
                display_name=display_name,
                created_at=record.created_at,
                updated_at=now,
                expires_at=max(
                    record.expires_at,
                    stored.expires_at,
                ),
                current_version=new_version_number,
                versions=(
                    *record.versions,
                    version,
                ),
                source_snapshot=record.source_snapshot,
                operation_receipts=updated_receipts,
                audit_events=(
                    *record.audit_events,
                    self._audit_event(
                        action,
                        detail={
                            "version": new_version_number,
                            "format": stored.format,
                        },
                    ),
                ),
            )
            self._write(updated)

        return self._view(updated)

    def restore(
        self,
        artifact_id: str,
        access_token: str,
        *,
        version: int,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> ArtifactView:
        with self._lock:
            record = self._read(artifact_id)
            self._verify_access(record, access_token)

            if (
                expected_version is not None
                and expected_version
                != record.current_version
            ):
                raise ArtifactConflictError(
                    "Artifact version changed before restore."
                )

            target = next(
                (
                    item
                    for item in record.versions
                    if item.version == version
                ),
                None,
            )

            if target is None:
                raise ArtifactNotFoundError(
                    "Artifact version was not found."
                )

            fingerprint = self._operation_fingerprint(
                "restored",
                {
                    "version": version,
                    "expected_version": expected_version,
                },
            )
            if idempotency_key:
                receipt = self._matching_receipt(
                    record,
                    idempotency_key=idempotency_key,
                )
                if receipt is not None:
                    if (
                        receipt.get("action") != "restored"
                        or receipt.get("fingerprint") != fingerprint
                    ):
                        raise ArtifactConflictError(
                            "Idempotency key was reused for a different artifact operation."
                        )
                    return self._view(record, version=version)

            now = self._utc_now()
            updated_receipts = record.operation_receipts
            if idempotency_key:
                updated_receipts = (
                    *record.operation_receipts[-99:],
                    {
                        "key_hash": self._operation_key_hash(idempotency_key),
                        "action": "restored",
                        "fingerprint": fingerprint,
                        "version": version,
                        "timestamp": now.isoformat(),
                    },
                )
            updated = ArtifactRecord(
                artifact_id=record.artifact_id,
                access_token_hash=record.access_token_hash,
                title=record.title,
                display_name=normalize_display_filename(
                    record.display_name,
                    format=target.format,
                ),
                created_at=record.created_at,
                updated_at=now,
                expires_at=record.expires_at,
                current_version=version,
                versions=record.versions,
                source_snapshot=record.source_snapshot,
                operation_receipts=updated_receipts,
                audit_events=(
                    *record.audit_events,
                    self._audit_event(
                        "restored",
                        detail={"version": version},
                    ),
                ),
            )
            self._write(updated)

        return self._view(updated)

    def list_versions(
        self,
        artifact_id: str,
        access_token: str,
    ) -> tuple[ArtifactVersionRecord, ...]:
        record = self._read(artifact_id)
        self._verify_access(record, access_token)
        return tuple(
            sorted(
                record.versions,
                key=lambda item: item.version,
                reverse=True,
            )
        )

    def list_audit_events(
        self,
        artifact_id: str,
        access_token: str,
    ) -> tuple[dict[str, Any], ...]:
        record = self._read(artifact_id)
        self._verify_access(record, access_token)
        return record.audit_events

    def stats(self) -> dict[str, int]:
        artifact_count = 0
        version_count = 0

        with self._lock:
            for directory in self.root_directory.iterdir():
                if (
                    directory.is_symlink()
                    or not directory.is_dir()
                    or directory.name == _CREATION_IDEMPOTENCY_DIRECTORY
                ):
                    continue

                try:
                    record = self._read(directory.name)
                except (
                    ArtifactNotFoundError,
                    ArtifactRepositoryError,
                ):
                    continue

                artifact_count += 1
                version_count += record.version_count

        return {
            "artifact_count": artifact_count,
            "version_count": version_count,
        }

    def cleanup_expired(self) -> int:
        deleted_count = 0
        now = self._utc_now()

        with self._lock:
            for directory in list(
                self.root_directory.iterdir()
            ):
                if (
                    directory.is_symlink()
                    or not directory.is_dir()
                    or directory.name == _CREATION_IDEMPOTENCY_DIRECTORY
                ):
                    continue

                try:
                    record = self._read(
                        directory.name
                    )
                except (
                    ArtifactNotFoundError,
                    ArtifactRepositoryError,
                ):
                    continue

                if now < record.expires_at:
                    continue

                for version in record.versions:
                    self.artifact_storage.delete(
                        version.physical_artifact_id,
                        missing_ok=True,
                    )

                shutil.rmtree(
                    directory,
                    ignore_errors=True,
                )
                deleted_count += 1

            for receipt_path in self._creation_idempotency_directory.glob("*.json"):
                try:
                    payload = json.loads(
                        receipt_path.read_text(encoding="utf-8")
                    )
                    expires_at = _parse_datetime(payload["expires_at"])
                    if expires_at <= now:
                        receipt_path.unlink(missing_ok=True)
                except Exception:
                    receipt_path.unlink(missing_ok=True)

        return deleted_count

    def delete(
        self,
        artifact_id: str,
        access_token: str,
    ) -> bool:
        with self._lock:
            record = self._read(artifact_id)
            self._verify_access(record, access_token)

            physical_ids = {
                version.physical_artifact_id
                for version in record.versions
            }

            for physical_id in physical_ids:
                try:
                    self.artifact_storage.delete(
                        physical_id,
                        missing_ok=True,
                    )
                except ArtifactStorageError:
                    raise

            directory = self._record_directory(
                artifact_id
            )
            shutil.rmtree(
                directory,
                ignore_errors=False,
            )

        return True
