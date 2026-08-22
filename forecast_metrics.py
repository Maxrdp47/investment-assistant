from __future__ import annotations

import math


WILSON_Z_95 = 1.959963984540054


def percentage(numerator: int | float, denominator: int | float) -> float | None:
    if float(denominator) <= 0:
        return None
    return round(float(numerator) / float(denominator) * 100, 1)


def wilson_interval(
    hits: int,
    total: int,
    *,
    z: float = WILSON_Z_95,
) -> tuple[float | None, float | None]:
    if total <= 0 or hits < 0 or hits > total:
        return None, None
    n = float(total)
    proportion = float(hits) / n
    denominator = 1 + z * z / n
    center = (proportion + z * z / (2 * n)) / denominator
    margin = (
        z
        * math.sqrt((proportion * (1 - proportion) + z * z / (4 * n)) / n)
        / denominator
    )
    return round(max(0.0, center - margin) * 100, 1), round(
        min(1.0, center + margin) * 100,
        1,
    )


def binary_up_metrics(tp: int, fp: int, fn: int, tn: int) -> dict:
    precision = percentage(tp, tp + fp)
    recall = percentage(tp, tp + fn)
    specificity = percentage(tn, tn + fp)
    balanced_accuracy = (
        round((recall + specificity) / 2, 1)
        if recall is not None and specificity is not None
        else None
    )
    return {
        "up_precision_pct": precision,
        "up_recall_pct": recall,
        "up_specificity_pct": specificity,
        "balanced_accuracy_pct": balanced_accuracy,
        "confusion": {"tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)},
    }


def probability_metrics(
    cases: list[tuple[float | int | None, float | int | None]],
    *,
    calibration_bins: int = 10,
) -> dict:
    valid: list[tuple[float, int]] = []
    for probability, outcome in cases:
        try:
            probability_value = float(probability)
            outcome_value = int(outcome)
        except (TypeError, ValueError):
            continue
        if (
            not math.isfinite(probability_value)
            or probability_value < 0
            or probability_value > 1
            or outcome_value not in {0, 1}
        ):
            continue
        valid.append((probability_value, outcome_value))
    if not valid:
        return {
            "probability_evaluated": 0,
            "brier_score": None,
            "log_loss": None,
            "calibration_error_pct": None,
            "calibration_bias_pct": None,
        }

    epsilon = 1e-15
    brier = sum((probability - outcome) ** 2 for probability, outcome in valid) / len(valid)
    log_loss = -sum(
        outcome * math.log(max(probability, epsilon))
        + (1 - outcome) * math.log(max(1 - probability, epsilon))
        for probability, outcome in valid
    ) / len(valid)
    bin_count = max(int(calibration_bins), 1)
    calibration_error = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        bucket = [
            item
            for item in valid
            if (
                (lower <= item[0] <= upper)
                if index == bin_count - 1
                else (lower <= item[0] < upper)
            )
        ]
        if not bucket:
            continue
        mean_probability = sum(item[0] for item in bucket) / len(bucket)
        mean_outcome = sum(item[1] for item in bucket) / len(bucket)
        calibration_error += len(bucket) / len(valid) * abs(mean_probability - mean_outcome)
    bias = sum(probability - outcome for probability, outcome in valid) / len(valid)
    return {
        "probability_evaluated": len(valid),
        "brier_score": round(brier, 4),
        "log_loss": round(log_loss, 4),
        "calibration_error_pct": round(calibration_error * 100, 1),
        "calibration_bias_pct": round(bias * 100, 1),
    }
