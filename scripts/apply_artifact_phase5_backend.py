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


def patch_app(
    content: str,
) -> str:
    composer_import = """from routes.artifact_composer import (
    router as artifact_composer_router,
)
"""

    if composer_import not in content:
        marker = (
            "from routes.artifacts import "
            "router as artifacts_router\n"
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "Artifact route import "
                    "marker was not found."
                )
            )

        content = content.replace(
            marker,
            marker + composer_import,
            1,
        )

    delete_method = '        "DELETE",\n'

    if delete_method not in content:
        marker = (
            '        "POST",\n'
            '        "OPTIONS",\n'
        )

        replacement = (
            '        "POST",\n'
            '        "DELETE",\n'
            '        "OPTIONS",\n'
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "CORS method marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            replacement,
            1,
        )

    composer_router_block = """app.include_router(
    artifact_composer_router,
    prefix="/api/v1",
)
"""

    if composer_router_block not in content:
        artifacts_router_block = """app.include_router(
    artifacts_router,
    prefix="/api/v1",
)
"""

        if artifacts_router_block not in content:
            raise RuntimeError(
                (
                    "Artifact router block "
                    "was not found."
                )
            )

        content = content.replace(
            artifacts_router_block,
            (
                artifacts_router_block
                + "\n"
                + composer_router_block
            ),
            1,
        )

    return content


def verify_phase5_files() -> None:
    required_files = [
        (
            "backend/schemas/"
            "artifact_composer.py"
        ),
        (
            "backend/artifacts/"
            "composer.py"
        ),
        (
            "backend/routes/"
            "artifact_composer.py"
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
                "Phase 5 backend files "
                "are missing:\n"
                f"{formatted}"
            )
        )

    print(
        (
            "PASS: All Phase 5 backend "
            "files exist"
        )
    )


def main() -> None:
    verify_phase5_files()

    update_file(
        "backend/app.py",
        patch_app,
    )

    print()
    print(
        (
            "PASS: Phase 5 backend "
            "integration applied"
        )
    )


if __name__ == "__main__":
    main()