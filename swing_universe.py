from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path


SWING_UNIVERSE_VERSION = "2026.08.02-v1"
SWING_ASSET_ID_VERSION = "swing-asset-id-2026.08.09-v1"
DEFAULT_SWING_UNIVERSE_PATH = Path(__file__).resolve().parent / "config" / "swing_universe.csv"
REQUIRED_COLUMNS = {
    "version",
    "ticker",
    "name",
    "asset_type",
    "region",
    "category",
    "active",
    "liquidity_class",
    "source_group",
}
ALLOWED_ASSET_TYPES = {"Aktie", "ETF", "Krypto"}
ALLOWED_LIQUIDITY_CLASSES = {"A", "B", "C"}
_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-=^]{0,24}$")
_LEVERAGED_TEXT = re.compile(
    r"(?:\b(?:2x|3x|ultra|ultrapro|leveraged|inverse)\b|daily\s+(?:short|bear)|-2x|-3x)",
    re.IGNORECASE,
)
_FORBIDDEN_TICKERS = {
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


@dataclass(frozen=True)
class SwingUniverseAsset:
    version: str
    ticker: str
    name: str
    asset_type: str
    region: str
    category: str
    active: bool
    liquidity_class: str
    source_group: str

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload.update(
            {
                "asset_id": stable_swing_asset_id(self.ticker, self.asset_type, self.region),
                "identity_version": SWING_ASSET_ID_VERSION,
                "exchange": None,
                "isin": None,
            }
        )
        return payload


@dataclass(frozen=True)
class SwingUniverseReport:
    assets: tuple[SwingUniverseAsset, ...]
    errors: tuple[str, ...]
    total_rows: int
    active_count: int
    inactive_count: int
    duplicate_count: int
    forbidden_count: int

    @property
    def valid(self) -> bool:
        return not self.errors


def stable_swing_asset_id(ticker: str, asset_type: str, region: str) -> str:
    identity = "|".join(
        [
            SWING_ASSET_ID_VERSION,
            str(ticker or "").strip().upper(),
            str(asset_type or "").strip(),
            str(region or "").strip(),
        ]
    )
    return f"swing-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"


def _parse_active(value: object) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "1", "yes", "ja", "aktiv"}:
        return True
    if normalized in {"false", "0", "no", "nein", "inaktiv"}:
        return False
    return None


def is_forbidden_leveraged_asset(*, ticker: str, name: str, asset_type: str, category: str) -> bool:
    normalized_ticker = str(ticker or "").strip().upper()
    if normalized_ticker in _FORBIDDEN_TICKERS:
        return True
    if str(asset_type or "").strip() != "ETF":
        return False
    return bool(_LEVERAGED_TEXT.search(f"{name} {category}"))


def load_swing_universe(
    path: Path = DEFAULT_SWING_UNIVERSE_PATH,
    *,
    minimum_active_assets: int = 1_000,
) -> SwingUniverseReport:
    path = Path(path)
    if not path.exists():
        return SwingUniverseReport((), (f"Scanner-Universum fehlt: {path}",), 0, 0, 0, 0, 0)

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or [])
            missing_columns = sorted(REQUIRED_COLUMNS - fieldnames)
            if missing_columns:
                return SwingUniverseReport(
                    (),
                    (f"Scanner-Universum ohne Pflichtspalten: {', '.join(missing_columns)}",),
                    0,
                    0,
                    0,
                    0,
                    0,
                )
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError) as exc:
        return SwingUniverseReport((), (f"Scanner-Universum ist nicht lesbar: {exc}",), 0, 0, 0, 0, 0)

    assets: list[SwingUniverseAsset] = []
    errors: list[str] = []
    seen: set[str] = set()
    duplicate_count = 0
    forbidden_count = 0

    for row_number, row in enumerate(rows, start=2):
        ticker = str(row.get("ticker") or "").strip().upper()
        name = str(row.get("name") or "").strip()
        asset_type = str(row.get("asset_type") or "").strip()
        region = str(row.get("region") or "").strip()
        category = str(row.get("category") or "").strip()
        version = str(row.get("version") or "").strip()
        liquidity_class = str(row.get("liquidity_class") or "").strip().upper()
        source_group = str(row.get("source_group") or "").strip()
        active = _parse_active(row.get("active"))

        row_errors: list[str] = []
        if not _TICKER_PATTERN.fullmatch(ticker):
            row_errors.append("Tickerformat ungültig")
        if ticker in seen:
            duplicate_count += 1
            row_errors.append("Ticker doppelt")
        if not name:
            row_errors.append("Name fehlt")
        if asset_type not in ALLOWED_ASSET_TYPES:
            row_errors.append("Asset-Typ nicht freigegeben")
        if not region:
            row_errors.append("Region fehlt")
        if not category:
            row_errors.append("Branche/Kategorie fehlt")
        if not version:
            row_errors.append("Version fehlt")
        if active is None:
            row_errors.append("Aktiv/Inaktiv ungültig")
        if liquidity_class not in ALLOWED_LIQUIDITY_CLASSES:
            row_errors.append("Liquiditätsklasse ungültig")
        if not source_group:
            row_errors.append("Quellengruppe fehlt")
        if is_forbidden_leveraged_asset(
            ticker=ticker,
            name=name,
            asset_type=asset_type,
            category=category,
        ):
            forbidden_count += 1
            row_errors.append("Hebel-/Inverse-Produkt ist ausgeschlossen")

        if row_errors:
            errors.append(f"Zeile {row_number} ({ticker or 'ohne Ticker'}): {', '.join(row_errors)}.")
            continue

        seen.add(ticker)
        assets.append(
            SwingUniverseAsset(
                version=version,
                ticker=ticker,
                name=name,
                asset_type=asset_type,
                region=region,
                category=category,
                active=bool(active),
                liquidity_class=liquidity_class,
                source_group=source_group,
            )
        )

    active_count = sum(asset.active for asset in assets)
    inactive_count = len(assets) - active_count
    if active_count < minimum_active_assets:
        errors.append(
            f"Scanner-Universum enthält nur {active_count} aktive gültige Assets; erforderlich sind mindestens {minimum_active_assets}."
        )
    if not any(asset.ticker == "NOW" and asset.active for asset in assets):
        errors.append("ServiceNow (NOW) fehlt im aktiven Scanner-Universum.")

    return SwingUniverseReport(
        assets=tuple(assets),
        errors=tuple(errors),
        total_rows=len(rows),
        active_count=active_count,
        inactive_count=inactive_count,
        duplicate_count=duplicate_count,
        forbidden_count=forbidden_count,
    )


def active_swing_assets(report: SwingUniverseReport) -> list[SwingUniverseAsset]:
    return [asset for asset in report.assets if asset.active]
