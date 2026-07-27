from __future__ import annotations

from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]


def update_file(
    relative_path: str,
    transform: Callable[[str], str],
) -> None:
    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    content = path.read_text(
        encoding="utf-8",
    )

    updated = transform(content)

    if updated == content:
        print(
            f"UNCHANGED: {relative_path}"
        )
        return

    path.write_text(
        updated,
        encoding="utf-8",
    )

    print(
        f"UPDATED: {relative_path}"
    )


def replace_once(
    content: str,
    old: str,
    new: str,
    *,
    description: str,
) -> str:
    if new in content:
        return content

    if old not in content:
        raise RuntimeError(
            f"{description} marker was not found."
        )

    return content.replace(
        old,
        new,
        1,
    )


def patch_app(
    content: str,
) -> str:
    content = replace_once(
        content,
        """from typing import Any

import uvicorn
""",
        """import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
""",
        description=(
            "FastAPI lifespan imports"
        ),
    )

    job_route_import = """from routes.artifact_jobs import (
    recover_interrupted_artifact_jobs,
    router as artifact_jobs_router,
    shutdown_artifact_job_runner,
)
"""

    if job_route_import not in content:
        composer_import = """from routes.artifact_composer import (
    router as artifact_composer_router,
)
"""

        if composer_import not in content:
            raise RuntimeError(
                (
                    "Artifact composer import "
                    "marker was not found."
                )
            )

        content = content.replace(
            composer_import,
            (
                composer_import
                + job_route_import
            ),
            1,
        )

    lifespan_block = """@asynccontextmanager
async def lifespan(
    _: FastAPI,
) -> AsyncIterator[None]:
    await asyncio.to_thread(
        recover_interrupted_artifact_jobs
    )

    try:
        yield
    finally:
        await shutdown_artifact_job_runner()


"""

    if lifespan_block not in content:
        app_marker = "app = FastAPI(\n"

        if app_marker not in content:
            raise RuntimeError(
                (
                    "FastAPI application "
                    "marker was not found."
                )
            )

        content = content.replace(
            app_marker,
            lifespan_block + app_marker,
            1,
        )

    content = replace_once(
        content,
        """    description=(
        "Private backend API for Authentic AI Image."
    ),
)
""",
        """    description=(
        "Private backend API for Authentic AI Image."
    ),
    lifespan=lifespan,
)
""",
        description=(
            "FastAPI lifespan configuration"
        ),
    )

    token_header = (
        '        "X-Artifact-Job-Token",\n'
    )

    if token_header not in content:
        header_marker = (
            '        "Content-Type",\n'
        )

        if header_marker not in content:
            raise RuntimeError(
                (
                    "CORS header marker "
                    "was not found."
                )
            )

        content = content.replace(
            header_marker,
            header_marker + token_header,
            1,
        )

    jobs_router_block = """app.include_router(
    artifact_jobs_router,
    prefix="/api/v1",
)
"""

    if jobs_router_block not in content:
        composer_router_block = """app.include_router(
    artifact_composer_router,
    prefix="/api/v1",
)
"""

        if composer_router_block not in content:
            raise RuntimeError(
                (
                    "Artifact composer router "
                    "block was not found."
                )
            )

        content = content.replace(
            composer_router_block,
            (
                composer_router_block
                + "\n"
                + jobs_router_block
            ),
            1,
        )

    return content


def verify_phase6_backend_files() -> None:
    required_files = [
        (
            "backend/core/"
            "artifact_job_settings.py"
        ),
        (
            "backend/schemas/"
            "artifact_jobs.py"
        ),
        (
            "backend/artifacts/"
            "job_store.py"
        ),
        (
            "backend/core/"
            "artifact_job_rate_limit.py"
        ),
        (
            "backend/artifacts/"
            "job_runner.py"
        ),
        (
            "backend/routes/"
            "artifact_jobs.py"
        ),
    ]

    missing_files = [
        relative_path
        for relative_path in required_files
        if not (
            ROOT / relative_path
        ).is_file()
    ]

    if missing_files:
        formatted = "\n".join(
            f"- {path}"
            for path in missing_files
        )

        raise FileNotFoundError(
            (
                "Phase 6 backend files "
                "are missing:\n"
                f"{formatted}"
            )
        )

    print(
        (
            "PASS: All Phase 6 backend "
            "files exist"
        )
    )


def main() -> None:
    verify_phase6_backend_files()

    update_file(
        "backend/app.py",
        patch_app,
    )

    print()
    print(
        (
            "PASS: Phase 6 backend "
            "integration applied"
        )
    )


if __name__ == "__main__":
    main()