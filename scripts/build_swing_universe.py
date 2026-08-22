from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FORECAST_UNIVERSE = PROJECT_ROOT / "config" / "forecast_weekly_universe.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "config" / "swing_universe.csv"
DEFAULT_METADATA_OUTPUT = PROJECT_ROOT / "config" / "swing_universe_sources.json"
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP400_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
SP600_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
UNIVERSE_VERSION = "2026.08.11-v1"
OUTPUT_COLUMNS = [
    "version",
    "ticker",
    "name",
    "asset_type",
    "region",
    "category",
    "active",
    "liquidity_class",
    "source_group",
]
FORBIDDEN_TICKERS = {
    "TQQQ",
    "SQQQ",
    "UPRO",
    "SPXU",
    "SPXL",
    "SPXS",
    "SOXL",
    "SOXS",
    "TECL",
    "TECS",
    "FAS",
    "FAZ",
    "LABU",
    "LABD",
    "TNA",
    "TZA",
}
FORBIDDEN_SECURITY_NAME_TOKENS = (
    " warrant",
    " unit",
    " right",
    " preferred",
    " note",
    " bond",
)


class _WikiTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            if self._table_depth == 0:
                self._current_table = []
            self._table_depth += 1
            return
        if self._table_depth != 1:
            return
        if tag == "tr":
            self._current_row = []
        elif tag in {"th", "td"} and self._current_row is not None:
            self._current_cell = []
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append(" ")

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            return
        if self._table_depth != 1:
            return
        if tag in {"th", "td"} and self._current_cell is not None and self._current_row is not None:
            value = " ".join("".join(self._current_cell).split())
            self._current_row.append(value)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None and self._current_table is not None:
            if self._current_row:
                self._current_table.append(self._current_row)
            self._current_row = None


def _read_wikipedia_table(url: str) -> list[dict[str, str]]:
    request = Request(
        url,
        headers={"User-Agent": "InvestmentAssistantUniverseBuilder/2026.08 (local documentation build)"},
    )
    with urlopen(request, timeout=30) as response:
        payload = response.read(8_000_000).decode("utf-8")
    parser = _WikiTableParser()
    parser.feed(payload)
    for table in parser.tables:
        if not table:
            continue
        headers = table[0]
        if not {"Symbol", "Security"}.issubset(set(headers)):
            continue
        rows: list[dict[str, str]] = []
        for values in table[1:]:
            if len(values) < len(headers):
                values = [*values, *([""] * (len(headers) - len(values)))]
            rows.append(dict(zip(headers, values, strict=False)))
        return rows
    raise RuntimeError(f"Konstituententabelle nicht gefunden: {url}")


def _read_nasdaq_symbol_directory(url: str = NASDAQ_LISTED_URL) -> list[dict[str, str]]:
    request = Request(
        url,
        headers={"User-Agent": "InvestmentAssistantUniverseBuilder/2026.08 (local universe build)"},
    )
    with urlopen(request, timeout=30) as response:
        payload = response.read(4_000_000).decode("utf-8")
    rows = list(csv.DictReader(payload.splitlines(), delimiter="|"))
    if not rows or "Market Category" not in rows[0]:
        raise RuntimeError("Die offizielle Nasdaq-Symboldatei besitzt nicht das erwartete Format.")
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Erzeugt das versionierte Swing-Scanner-Universum aus dem breiten Projektuniversum, "
            "drei liquiden US-Indizes und regulären Nasdaq-Global-Select-Aktien."
        )
    )
    parser.add_argument("--forecast-universe", type=Path, default=DEFAULT_FORECAST_UNIVERSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT)
    parser.add_argument("--minimum-assets", type=int, default=2_000)
    parser.add_argument(
        "--include-smallcap",
        action="store_true",
        help="Zusätzlich den S&P SmallCap 600 für ein breiteres Wochenuniversum aufnehmen.",
    )
    parser.add_argument("--universe-version", default=UNIVERSE_VERSION)
    return parser.parse_args()


def _normalize_us_ticker(value: object) -> str:
    return str(value or "").strip().upper().replace(".", "-")


