from __future__ import annotations

from forecast_metrics import binary_up_metrics, percentage, probability_metrics, wilson_interval


def test_percentage_and_wilson_interval_are_honest_for_small_samples() -> None:
    assert percentage(2, 4) == 50.0
    assert percentage(0, 0) is None
    low, high = wilson_interval(1, 1)
    assert low == 20.7
    assert high == 100.0
    assert wilson_interval(0, 0) == (None, None)


def test_binary_up_metrics_require_both_classes_for_balanced_accuracy() -> None:
    balanced = binary_up_metrics(tp=1, fp=1, fn=1, tn=1)
    one_sided = binary_up_metrics(tp=3, fp=0, fn=0, tn=0)

    assert balanced["up_precision_pct"] == 50.0
    assert balanced["up_recall_pct"] == 50.0
    assert balanced["up_specificity_pct"] == 50.0
    assert balanced["balanced_accuracy_pct"] == 50.0
    assert one_sided["balanced_accuracy_pct"] is None


def test_probability_metrics_score_only_valid_forward_probabilities() -> None:
    metrics = probability_metrics(
        [(0.8, 1), (0.8, 0), (None, 1), (1.2, 1)],
    )

    assert metrics["probability_evaluated"] == 2
    assert metrics["brier_score"] == 0.34
    assert metrics["log_loss"] == 0.9163
    assert metrics["calibration_error_pct"] == 30.0
    assert metrics["calibration_bias_pct"] == 30.0
    assert probability_metrics([])["brier_score"] is None
