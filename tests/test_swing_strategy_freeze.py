import json
import sqlite3

import pytest

from swing_strategy_freeze import (
    REQUIRED_DOMAINS,
    build_strategy_freeze_artifact,
    register_strategy_freeze,
    strategy_freeze_store_audit,
)


def components() -> dict:
    return {name: {"version": f"test-{name}-v1"} for name in REQUIRED_DOMAINS}


def test_freeze_fingerprint_is_reproducible_and_code_change_creates_new_version(tmp_path) -> None:
    code = tmp_path / "strategy.py"
    config = tmp_path / "settings.json"
    code.write_text("RULE = 1\n", encoding="utf-8")
    config.write_text(json.dumps({"risk": 0.5}), encoding="utf-8")
    first = build_strategy_freeze_artifact(
        strategy_name="baseline",
        strategy_family="long-v1",
        strategy_role="existing_baseline",
        components=components(),
        code_paths=[code],
        config_paths=[config],
        created_at="2026-08-18T10:00:00+00:00",
    )
    repeated = build_strategy_freeze_artifact(
        strategy_name="baseline",
        strategy_family="long-v1",
        strategy_role="existing_baseline",
        components=components(),
        code_paths=[code],
        config_paths=[config],
        created_at="2026-08-18T11:00:00+00:00",
    )
    assert first["strategy_version"] == repeated["strategy_version"]
    database = tmp_path / "freezes.sqlite3"
    assert register_strategy_freeze(first, database)["inserted"] is True
    assert register_strategy_freeze(repeated, database)["existing"] is True

    code.write_text("RULE = 2\n", encoding="utf-8")
    changed = build_strategy_freeze_artifact(
        strategy_name="baseline",
        strategy_family="long-v1",
        strategy_role="existing_baseline",
        components=components(),
        code_paths=[code],
        config_paths=[config],
    )
    assert changed["strategy_version"] != first["strategy_version"]
    assert register_strategy_freeze(changed, database)["inserted"] is True
    assert strategy_freeze_store_audit(database)["freezes"] == 2


def test_freeze_store_is_append_only_and_never_performance_released(tmp_path) -> None:
    code = tmp_path / "strategy.py"
    config = tmp_path / "settings.json"
    code.write_text("RULE = 1\n", encoding="utf-8")
    config.write_text("{}", encoding="utf-8")
    artifact = build_strategy_freeze_artifact(
        strategy_name="rsi-challenger",
        strategy_family="long-v1-rsi",
        strategy_role="research_challenger",
        components=components(),
        code_paths=[code],
        config_paths=[config],
    )
    database = tmp_path / "freezes.sqlite3"
    register_strategy_freeze(artifact, database)
    assert artifact["release"]["approved_from_performance"] is False
    assert artifact["release"]["automatic_production_activation"] is False
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(
                "UPDATE strategy_freezes SET strategy_name='changed' WHERE strategy_version=?",
                (artifact["strategy_version"],),
            )
