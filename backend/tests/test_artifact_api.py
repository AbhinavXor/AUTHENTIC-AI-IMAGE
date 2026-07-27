from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app
from artifacts.storage import ArtifactStorage


class ArtifactApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory(
                prefix="authentic-artifact-api-test-"
            )
        )

        self.storage = ArtifactStorage(
            Path(self.temporary_directory.name),
            retention_hours=1,
            maximum_file_bytes=10 * 1024 * 1024,
        )

        self.storage_patch = patch(
            "routes.artifacts.get_artifact_storage",
            return_value=self.storage,
        )

        self.storage_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.storage_patch.stop()
        self.temporary_directory.cleanup()

    def test_generate_metadata_download_and_delete(self) -> None:
        generation_response = self.client.post(
            "/api/v1/artifacts/generate",
            json={
                "content": (
                    "# Authentic AI API Report\n\n"
                    "## Executive Summary\n\n"
                    "This report validates secure artifact "
                    "generation and download delivery.\n\n"
                    "## Capabilities\n\n"
                    "- Professional PDF generation\n"
                    "- Private storage\n"
                    "- Expiring download delivery\n"
                ),
                "format": "pdf",
                "title": "Authentic AI API Report",
                "subtitle": "End-to-End API Test",
                "author": "Authentic AI",
                "filename": "Authentic AI: API Report",
            },
        )

        self.assertEqual(
            generation_response.status_code,
            201,
            generation_response.text,
        )

        payload = generation_response.json()

        artifact_id = payload["artifact_id"]

        self.assertEqual(
            len(artifact_id),
            32,
        )
        self.assertEqual(
            payload["filename"],
            "Authentic-AI-API-Report.pdf",
        )
        self.assertEqual(
            payload["format"],
            "pdf",
        )
        self.assertEqual(
            payload["media_type"],
            "application/pdf",
        )
        self.assertGreater(
            payload["size_bytes"],
            1_000,
        )
        self.assertEqual(
            len(payload["sha256"]),
            64,
        )
        self.assertEqual(
            payload["download_url"],
            (
                f"/api/v1/artifacts/"
                f"{artifact_id}/download"
            ),
        )

        metadata_response = self.client.get(
            f"/api/v1/artifacts/{artifact_id}"
        )

        self.assertEqual(
            metadata_response.status_code,
            200,
            metadata_response.text,
        )
        self.assertEqual(
            metadata_response.json()["sha256"],
            payload["sha256"],
        )

        download_response = self.client.get(
            payload["download_url"]
        )

        self.assertEqual(
            download_response.status_code,
            200,
            download_response.text,
        )
        self.assertEqual(
            download_response.headers[
                "content-type"
            ],
            "application/pdf",
        )
        self.assertEqual(
            download_response.headers[
                "x-artifact-sha256"
            ],
            payload["sha256"],
        )
        self.assertIn(
            "attachment",
            download_response.headers[
                "content-disposition"
            ],
        )
        self.assertTrue(
            download_response.content.startswith(
                b"%PDF-"
            )
        )
        self.assertGreater(
            len(download_response.content),
            1_000,
        )

        deletion_response = self.client.delete(
            f"/api/v1/artifacts/{artifact_id}"
        )

        self.assertEqual(
            deletion_response.status_code,
            200,
            deletion_response.text,
        )
        self.assertEqual(
            deletion_response.json(),
            {
                "artifact_id": artifact_id,
                "deleted": True,
            },
        )

        missing_response = self.client.get(
            f"/api/v1/artifacts/{artifact_id}"
        )

        self.assertEqual(
            missing_response.status_code,
            404,
        )

    def test_invalid_format_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/artifacts/generate",
            json={
                "content": "# Invalid Format\n\nTest.",
                "format": "xlsx",
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )

    def test_unknown_request_field_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/artifacts/generate",
            json={
                "content": "# Unknown Field\n\nTest.",
                "format": "pdf",
                "unexpected": True,
            },
        )

        self.assertEqual(
            response.status_code,
            422,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )