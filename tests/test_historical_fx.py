from __future__ import annotations

import pandas as pd

from historical_fx import historical_fx_evidence


def test_eur_identity_needs_no_provider_call() -> None:
    def forbidden_loader(*_args):
        raise AssertionError("EUR darf keinen Providerabruf benötigen.")

    evidence = historical_fx_evidence(
        "EUR",
        "2026-08-10T14:30:00+00:00",
        history_loader=forbidden_loader,
    )

    assert evidence["rate_to_eur"] == 1.0
    assert evidence["quality"] == "identity"


def test_intraday_rate_never_uses_a_quote_after_the_trade() -> None:
    def loader(ticker, _start, _end, interval):
        if ticker != "USDEUR=X" or interval != "5m":
            return pd.DataFrame()
        return pd.DataFrame(
            {"Close": [0.90, 0.91, 0.99]},
            index=pd.to_datetime(
                ["2026-08-10T14:20:00Z", "2026-08-10T14:25:00Z", "2026-08-10T14:35:00Z"],
                utc=True,
            ),
        )

    evidence = historical_fx_evidence(
        "USD",
        "2026-08-10T14:30:00+00:00",
        history_loader=loader,
    )

    assert evidence["rate_to_eur"] == 0.91
    assert evidence["observed_at"] == "2026-08-10T14:25:00+00:00"
    assert evidence["quality"] == "intraday_at_or_before_event"


def test_daily_fallback_uses_previous_close_not_same_day_close() -> None:
    def loader(ticker, _start, _end, interval):
        if ticker != "USDEUR=X" or interval != "1d":
            return pd.DataFrame()
        return pd.DataFrame(
            {"Close": [0.88, 0.98]},
            index=pd.to_datetime(["2026-08-09", "2026-08-10"], utc=True),
        )

    evidence = historical_fx_evidence(
        "USD",
        "2026-08-10T14:30:00+00:00",
        history_loader=loader,
    )

    assert evidence["rate_to_eur"] == 0.88
    assert evidence["quality"] == "previous_daily_close"
