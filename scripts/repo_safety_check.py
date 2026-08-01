from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED_FILES = {
    ".env",
    ".streamlit/secrets.toml",
    "search_history.json",
    "trade_history.json",
    "forward_tests.json",
    "decision_history.json",
    "prediction_history.json",
    "backtest_history.json",
}

ALLOWED_PORTFOLIO_ROOT_KEYS = {"cash", "positions"}
ALLOWED_POSITION_KEYS = {"ticker", "asset_type", "shares", "buy_price"}
FORBIDDEN_PORTFOLIO_KEYS = {
    "name",
    "address",
    "adresse",
    "account",
    "account_number",
    "kontonummer",
    "depotnummer",
    "broker_login",
    "api_key",
    "apikey",
    "secret",
    "password",
    "passwort",
    "token",
}


def git_ls_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()}


def fail(message: str) -> None:
    print(f"Repo-Sicherheitscheck: FEHLER - {message}")
    raise SystemExit(1)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"{path.name} ist kein gültiges JSON: {exc}")


def validate_portfolio_file(path: Path) -> None:
    if not path.exists():
        return

    data = load_json(path)
    if not isinstance(data, dict):
        fail("portfolio.json muss ein JSON-Objekt sein.")

    root_keys = set(data)
    forbidden_root = root_keys & FORBIDDEN_PORTFOLIO_KEYS
    if forbidden_root:
        fail(f"portfolio.json enthält verbotene Felder: {', '.join(sorted(forbidden_root))}")

    extra_root = root_keys - ALLOWED_PORTFOLIO_ROOT_KEYS
    if extra_root:
        fail(f"portfolio.json enthält nicht erlaubte Hauptfelder: {', '.join(sorted(extra_root))}")

    cash = data.get("cash")
    if cash is not None and not isinstance(cash, (int, float)):
        fail("portfolio.json: cash muss eine Zahl sein.")

    positions = data.get("positions", [])
    if not isinstance(positions, list):
        fail("portfolio.json: positions muss eine Liste sein.")

    for index, position in enumerate(positions, start=1):
        if not isinstance(position, dict):
            fail(f"portfolio.json: Position {index} muss ein Objekt sein.")
        keys = set(position)
        forbidden_position = keys & FORBIDDEN_PORTFOLIO_KEYS
        if forbidden_position:
            fail(
                "portfolio.json: "
                f"Position {index} enthält verbotene Felder: {', '.join(sorted(forbidden_position))}"
            )
        extra_position = keys - ALLOWED_POSITION_KEYS
        if extra_position:
            fail(
                "portfolio.json: "
                f"Position {index} enthält nicht erlaubte Felder: {', '.join(sorted(extra_position))}"
            )
        for required in ("ticker", "asset_type", "shares", "buy_price"):
            if required not in position:
                fail(f"portfolio.json: Position {index} fehlt Feld {required}.")
        if not isinstance(position["ticker"], str) or not position["ticker"].strip():
            fail(f"portfolio.json: Position {index} hat keinen gültigen Ticker.")
        if not isinstance(position["asset_type"], str) or not position["asset_type"].strip():
            fail(f"portfolio.json: Position {index} hat keinen gültigen Asset-Typ.")
        if not isinstance(position["shares"], (int, float)):
            fail(f"portfolio.json: Position {index}: shares muss eine Zahl sein.")
        if not isinstance(position["buy_price"], (int, float)):
            fail(f"portfolio.json: Position {index}: buy_price muss eine Zahl sein.")


def main() -> int:
    tracked = git_ls_files()
    forbidden_tracked = sorted(FORBIDDEN_TRACKED_FILES & tracked)
    if forbidden_tracked:
        fail(f"private Laufzeitdateien sind getrackt: {', '.join(forbidden_tracked)}")

    validate_portfolio_file(ROOT / "portfolio.json")
    validate_portfolio_file(ROOT / "portfolio.example.json")

    print("Repo-Sicherheitscheck: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
