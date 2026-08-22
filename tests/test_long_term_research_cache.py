from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

import long_term_research_cache
from long_term_analysis import LongTermEvidence, LongTermSource
from long_term_research_cache import (
    LONG_TERM_CACHE_SCHEMA_VERSION,
    cache_path_for_ticker,
    load_long_term_cache,
    save_long_term_cache,
)


COLLECTED_AT = "2026-08-02T18:00:00+02:00"
EXPIRES_AT = "2026-08-03T18:00:00+02:00"


def source(source_id: str = "annual") -> LongTermSource:
    return LongTermSource(
        source_id=source_id,
        title="Geschäftsbericht",
        url="https://example.com/annual-report",
        publisher="Example AG",
        source_type="annual_report",
        accessed_at=COLLECTED_AT,
        purpose="Geschäftsmodell und Finanzqualität",
        published_at="2026-07-31",
    )


def evidence(source_id: str = "annual") -> LongTermEvidence:
    return LongTermEvidence(
        section="business_model",
        statement="Das Geschäftsmodell ist durch den Bericht belegt.",
        source_ids=(source_id,),
    )


def save_sample(path: Path) -> bool:
    return save_long_term_cache(
        path,
        ticker="NVDA",
        collected_at=COLLECTED_AT,
        expires_at=EXPIRES_AT,
        sources=[source()],
        evidence=[evidence()],
    )


def test_cache_path_stays_inside_requested_directory_for_untrusted_ticker(tmp_path: Path) -> None:
    path = cache_path_for_ticker("../../NVDA / test", tmp_path)

    assert path.parent == tmp_path
    assert path.suffix == ".json"
    assert ".." not in path.name
    assert "/" not in path.name
    assert "\\" not in path.name


def test_fresh_cache_roundtrip_preserves_public_source_provenance(tmp_path: Path) -> None:
    path = tmp_path / "nvda.json"

    assert save_sample(path) is True
    result = load_long_term_cache(
        path,
        now=datetime(2026, 8, 2, 19, 0, tzinfo=timezone.utc),
    )

    assert result.available is True
    assert result.usable is True
    assert result.stale is False
    assert result.cache is not None
    assert result.cache.schema_version == LONG_TERM_CACHE_SCHEMA_VERSION
    assert result.cache.ticker == "NVDA"
    assert result.cache.sources == (source(),)
    assert result.cache.evidence == (evidence(),)


def test_stale_cache_remains_readable_but_is_not_usable(tmp_path: Path) -> None:
    path = tmp_path / "nvda.json"
    assert save_sample(path) is True
    before = path.read_bytes()

    result = load_long_term_cache(
        path,
        now=datetime(2026, 8, 4, 0, 0, tzinfo=timezone.utc),
    )

    assert result.available is True
    assert result.usable is False
    assert result.stale is True
    assert result.cache is not None
    assert "veraltet" in result.status
    assert path.read_bytes() == before


def test_missing_and_corrupt_cache_have_explicit_safe_states(tmp_path: Path) -> None:
    missing = load_long_term_cache(tmp_path / "missing.json")
    assert missing.available is False
    assert missing.warnings == ()

    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{broken", encoding="utf-8")
    corrupt = load_long_term_cache(corrupt_path)
    assert corrupt.available is False
    assert corrupt.usable is False
    assert corrupt.warnings


def test_future_schema_is_rejected_without_changing_file(tmp_path: Path) -> None:
    path = tmp_path / "future.json"
    assert save_sample(path) is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = LONG_TERM_CACHE_SCHEMA_VERSION + 1
    path.write_text(json.dumps(payload), encoding="utf-8")
    before = path.read_bytes()

    result = load_long_term_cache(path)

    assert result.available is False
    assert result.usable is False
    assert "Schemaversion" in result.warnings[0]
    assert path.read_bytes() == before


def test_invalid_source_or_unknown_reference_is_never_written(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    invalid_source = replace(source(), purpose="")

    with pytest.raises(ValueError, match="Ungültige Long-Term-Quelle"):
        save_long_term_cache(
            path,
            ticker="NVDA",
            collected_at=COLLECTED_AT,
            expires_at=EXPIRES_AT,
            sources=[invalid_source],
            evidence=[evidence()],
        )
    assert not path.exists()

    with pytest.raises(ValueError, match="unbekannte Quellen"):
        save_long_term_cache(
            path,
            ticker="NVDA",
            collected_at=COLLECTED_AT,
            expires_at=EXPIRES_AT,
            sources=[source()],
            evidence=[evidence("missing")],
        )
    assert not path.exists()


def test_failed_atomic_replace_preserves_existing_cache_and_removes_temp_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "nvda.json"
    assert save_sample(path) is True
    before = path.read_bytes()

    def fail_replace(source_path: Path, target_path: Path) -> None:
        raise OSError("simulierter Austauschfehler")

    monkeypatch.setattr(long_term_research_cache.os, "replace", fail_replace)

    assert save_long_term_cache(
        path,
        ticker="NVDA",
        collected_at="2026-08-02T19:00:00+02:00",
        expires_at="2026-08-03T19:00:00+02:00",
        sources=[source()],
        evidence=[evidence()],
    ) is False
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_cache_times_must_be_ordered_and_timezone_aware(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mit Zeitzone"):
        save_long_term_cache(
            tmp_path / "naive.json",
            ticker="NVDA",
            collected_at="2026-08-02T18:00:00",
            expires_at=EXPIRES_AT,
            sources=[source()],
            evidence=[evidence()],
        )

    with pytest.raises(ValueError, match="nach dem Sammelzeitpunkt"):
        save_long_term_cache(
            tmp_path / "ordered.json",
            ticker="NVDA",
            collected_at=COLLECTED_AT,
            expires_at=COLLECTED_AT,
            sources=[source()],
            evidence=[evidence()],
        )


def test_cache_rejects_stale_source_even_when_collection_time_is_current(tmp_path: Path) -> None:
    stale_source = replace(source(), published_at="2024-01-01")

    with pytest.raises(ValueError, match="veraltet"):
        save_long_term_cache(
            tmp_path / "stale-source.json",
            ticker="NVDA",
            collected_at=COLLECTED_AT,
            expires_at=EXPIRES_AT,
            sources=[stale_source],
            evidence=[evidence()],
        )

    assert not (tmp_path / "stale-source.json").exists()
