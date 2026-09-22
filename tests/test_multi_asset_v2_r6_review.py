from __future__ import annotations

import math

import numpy as np
import pytest

from multi_asset_discovery_v1 import fingerprint
from multi_asset_v2_r6_review import (
    Moments,
    _feature_values,
    _joined_payloads_valid,
    render_descriptive_report_markdown,
)


def test_streaming_moments_match_direct_correlation() -> None:
    x = np.asarray([1.0, 2.0, 3.0, np.nan, 4.0])
    y = np.asarray([2.0, 1.0, 5.0, 99.0, 8.0])
    moments = Moments()
    moments.update(x[:2], y[:2])
    moments.update(x[2:], y[2:])
    result = moments.result()
    mask = np.isfinite(x) & np.isfinite(y)
    assert result["n"] == 4
    assert result["correlation"] == pytest.approx(np.corrcoef(x[mask], y[mask])[0, 1])


def test_review_feature_projection_never_turns_missing_into_zero() -> None:
    parent_feature = {
        "features": {
            "return_20": {"status": "AVAILABLE", "value": 0.1},
            "return_60": {"status": "UNKNOWN", "value": None},
            "ema_20": {"status": "AVAILABLE", "value": 100.0},
            "ema_50": {"status": "AVAILABLE", "value": 90.0},
        },
        "safe_zones": {"A": {"lower": 80.0}},
    }
    parent_outcome = {"signal_close": 110.0}
    delta = {
        "feature_values": {"r4b.relative_momentum_20": 0.2},
        "missing_features": {"r4b.relative_momentum_60": {"status": "UNKNOWN"}},
    }
    names = [
        "core.return_20", "core.return_60", "core.close_vs_ema20_pct",
        "core.ema20_vs_ema50_pct", "core.safe_zone_a_distance_pct",
        "r4b.relative_momentum_20", "r4b.relative_momentum_60",
    ]
    values = _feature_values(parent_feature, parent_outcome, delta, names)
    assert values["core.return_20"] == 0.1
    assert "core.return_60" not in values
    assert "r4b.relative_momentum_60" not in values
    assert values["core.close_vs_ema20_pct"] == pytest.approx(0.1)
    assert values["core.ema20_vs_ema50_pct"] == pytest.approx(100.0 / 90.0 - 1.0)
    assert values["core.safe_zone_a_distance_pct"] == pytest.approx(110.0 / 80.0 - 1.0)
    assert math.isfinite(values["r4b.relative_momentum_20"])


def test_joined_payload_validation_covers_r6_outcome_reference() -> None:
    case_id = "case-1"
    parent_feature = {"case_id": case_id, "value": 1.0}
    parent_feature["feature_fingerprint"] = fingerprint(parent_feature)
    parent_outcome = {
        "case_id": case_id,
        "feature_fingerprint": parent_feature["feature_fingerprint"],
        "value": 2.0,
    }
    parent_outcome["outcome_fingerprint"] = fingerprint(parent_outcome)
    delta = {
        "case_id": case_id,
        "parent_case_id": case_id,
        "parent_feature_fingerprint": parent_feature["feature_fingerprint"],
        "feature_values": {},
    }
    delta["feature_fingerprint"] = fingerprint(delta)
    r6_outcome = {
        "case_id": case_id,
        "parent_case_id": case_id,
        "feature_fingerprint": delta["feature_fingerprint"],
        "parent_outcome_fingerprint": parent_outcome["outcome_fingerprint"],
        "outcome_values_copied": False,
    }
    r6_outcome["outcome_fingerprint"] = fingerprint(r6_outcome)
    arguments = {
        "case_id": case_id,
        "delta_fingerprint": delta["feature_fingerprint"],
        "r6_outcome_fingerprint": r6_outcome["outcome_fingerprint"],
        "r6_feature_link": delta["feature_fingerprint"],
        "parent_feature_fingerprint": parent_feature["feature_fingerprint"],
        "parent_outcome_fingerprint": parent_outcome["outcome_fingerprint"],
        "parent_outcome_link": parent_feature["feature_fingerprint"],
        "delta": delta,
        "r6_outcome": r6_outcome,
        "parent_feature": parent_feature,
        "parent_outcome": parent_outcome,
    }
    assert _joined_payloads_valid(**arguments)

    tampered = dict(r6_outcome)
    tampered["parent_outcome_fingerprint"] = "tampered"
    assert not _joined_payloads_valid(**{**arguments, "r6_outcome": tampered})


def test_descriptive_markdown_keeps_all_outcome_dimensions_visible() -> None:
    report = {
        "status": "R6_DESCRIPTIVE_COMPLETE_NO_ROBUST_CANDIDATE",
        "run_id": "run-1",
        "cases_reviewed": 10,
        "feature_count": 1,
        "robust_candidate_count": 0,
        "artifact_fingerprint": "abc",
        "candidate_gate_reason": "DEPENDENCY_FAIL",
        "quality_c_dimensions": {"DEPENDENCIES": "FAIL"},
        "association_rows": [
            {
                "feature": "core.return_20",
                "family": "PRICE_RETURNS",
                "horizon": 20,
                "outcomes": {
                    metric: {"n": 10, "correlation": value}
                    for metric, value in {
                        "return_pct": 0.1,
                        "mfe_pct": 0.2,
                        "mae_pct": -0.3,
                    }.items()
                },
            }
        ],
    }
    rendered = render_descriptive_report_markdown(report)
    assert "`core.return_20`" in rendered
    assert "0.100000" in rendered
    assert "0.200000" in rendered
    assert "-0.300000" in rendered
    assert "keine nach Rendite ausgewählte Rangliste" in rendered
