from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    PROJECT_ROOT
    / "backend"
    / "tests"
    / "fixtures"
    / "mathematics_authoritative_source.txt"
)
RECORD = (
    PROJECT_ROOT
    / "backend"
    / "data"
    / "generated_artifacts"
    / "_records"
    / "5bdcb51871394952843a581aa21e37a4"
    / "artifact.json"
)


def main() -> None:
    source = FIXTURE.read_text(
        encoding="utf-8",
    ).strip()

    required_markers = (
        "1. Mathematical Thinking",
        "25. Integration by Substitution",
        "31. Regression",
        "37. Final Verification Checklist",
    )
    missing = [
        marker
        for marker in required_markers
        if marker not in source
    ]
    if missing:
        raise SystemExit(
            "Authoritative fixture is incomplete: "
            + ", ".join(missing)
        )

    payload = json.loads(
        RECORD.read_text(
            encoding="utf-8",
        )
    )
    if (
        payload.get("artifact_id")
        != RECORD.parent.name
    ):
        raise SystemExit(
            "Artifact record identity check failed."
        )

    existing = payload.get(
        "source_snapshot",
        {},
    )
    existing_content = str(
        existing.get("content")
        or ""
    )
    if (
        "25. Integration by Substitution"
        in existing_content
        and "37. Final Verification Checklist"
        in existing_content
    ):
        print(
            "Legacy mathematics source is already repaired."
        )
        return

    backup = RECORD.with_name(
        "artifact.json.pre-source-repair-"
        + datetime.now().strftime(
            "%Y%m%d-%H%M%S",
        )
    )
    shutil.copy2(
        RECORD,
        backup,
    )

    payload["source_snapshot"] = {
        "attachment_names": [],
        "confidence": 1.0,
        "content": source,
        "kind": "explicit_prompt",
        "message_ids": [],
        "summary": (
            "Complete authoritative mathematics source "
            "covering algebra, calculus, probability, "
            "statistics, modelling, graphs and verification."
        ),
    }

    temporary = RECORD.with_suffix(
        ".json.tmp",
    )
    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(RECORD)

    print(
        "Repaired legacy mathematics source record."
    )
    print(
        f"Backup: {backup}"
    )


if __name__ == "__main__":
    main()