def _atomic_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _base_rows(path: Path, universe_version: str = UNIVERSE_VERSION) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    rows: list[dict] = []
    for item in source:
        ticker = str(item.get("ticker") or "").strip().upper()
        asset_type = str(item.get("asset_type") or "").strip()
        if not ticker or ticker in FORBIDDEN_TICKERS:
            continue
        source_liquidity = str(item.get("liquidity_class") or "").strip().upper()
        liquidity_class = (
            source_liquidity
            if source_liquidity in {"A", "B", "C"}
            else "A" if asset_type in {"ETF", "Krypto"} else "B"
        )
        rows.append(
            {
                "version": universe_version,
                "ticker": ticker,
                "name": str(item.get("name") or ticker).strip(),
                "asset_type": asset_type,
                "region": str(item.get("region") or "International").strip(),
                "category": str(item.get("category") or "Nicht klassifiziert").strip(),
                "active": "true",
                "liquidity_class": liquidity_class,
                "source_group": str(
                    item.get("source_group") or "Kuratiertes Prognoseuniversum"
                ).strip(),
            }
        )
    return rows


def _index_rows(
    url: str,
    *,
    source_group: str,
    liquidity_class: str,
    universe_version: str = UNIVERSE_VERSION,
) -> list[dict]:
    table = _read_wikipedia_table(url)
    rows: list[dict] = []
    for item in table:
        ticker = _normalize_us_ticker(item.get("Symbol"))
        if not ticker or ticker in FORBIDDEN_TICKERS:
            continue
        category = str(item.get("GICS Sector") or "US-Aktienindex").strip()
        if not category or category.lower() == "nan":
            category = "US-Aktienindex"
        rows.append(
            {
                "version": universe_version,
                "ticker": ticker,
                "name": str(item.get("Security") or ticker).strip(),
                "asset_type": "Aktie",
                "region": "USA",
                "category": category,
                "active": "true",
                "liquidity_class": liquidity_class,
                "source_group": source_group,
            }
        )
    return rows


def _nasdaq_global_select_rows(
    source: list[dict[str, str]],
    *,
    universe_version: str = UNIVERSE_VERSION,
) -> list[dict]:
    rows: list[dict] = []
    for item in source:
        ticker = _normalize_us_ticker(item.get("Symbol"))
        security_name = str(item.get("Security Name") or "").strip()
        lowered_name = f" {security_name.lower()}"
        if (
            not ticker
            or ticker in FORBIDDEN_TICKERS
            or str(item.get("Market Category") or "").strip() != "Q"
            or str(item.get("Test Issue") or "").strip() != "N"
            or str(item.get("Financial Status") or "").strip() != "N"
            or str(item.get("ETF") or "").strip() != "N"
            or any(token in lowered_name for token in FORBIDDEN_SECURITY_NAME_TOKENS)
        ):
            continue
        rows.append(
            {
                "version": universe_version,
                "ticker": ticker,
                "name": security_name.split(" - ", 1)[0].strip() or ticker,
                "asset_type": "Aktie",
                "region": "USA",
                "category": "Nasdaq Global Select",
                "active": "true",
                "liquidity_class": "B",
                "source_group": "Nasdaq Global Select Market",
            }
        )
    return rows


