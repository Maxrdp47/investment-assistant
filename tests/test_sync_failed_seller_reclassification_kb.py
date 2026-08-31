from __future__ import annotations

from pathlib import Path

from scripts.sync_failed_seller_reclassification_kb import (
    ORIGINAL_RUN_ID,
    RESULT_ID,
    sync_reference,
)


class _Knowledge:
    def __init__(self) -> None:
        self.references: list[dict[str, object]] = []

    def get_result(self, result_id: str) -> dict[str, object]:
        assert result_id == RESULT_ID
        return {
            "id": RESULT_ID,
            "conclusion": "inconclusive",
            "sample_size": 379_039,
            "references": list(self.references),
            "validation_assessments": [],
            "work_request_links": [],
        }

    def add_external_reference(self, **values: object) -> dict[str, object]:
        self.references.append(dict(values))
        return dict(values)


def _payload() -> dict[str, object]:
    return {
        "status": "COMPLETED_READ_ONLY_RECLASSIFICATION",
        "original_run_id": ORIGINAL_RUN_ID,
        "raw_metrics_changed": False,
        "reclassification_id": "failed-seller-reclassification-pytest",
    }


def test_sync_is_append_only_idempotent_and_preserves_result_core(tmp_path: Path) -> None:
    knowledge = _Knowledge()
    artifact = tmp_path / "assessment.json"
    artifact.write_text("{}\n", encoding="utf-8")

    first = sync_reference(
        knowledge,
        payload=_payload(),
        artifact_path=artifact,
        created_at="2026-08-31T10:00:00+00:00",
    )
    second = sync_reference(
        knowledge,
        payload=_payload(),
        artifact_path=artifact,
        created_at="2026-08-31T10:00:00+00:00",
    )

    assert first["reference_inserted"] == 1
    assert second["reference_inserted"] == 0
    assert second["reference_deduplicated"] == 1
    assert first["result_core_fingerprint_before"] == first[
        "result_core_fingerprint_after"
    ]
    assert len(knowledge.references) == 1
