from __future__ import annotations

from scripts import run_water_infrastructure_research as runner
from water_infrastructure_research import load_contract


def test_kb_result_uses_numeric_costs_and_does_not_invent_slippage() -> None:
    class WorkflowStub:
        def complete_work_request(self, request_id, **kwargs):
            self.request_id = request_id
            self.kwargs = kwargs
            return {"id": request_id, "current_status": "COMPLETED"}

    workflow = WorkflowStub()
    contract = load_contract()
    review = {
        "stage": "development",
        "decision": "DEVELOPMENT_INCONCLUSIVE",
        "review_fingerprint": "a" * 64,
        "treatment": {"n": 7, "mean": 0.01},
    }
    runner._complete_kb(
        workflow,
        contract,
        {"claim_token": "test"},
        review,
        {"development": review},
        "2026-09-22T00:00:00+00:00",
    )
    result = workflow.kwargs["result"]
    assert result["costs"] == 0.0018
    assert result["slippage"] is None
    assert result["validation"]["status"] == "NOT_RUN"
    assert result["out_of_sample"]["status"] == "NOT_RUN"
