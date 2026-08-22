from __future__ import annotations

import json

import json_history_store as store


def test_missing_invalid_and_legacy_histories_are_loaded_defensively(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    legacy = tmp_path / "legacy.json"
    invalid.write_text("{not-json", encoding="utf-8")
    legacy.write_text(json.dumps({"records": [{"id": 1}, "invalid", {"id": 2}]}), encoding="utf-8")

    assert store.load_json_dict_list(missing) == []
    assert store.load_json_dict_list(invalid) == []
    assert store.load_json_dict_list(legacy) == [{"id": 1}, {"id": 2}]


def test_atomic_save_writes_complete_json_and_leaves_no_temporary_file(tmp_path) -> None:
    path = tmp_path / "history.json"
    records = [{"ticker": "NVDA"}, {"ticker": "BTC-EUR"}]

    assert store.save_json_dict_list(path, records)
    assert store.load_json_dict_list(path) == records
    assert list(tmp_path.glob(".history.json.*.tmp")) == []


def test_failed_atomic_replace_preserves_existing_history(tmp_path, monkeypatch) -> None:
    path = tmp_path / "history.json"
    original = [{"ticker": "NOW"}]
    path.write_text(json.dumps(original), encoding="utf-8")

    def fail_replace(*_args, **_kwargs):
        raise OSError("simulierter Austauschfehler")

    monkeypatch.setattr(store.os, "replace", fail_replace)

    assert not store.save_json_dict_list(path, [{"ticker": "NVDA"}])
    assert store.load_json_dict_list(path) == original
    assert list(tmp_path.glob(".history.json.*.tmp")) == []
