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


def patch_navigation(
    content: str,
) -> str:
    page_member = (
        "  | 'artifact-studio'\n"
    )

    if page_member not in content:
        marker = "  | 'projects'\n"

        if marker not in content:
            raise RuntimeError(
                (
                    "Navigation page marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            marker + page_member,
            1,
        )

    title_entry = (
        "  'artifact-studio': "
        "'Artifact Studio',\n"
    )

    if title_entry not in content:
        marker = (
            "  projects: 'Projects',\n"
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "Navigation title marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            marker + title_entry,
            1,
        )

    return content


def patch_sidebar(
    content: str,
) -> str:
    icon_import = "  FileOutput,\n"

    if icon_import not in content:
        marker = "  Folder,\n"

        if marker not in content:
            raise RuntimeError(
                (
                    "Sidebar icon import "
                    "marker was not found."
                )
            )

        content = content.replace(
            marker,
            marker + icon_import,
            1,
        )

    navigation_item = """  {
    id: 'artifact-studio',
    label: 'Artifact Studio',
    icon: FileOutput,
  },
"""

    if navigation_item not in content:
        marker = """  {
    id: 'projects',
    label: 'Projects',
    icon: Folder,
  },
"""

        if marker not in content:
            raise RuntimeError(
                (
                    "Sidebar navigation "
                    "marker was not found."
                )
            )

        content = content.replace(
            marker,
            marker + navigation_item,
            1,
        )

    return content


def patch_app(
    content: str,
) -> str:
    page_import = (
        "import { ArtifactStudio } "
        "from './pages/ArtifactStudio'\n"
    )

    if page_import not in content:
        marker = (
            "import { Memory } "
            "from './pages/Memory'\n"
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "App page import marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            marker + page_import,
            1,
        )

    style_import = (
        "import "
        "'./styles/artifact-studio.css'\n"
    )

    if style_import not in content:
        marker = (
            "import "
            "'./styles/visualization.css'\n"
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "App stylesheet marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            marker + style_import,
            1,
        )

    page_block = """    if (
      activePage === 'artifact-studio'
    ) {
      return <ArtifactStudio />
    }

"""

    if page_block not in content:
        marker = (
            "    if (activePage === 'memory') {\n"
        )

        if marker not in content:
            raise RuntimeError(
                (
                    "App page-routing marker "
                    "was not found."
                )
            )

        content = content.replace(
            marker,
            page_block + marker,
            1,
        )

    return content


def verify_created_files() -> None:
    required_files = [
        (
            "frontend/src/types/"
            "artifacts.ts"
        ),
        (
            "frontend/src/services/"
            "artifacts.ts"
        ),
        (
            "frontend/src/components/"
            "Artifacts/"
            "ArtifactFormatSelector.tsx"
        ),
        (
            "frontend/src/components/"
            "Artifacts/"
            "ArtifactResultCard.tsx"
        ),
        (
            "frontend/src/pages/"
            "ArtifactStudio.tsx"
        ),
        (
            "frontend/src/styles/"
            "artifact-studio.css"
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
                "Phase 4 files are missing:\n"
                f"{formatted}"
            )
        )

    print(
        "PASS: All Phase 4 files exist"
    )


def main() -> None:
    verify_created_files()

    update_file(
        (
            "frontend/src/types/"
            "navigation.ts"
        ),
        patch_navigation,
    )

    update_file(
        (
            "frontend/src/components/"
            "Sidebar/Sidebar.tsx"
        ),
        patch_sidebar,
    )

    update_file(
        "frontend/src/App.tsx",
        patch_app,
    )

    print()
    print(
        (
            "PASS: Phase 4 frontend "
            "integration applied"
        )
    )


if __name__ == "__main__":
    main()