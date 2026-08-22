from __future__ import annotations

import app
from analysis_models import AssetProfile, ModuleScore, RiskReward
from score_composition import score_from_optional, score_weight_rows, weighted_total_score


def test_app_reexports_score_composition_interfaces() -> None:
    assert app.score_weight_rows is score_weight_rows
    assert app.weighted_total_score is weighted_total_score
    assert app.score_from_optional is score_from_optional


def test_weight_rows_preserve_configured_order_and_transparent_percentages() -> None:
    profile = AssetProfile(
        "Aktie",
        "EQUITY",
        "",
        {"Technik": 0.3, "Fundamentaldaten": 0.4, "Unbekannt": 0.3},
    )

    rows = score_weight_rows(profile)

    assert [row["Baustein"] for row in rows] == ["Technik", "Fundamentaldaten", "Unbekannt"]
    assert [row["Gewichtung"] for row in rows] == ["30%", "40%", "30%"]
    assert rows[-1]["Bedeutung"] == "Bewertungsbaustein."


def test_default_weighted_total_and_parts_remain_exact() -> None:
    result, parts = weighted_total_score(
        ModuleScore(8.0, "", []),
        ModuleScore(7.0, "", []),
        ModuleScore(6.0, "", []),
        ModuleScore(5.0, "", []),
        RiskReward(None, None, None, 4.0, ""),
    )

    assert result == 6.6
    assert parts == {
        "Technik": 8.0,
        "Fundamentaldaten": 7.0,
        "Makro": 6.0,
        "News": 5.0,
        "CRV": 4.0,
    }


def test_custom_weights_do_not_mutate_input_mapping() -> None:
    weights = {"Technik": 1.0}
    original = dict(weights)

    result, _ = weighted_total_score(
        ModuleScore(8.0, "", []),
        ModuleScore(7.0, "", []),
        ModuleScore(6.0, "", []),
        ModuleScore(5.0, "", []),
        RiskReward(None, None, None, 4.0, ""),
        weights,
    )

    assert result == 8.0
    assert weights == original


def test_optional_score_uses_neutral_empty_value_and_rounded_mean() -> None:
    assert score_from_optional([]) == 5.0
    assert score_from_optional([], neutral_if_empty=4.0) == 4.0
    assert score_from_optional([4.0, 5.0, 8.0]) == 5.7
