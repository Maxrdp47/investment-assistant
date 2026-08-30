from __future__ import annotations

from scripts.sync_fx_pit_foundations_kb import (
    EXPERIMENT_ID,
    HYPOTHESIS_ID,
    RESULT_ID,
    sync_references,
)


class FakeWorkflow:
    def get_work_request(self, request_id, include_context=False):
        return {
            "current_status": "COMPLETED",
            "result_id": RESULT_ID,
            "hypothesis_id": HYPOTHESIS_ID,
            "experiment_id": EXPERIMENT_ID,
        }


class FakeKnowledge:
    def __init__(self):
        self.references = []

    def get_experiment(self, experiment_id):
        return {"current_status": "COMPLETED"}

    def get_result(self, result_id):
        return {
            "experiment_id": EXPERIMENT_ID,
            "conclusion": "inconclusive",
            "sample_size": 0,
            "references": list(self.references),
        }

    def add_external_reference(self, **reference):
        self.references.append(
            {
                "system": reference["system"],
                "record_type": reference["record_type"],
                "record_id": reference["record_id"],
            }
        )


def test_sync_is_idempotent_and_does_not_rewrite_result() -> None:
    knowledge = FakeKnowledge()
    references = [
        {"system": "fx", "record_type": "artifact", "record_id": "abc"}
    ]
    first = sync_references(
        knowledge=knowledge,
        workflow=FakeWorkflow(),
        references=references,
        created_at="2026-08-29T12:00:00+00:00",
    )
    second = sync_references(
        knowledge=knowledge,
        workflow=FakeWorkflow(),
        references=references,
        created_at="2026-08-29T12:00:00+00:00",
    )
    assert first["references_inserted"] == 1
    assert second["references_inserted"] == 0
    assert second["references_deduplicated"] == 1
    assert second["result_conclusion_unchanged"] == "inconclusive"
    assert second["result_sample_size_unchanged"] == 0
