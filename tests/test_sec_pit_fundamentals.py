from __future__ import annotations

import copy

import pytest

from sec_pit_fundamentals import annual_facts_as_of, extract_annual_pit_history


SHA = "a" * 64


def _payload() -> dict:
    return {
        "cik": 12345,
        "entityName": "Example Issuer",
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {"start": "2018-01-01", "end": "2018-12-31", "val": 100, "accn": "0000012345-19-000001", "form": "10-K", "filed": "2019-02-12", "fp": "FY"},
                            {"start": "2019-01-01", "end": "2019-12-31", "val": 120, "accn": "0000012345-20-000001", "form": "10-K", "filed": "2020-02-10", "fp": "FY"},
                            {"start": "2019-01-01", "end": "2019-12-31", "val": 118, "accn": "0000012345-20-000002", "form": "10-K/A", "filed": "2020-03-05", "fp": "FY"},
                            {"start": "2020-01-01", "end": "2020-12-31", "val": 900, "accn": "0000012345-21-000001", "form": "10-K", "filed": "2021-02-10", "fp": "FY"},
                        ]
                    }
                }
            }
        },
    }


def test_filing_date_is_not_same_day_available_and_revisions_are_kept() -> None:
    payload = _payload()
    history = extract_annual_pit_history(payload, source_snapshot_sha256=SHA)
    assert len(history["facts"]) == 4
    assert not annual_facts_as_of(history, "2019-02-12")
    assert annual_facts_as_of(history, "2019-02-13")["revenue"]["value"] == 100
    assert annual_facts_as_of(history, "2020-02-10")["revenue"]["value"] == 100
    assert annual_facts_as_of(history, "2020-02-11")["revenue"]["value"] == 120
    assert annual_facts_as_of(history, "2020-03-05")["revenue"]["value"] == 120
    amended = annual_facts_as_of(history, "2020-03-06")["revenue"]
    assert amended["value"] == 118
    assert amended["accession_number"] == "0000012345-20-000002"
    assert history["historical_ticker_join_performed"] is False
    assert payload == _payload()


def test_future_filing_and_current_snapshot_changes_do_not_rewrite_as_of() -> None:
    history = extract_annual_pit_history(_payload(), source_snapshot_sha256=SHA)
    previous = annual_facts_as_of(history, "2020-03-06")
    changed = copy.deepcopy(_payload())
    changed["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"]["units"]["USD"].append(
        {"start": "2021-01-01", "end": "2021-12-31", "val": 1000, "accn": "0000012345-22-000001", "form": "10-K", "filed": "2022-02-10", "fp": "FY"}
    )
    later = extract_annual_pit_history(changed, source_snapshot_sha256="b" * 64)
    current = annual_facts_as_of(later, "2020-03-06")
    assert current["revenue"]["value"] == previous["revenue"]["value"]
    assert current["revenue"]["first_usable_date"] == previous["revenue"]["first_usable_date"]
    assert history["history_fingerprint"] != later["history_fingerprint"]


def test_invalid_provenance_or_signal_day_fails_closed() -> None:
    with pytest.raises(ValueError, match="snapshot"):
        extract_annual_pit_history(_payload(), source_snapshot_sha256="short")
    with pytest.raises(ValueError, match="Signal date"):
        annual_facts_as_of({"facts": []}, "not a date")
    malformed = _payload()
    malformed["facts"] = []
    with pytest.raises(ValueError, match="SEC facts"):
        extract_annual_pit_history(malformed, source_snapshot_sha256=SHA)
