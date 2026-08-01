from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from artifacts.models import ArtifactDocument
from artifacts.repository import ArtifactView
from artifacts.storage import StoredArtifact
from schemas.chat import ChatResponse


@runtime_checkable
class ArtifactBinaryStorage(Protocol):
    """Binary artifact persistence contract.

    The current implementation is filesystem-backed. Object-storage
    adapters can implement this protocol without changing lifecycle logic.
    """

    root_directory: Path

    def create(
        self,
        artifact: ArtifactDocument,
        *,
        format: object,
        filename: str | None = None,
    ) -> StoredArtifact: ...

    def get(self, artifact_id: str) -> StoredArtifact: ...

    def delete(
        self,
        artifact_id: str,
        *,
        missing_ok: bool = False,
    ) -> bool: ...

    def cleanup_expired(self, **kwargs: Any) -> int: ...

    def stats(self) -> dict[str, int]: ...


@runtime_checkable
class ArtifactMetadataRepository(Protocol):
    """Logical artifact, version, access, idempotency, and audit contract."""

    def get(
        self,
        artifact_id: str,
        access_token: str,
        *,
        version: int | None = None,
    ) -> ArtifactView: ...

    def get_internal(
        self,
        artifact_id: str,
        *,
        version: int | None = None,
    ) -> ArtifactView: ...

    def stats(self) -> dict[str, int]: ...


@runtime_checkable
class ArtifactAnswerRouter(Protocol):
    """Minimal provider-router contract used by artifact composition."""

    async def answer(
        self,
        *,
        message: str,
        history: list[object],
    ) -> ChatResponse: ...
