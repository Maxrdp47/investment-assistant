from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts import collect_long_term_sources as cli


USER_AGENT = "Investment Assistant tests@example.com"


def test_preflight_without_contact_is_offline_and_configuration_required(tmp_path: Path) -> None:
    result = cli.collection_preflight(
        cli.PROJECT_ROOT / "runtime" / "sec-test-cache",
        environment={},
    )

    assert result["status"] == "configuration_required"
    assert result["network_requested"] is False
    assert result["data_written"] is False
    assert result["contact_configured"] is False
    assert result["contact_value_exposed"] is False


def test_preflight_reports_valid_contact_without_exposing_value() -> None:
    result = cli.collection_preflight(
        cli.PROJECT_ROOT / "runtime" / "sec-test-cache",
        environment={cli.SEC_USER_AGENT_ENV: USER_AGENT},
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "ready"
    assert result["contact_configured"] is True
    assert USER_AGENT not in serialized


def test_preflight_rejects_cache_outside_private_runtime(tmp_path: Path) -> None:
    result = cli.collection_preflight(
        tmp_path,
        environment={cli.SEC_USER_AGENT_ENV: USER_AGENT},
    )

    assert result["status"] == "configuration_required"
    assert result["cache_inside_private_runtime"] is False


def test_live_cli_never_prints_contact_value(monkeypatch, capsys) -> None:
    @dataclass(frozen=True)
    class FakeResult:
        available: bool
        status: str

    monkeypatch.setenv(cli.SEC_USER_AGENT_ENV, USER_AGENT)
    monkeypatch.setattr(
        cli,
        "run_live_collection",
        lambda ticker, user_agent, cache_dir: FakeResult(True, f"Quellen für {ticker} verfügbar."),
    )

    exit_code = cli.main(["NVDA"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert USER_AGENT not in output
    assert json.loads(output)["contact_value_exposed"] is False
