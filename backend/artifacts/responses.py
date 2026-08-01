from __future__ import annotations

from typing import Any

from artifacts.repository import ArtifactView


def artifact_response_payload(
    view: ArtifactView,
    *,
    access_token: str,
) -> dict[str, Any]:
    validation = dict(view.version.validation)

    return {
        "artifact_id": view.record.artifact_id,
        "access_token": access_token,
        "filename": view.record.display_name,
        "title": view.record.title,
        "format": view.version.format,
        "media_type": view.version.media_type,
        "size_bytes": view.version.size_bytes,
        "sha256": view.version.sha256,
        "created_at": view.record.created_at,
        "updated_at": view.record.updated_at,
        "expires_at": view.record.expires_at,
        "download_url": (
            f"/api/v1/artifacts/"
            f"{view.record.artifact_id}/download"
        ),
        "version": view.version.version,
        "version_count": view.record.version_count,
        "page_or_slide_count": (
            view.version.page_or_slide_count
        ),
        "validation": {
            "status": validation.get("status", "passed"),
            "page_or_slide_count": validation.get(
                "page_or_slide_count",
                view.version.page_or_slide_count,
            ),
            "error_count": validation.get("error_count", 0),
            "warning_count": validation.get("warning_count", 0),
            "issues": validation.get("issues", []),
        },
    }