def build_universe(
    forecast_universe: Path,
    *,
    include_smallcap: bool = True,
    include_nasdaq_global_select: bool = True,
    universe_version: str = UNIVERSE_VERSION,
) -> tuple[list[dict], dict]:
    sources = [
        (SP500_URL, "S&P 500", "A"),
        (SP400_URL, "S&P MidCap 400", "B"),
    ]
    if include_smallcap:
        sources.append((SP600_URL, "S&P SmallCap 600", "C"))
    merged: dict[str, dict] = {}
    for row in _base_rows(forecast_universe, universe_version):
        merged[row["ticker"]] = row
    counts = {"Kuratiertes Prognoseuniversum": len(merged)}
    for url, source_group, liquidity_class in sources:
        rows = _index_rows(
            url,
            source_group=source_group,
            liquidity_class=liquidity_class,
            universe_version=universe_version,
        )
        counts[source_group] = len(rows)
        for row in rows:
            existing = merged.get(row["ticker"])
            if existing is None:
                merged[row["ticker"]] = row
                continue
            groups = {part.strip() for part in str(existing["source_group"]).split(";") if part.strip()}
            groups.add(source_group)
            existing["source_group"] = "; ".join(sorted(groups))
            if liquidity_class == "A":
                existing["liquidity_class"] = "A"
            if existing["category"] in {"Nicht klassifiziert", "Sonstige"}:
                existing["category"] = row["category"]

    if include_nasdaq_global_select:
        nasdaq_rows = _nasdaq_global_select_rows(
            _read_nasdaq_symbol_directory(),
            universe_version=universe_version,
        )
        counts["Nasdaq Global Select Market"] = len(nasdaq_rows)
        for row in nasdaq_rows:
            existing = merged.get(row["ticker"])
            if existing is None:
                merged[row["ticker"]] = row
                continue
            groups = {part.strip() for part in str(existing["source_group"]).split(";") if part.strip()}
            groups.add("Nasdaq Global Select Market")
            existing["source_group"] = "; ".join(sorted(groups))
            if existing["category"] in {"Nicht klassifiziert", "Sonstige"}:
                existing["category"] = row["category"]

    rows = sorted(
        merged.values(),
        key=lambda item: (
            {"Aktie": 0, "ETF": 1, "Krypto": 2}.get(item["asset_type"], 9),
            item["region"],
            item["ticker"],
        ),
    )
    metadata = {
        "schema_version": 1,
        "universe_version": universe_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {
                "name": "Kuratiertes Prognoseuniversum",
                "location": str(forecast_universe),
                "rows": counts["Kuratiertes Prognoseuniversum"],
            },
            {"name": "S&P 500", "url": SP500_URL, "rows": counts["S&P 500"]},
            {"name": "S&P MidCap 400", "url": SP400_URL, "rows": counts["S&P MidCap 400"]},
            *(
                [{"name": "S&P SmallCap 600", "url": SP600_URL, "rows": counts["S&P SmallCap 600"]}]
                if include_smallcap
                else []
            ),
            *(
                [
                    {
                        "name": "Nasdaq Global Select Market",
                        "url": NASDAQ_LISTED_URL,
                        "rows": counts["Nasdaq Global Select Market"],
                        "selection": (
                            "Market Category Q; normaler Finanzstatus; keine Testtitel, ETFs, "
                            "Warrants, Units, Rights, Preferreds, Notes oder Bonds"
                        ),
                    }
                ]
                if include_nasdaq_global_select
                else []
            ),
        ],
        "configured_assets": len(rows),
        "rules": [
            "Nur Aktien, ungehebelte ETFs und große Kryptowährungen.",
            "Keine bekannten Hebel- oder inversen Produkte.",
            "Ungültige Datenabrufe werden zur Laufzeit protokolliert und nie still aus der CSV gelöscht.",
            "Nasdaq-Global-Select-Titel erfüllen zusätzlich offizielle Listing-Anforderungen; die tatsächliche Handelsliquidität wird bei jedem Scan erneut geprüft.",
        ],
    }
    return rows, metadata


def main() -> int:
    args = parse_args()
    rows, metadata = build_universe(
        args.forecast_universe,
        include_smallcap=True,
        include_nasdaq_global_select=True,
        universe_version=str(args.universe_version),
    )
    if len(rows) < args.minimum_assets:
        raise RuntimeError(f"Nur {len(rows)} Assets erzeugt; mindestens {args.minimum_assets} erforderlich.")
    if not any(row["ticker"] == "NOW" for row in rows):
        raise RuntimeError("ServiceNow (NOW) fehlt im erzeugten Universum.")
    _atomic_csv(args.output, rows)
    _atomic_json(args.metadata_output, metadata)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "metadata": str(args.metadata_output),
                "configured_assets": len(rows),
                "version": str(args.universe_version),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
