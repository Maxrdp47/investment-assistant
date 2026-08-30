from __future__ import annotations

from pathlib import Path

import pandas as pd

import scripts.run_fx_pit_collector as runner
from fx_carry_pit import default_fx_pair_contracts


STAMP = "2026-08-29T10:00:00+00:00"


def _context(settings: dict) -> dict:
    return {
        "observed_at": STAMP,
        "schedule_slot": "2026-08-29:pilot",
        "settings": settings,
        "pairs": default_fx_pair_contracts(),
    }


def test_checked_in_settings_are_fail_closed_and_laptop_friendly() -> None:
    settings = runner.load_settings(runner.DEFAULT_SETTINGS_PATH)
    assert settings["mode"] == "FX_PIT_OBSERVER"
    assert settings["local_run_time"] == "21:45"
    assert settings["schedule"]["wake_to_run"] is False
    assert settings["schedule"]["start_when_available"] is True
    assert set(settings["pairs"]) == {"EUR/USD", "USD/JPY", "GBP/USD"}
    assert all(value is False for value in settings["safety"].values())


def test_offline_pilot_never_calls_yahoo_or_cftc(monkeypatch) -> None:
    settings = runner.load_settings(runner.DEFAULT_SETTINGS_PATH)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Offline-Pilot darf keine externe Quelle aufrufen.")

    monkeypatch.setattr(runner.yf, "Ticker", forbidden)
    monkeypatch.setattr(runner, "refresh_official_cot_forward", forbidden)
    yahoo = runner.yahoo_daily_ohlc_provider(_context(settings), offline=True)
    cot = runner.official_cftc_provider(_context(settings), offline=True)
    assert yahoo["status"] == "NOT_SCHEDULED"
    assert cot["status"] == "NOT_SCHEDULED"


def test_yahoo_adapter_stores_daily_bar_but_never_claims_bid_ask(monkeypatch) -> None:
    settings = runner.load_settings(runner.DEFAULT_SETTINGS_PATH)
    frame = pd.DataFrame(
        {"Open": [1.1], "High": [1.2], "Low": [1.0], "Close": [1.15]},
        index=pd.to_datetime(["2026-08-28T21:00:00Z"], utc=True),
    )

    class FakeTicker:
        def history(self, **_kwargs):
            return frame

    monkeypatch.setattr(runner.yf, "Ticker", lambda _ticker: FakeTicker())
    result = runner.yahoo_daily_ohlc_provider(_context(settings))
    assert result["status"] == "OBSERVED"
    assert len(result["observations"]) == 3
    for observation in result["observations"]:
        assert observation["observation_type"] == "FX_PRICE_BAR"
        assert observation["payload"]["bid_ask_available"] is False
        assert "bid" not in observation["payload"]
        assert "ask" not in observation["payload"]


def test_cftc_adapter_uses_only_reports_available_at_cutoff(monkeypatch) -> None:
    settings = runner.load_settings(runner.DEFAULT_SETTINGS_PATH)
    currencies = {
        "EURO FX": "EUR",
        "U.S. DOLLAR INDEX": "USD",
        "JAPANESE YEN": "JPY",
        "BRITISH POUND": "GBP",
    }
    reports = [
        {
            "report_id": f"report-{currency}",
            "report_date": "2026-08-25",
            "published_at": None,
            "available_at": "2026-08-28T20:00:00+00:00",
            "first_seen_at": "2026-08-28T20:00:00+00:00",
            "market_code": f"code-{currency}",
            "market_name": market_name,
            "report_type": "tff_futures_only",
            "open_interest": 100.0,
            "categories": {},
            "classification_guardrails": {"non_reportables_are_retail": False},
            "pit_eligible": True,
        }
        for market_name, currency in currencies.items()
    ]
    reports.append(
        {
            **reports[0],
            "report_id": "future-report",
            "available_at": "2026-08-30T20:00:00+00:00",
            "pit_eligible": False,
        }
    )
    monkeypatch.setattr(runner, "load_all_cot_reports_as_of", lambda *_args: reports)
    monkeypatch.setattr(runner, "refresh_official_cot_forward", lambda **_kwargs: {"status": "ok", "errors": []})
    result = runner.official_cftc_provider(_context(settings), force_refresh=True)
    assert result["status"] == "OBSERVED"
    assert len(result["observations"]) == 4
    assert all(item["source_type"] == "FORWARD_PIT" for item in result["observations"])
    assert all(item["payload"]["shadow_only"] is True for item in result["observations"])
    assert all(row["status"] == "AVAILABLE_PIT" for row in result["coverage"])
