from __future__ import annotations

import app
from analysis_models import ModuleScore, PortfolioResult, ScoreResult


def test_app_reexports_shared_analysis_models_for_compatibility() -> None:
    assert app.ScoreResult is ScoreResult
    assert app.ModuleScore is ModuleScore
    assert app.PortfolioResult is PortfolioResult


def test_model_defaults_remain_compatible() -> None:
    score = ScoreResult(7.0, "Beobachten", ["Testgrund"])
    portfolio = PortfolioResult(False, False, None, "Nicht aktiv", [])

    assert score.breakdown is None
    assert portfolio.asset_weight is None
    assert portfolio.adjusted_score is None
