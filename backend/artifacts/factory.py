from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from artifacts.contracts import ArtifactAnswerRouter
from artifacts.repository import ArtifactRepository
from artifacts.service import ArtifactLifecycleService
from artifacts.storage import ArtifactStorage


@dataclass(frozen=True, slots=True)
class ArtifactRuntime:
    storage: ArtifactStorage
    repository: ArtifactRepository
    lifecycle: ArtifactLifecycleService


@lru_cache(maxsize=1)
def build_artifact_runtime(
    model_router: ArtifactAnswerRouter,
) -> ArtifactRuntime:
    """Build the default local runtime.

    A deployment can replace this factory with database/object-storage
    adapters while preserving route and service contracts.
    """

    storage = ArtifactStorage()
    repository = ArtifactRepository(storage)
    lifecycle = ArtifactLifecycleService(
        artifact_storage=storage,
        artifact_repository=repository,
        model_router=model_router,
    )
    return ArtifactRuntime(
        storage=storage,
        repository=repository,
        lifecycle=lifecycle,
    )
