from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from artifacts.models import (
    ArtifactDocument,
    ArtifactSection,
    ParagraphBlock,
)
from artifacts.storage import (
    ArtifactNotFoundError,
    ArtifactStorage,
)


class ArtifactStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory(
                prefix="authentic-artifact-storage-test-"
            )
        )

        self.storage_root = Path(
            self.temporary_directory.name
        )

        self.storage = ArtifactStorage(
            self.storage_root,
            retention_hours=1,
            maximum_file_bytes=10 * 1024 * 1024,
        )

        self.document = ArtifactDocument(
            title="Authentic AI Storage Test",
            subtitle="Secure storage validation",
            author="Authentic AI",
            sections=(
                ArtifactSection(
                    title="Summary",
                    level=1,
                    blocks=(
                        ParagraphBlock(
                            text=(
                                "This artifact validates private "
                                "storage, metadata, retrieval, "
                                "expiry cleanup and deletion."
                            )
                        ),
                    ),
                ),
            ),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_get_and_delete(self) -> None:
        stored = self.storage.create(
            self.document,
            format="pdf",
            filename="Authentic AI: Storage Report",
        )

        self.assertEqual(
            len(stored.artifact_id),
            32,
        )

        self.assertEqual(
            stored.filename,
            "Authentic-AI-Storage-Report.pdf",
        )

        self.assertEqual(
            stored.media_type,
            "application/pdf",
        )

        self.assertTrue(
            stored.path.is_file()
        )

        self.assertGreater(
            stored.size_bytes,
            1_000,
        )

        self.assertEqual(
            len(stored.sha256),
            64,
        )

        metadata_path = (
            stored.path.parent
            / "metadata.json"
        )

        self.assertTrue(
            metadata_path.is_file()
        )

        metadata = json.loads(
            metadata_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            metadata["artifact_id"],
            stored.artifact_id,
        )

        self.assertEqual(
            metadata["filename"],
            stored.filename,
        )

        loaded = self.storage.get(
            stored.artifact_id
        )

        self.assertEqual(
            loaded.sha256,
            stored.sha256,
        )

        self.assertEqual(
            loaded.path,
            stored.path,
        )

        self.assertTrue(
            self.storage.delete(
                stored.artifact_id
            )
        )

        self.assertFalse(
            stored.path.parent.exists()
        )

        with self.assertRaises(
            ArtifactNotFoundError
        ):
            self.storage.get(
                stored.artifact_id
            )

    def test_invalid_identifier_is_rejected(
        self,
    ) -> None:
        for invalid_id in (
            "../outside",
            "not-an-artifact-id",
            "a" * 31,
            "g" * 32,
        ):
            with self.subTest(
                invalid_id=invalid_id
            ):
                with self.assertRaises(
                    ArtifactNotFoundError
                ):
                    self.storage.get(
                        invalid_id
                    )

    def test_expired_cleanup_removes_artifact(
        self,
    ) -> None:
        stored = self.storage.create(
            self.document,
            format="docx",
            filename="Expiring Artifact",
        )

        cleanup_time = (
            stored.expires_at
            + timedelta(
                seconds=1
            )
        )

        deleted_count = (
            self.storage.cleanup_expired(
                now=cleanup_time
            )
        )

        self.assertEqual(
            deleted_count,
            1,
        )

        self.assertFalse(
            stored.path.parent.exists()
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )