from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd


SWING_RESEARCH_DATASET_MANIFEST_VERSION = "swing-research-dataset-manifest-2026.08.18-v1"
REQUIRED_HISTORY_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


class FrozenResearchDatasetError(RuntimeError):
    """The immutable epoch dataset is absent, corrupt or contract-incompatible."""


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def normalized_research_history(frame: object) -> pd.DataFrame:
    if (
        not isinstance(frame, pd.DataFrame)
        or frame.empty
        or not set(REQUIRED_HISTORY_COLUMNS).issubset(frame.columns)
    ):
        return pd.DataFrame()
    result = frame.loc[:, list(REQUIRED_HISTORY_COLUMNS)].copy()
    result.index = pd.to_datetime(result.index, errors="coerce")
    if getattr(result.index, "tz", None) is not None:
        result.index = result.index.tz_convert(None)
    result = result.loc[~result.index.isna()].sort_index()
    result = result.loc[~result.index.duplicated(keep="last")]
    for column in REQUIRED_HISTORY_COLUMNS:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["Open", "High", "Low", "Close"])


def research_history_fingerprint(ticker: str, frame: object) -> str:
    normalized = normalized_research_history(frame)
    if normalized.empty:
        raise FrozenResearchDatasetError(f"{ticker}: leerer oder ungültiger Research-Kursverlauf.")
    # Datetime resolution is a storage representation, not research content.
    # Canonicalize it so a lossless Parquet roundtrip (for example s -> ms)
    # cannot invalidate a frozen history.
    normalized.index = normalized.index.as_unit("ns")
    return _research_history_fingerprint_from_normalized(ticker, normalized)


def _research_history_fingerprint_from_normalized(
    ticker: str,
    normalized: pd.DataFrame,
) -> str:
    digest = hashlib.sha256()
    digest.update(str(ticker).strip().upper().encode("utf-8"))
    digest.update(b"\0")
    digest.update("|".join(REQUIRED_HISTORY_COLUMNS).encode("utf-8"))
    digest.update(b"\0")
    digest.update("|".join(str(normalized[column].dtype) for column in REQUIRED_HISTORY_COLUMNS).encode("utf-8"))
    digest.update(b"\0")
    hashed = pd.util.hash_pandas_object(normalized, index=True, categorize=False)
    digest.update(hashed.to_numpy(dtype="uint64", copy=False).tobytes())
    return digest.hexdigest()


def research_history_compatible_fingerprints(ticker: str, frame: object) -> set[str]:
    """Accept legacy datetime units only when every research value is identical."""
    normalized = normalized_research_history(frame)
    if normalized.empty:
        raise FrozenResearchDatasetError(f"{ticker}: leerer oder ungültiger Research-Kursverlauf.")
    fingerprints = {research_history_fingerprint(ticker, normalized)}
    for unit in ("s", "ms", "us", "ns"):
        compatible = normalized.copy()
        compatible.index = compatible.index.as_unit(unit)
        fingerprints.add(
            _research_history_fingerprint_from_normalized(ticker, compatible)
        )
    return fingerprints


def research_dataset_scope(start: object, end: object | None) -> dict[str, str | None]:
    normalized_start = str(start).strip()
    normalized_end = str(end).strip() if end not in {None, "", "latest"} else None
    if not normalized_start:
        raise ValueError("Ein eingefrorener Research-Datensatz benötigt ein Startdatum.")
    return {
        "start": normalized_start,
        "end": normalized_end,
        "interval": "1d",
        "price_adjustment": "yfinance_auto_adjust_true",
    }


def research_dataset_scope_id(start: object, end: object | None) -> str:
    return _fingerprint(research_dataset_scope(start, end))[:20]


def research_dataset_epoch_directory(dataset_root: Path, dataset_epoch: str) -> Path:
    digest = hashlib.sha256(str(dataset_epoch).encode("utf-8")).hexdigest()[:24]
    return Path(dataset_root) / digest


def research_dataset_manifest_path(dataset_root: Path, dataset_epoch: str) -> Path:
    return research_dataset_epoch_directory(dataset_root, dataset_epoch) / "manifest.json"


def frozen_history_path(
    dataset_root: Path,
    dataset_epoch: str,
    *,
    scope_id: str,
    ticker: str,
) -> Path:
    ticker_digest = hashlib.sha256(str(ticker).strip().upper().encode("utf-8")).hexdigest()[:24]
    return research_dataset_epoch_directory(dataset_root, dataset_epoch) / scope_id / f"{ticker_digest}.parquet"


def research_cache_history_path(
    cache_root: Path,
    ticker: str,
    *,
    start: object,
    end: object | None,
) -> Path:
    contract = research_dataset_scope(start, end)
    cache_scope = (
        f"{contract['start']}|{contract['end'] or 'latest'}|"
        f"{contract['interval']}|{contract['price_adjustment']}"
    )
    digest = hashlib.sha256(
        f"{str(ticker).strip().upper()}|{cache_scope}".encode("utf-8")
    ).hexdigest()[:20]
    return Path(cache_root) / f"{digest}.parquet"


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _restore_frozen_history_from_cache(
    destination: Path,
    *,
    cache_root: Path,
    ticker: str,
    start: object,
    end: object | None,
    expected_history_fingerprint: str,
) -> tuple[pd.DataFrame, dict[str, object]] | None:
    cache_path = research_cache_history_path(
        cache_root,
        ticker,
        start=start,
        end=end,
    )
    try:
        cached = normalized_research_history(pd.read_parquet(cache_path))
    except Exception:
        return None
    if (
        cached.empty
        or expected_history_fingerprint
        not in research_history_compatible_fingerprints(ticker, cached)
    ):
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.repair.",
        suffix=".tmp.parquet",
        dir=destination.parent,
    )
    os.close(descriptor_fd)
    temporary = Path(temporary_name)
    quarantine: Path | None = None
    try:
        cached.to_parquet(temporary, index=True)
        restored = normalized_research_history(pd.read_parquet(temporary))
        if (
            restored.empty
            or expected_history_fingerprint
            not in research_history_compatible_fingerprints(ticker, restored)
        ):
            return None
        if destination.exists():
            quarantine_directory = destination.parent / ".recovery"
            quarantine_directory.mkdir(parents=True, exist_ok=True)
            quarantine = quarantine_directory / (
                f"{destination.name}.{_file_digest(destination)[:16]}.invalid"
            )
            if not quarantine.exists():
                shutil.copy2(destination, quarantine)
        os.replace(temporary, destination)
        return restored, {
            "ticker": str(ticker).strip().upper(),
            "source": "validated_local_cache",
            "provider_access": False,
            "manifest_changed": False,
            "history_fingerprint_preserved": True,
            "quarantine": str(quarantine) if quarantine is not None else None,
        }
    finally:
        if temporary.exists():
            temporary.unlink()


def frozen_history_descriptor(
    dataset_root: Path,
    dataset_epoch: str,
    *,
    scope_id: str,
    ticker: str,
    frame: object,
) -> dict[str, object]:
    normalized = normalized_research_history(frame)
    if normalized.empty:
        raise FrozenResearchDatasetError(f"{ticker}: Research-Kursverlauf kann nicht eingefroren werden.")
    destination = frozen_history_path(
        dataset_root,
        dataset_epoch,
        scope_id=scope_id,
        ticker=ticker,
    )
    relative_path = destination.relative_to(research_dataset_epoch_directory(dataset_root, dataset_epoch))
    return {
        "ticker": str(ticker).strip().upper(),
        "status": "available",
        "file": relative_path.as_posix(),
        "history_fingerprint": research_history_fingerprint(ticker, normalized),
        "rows": len(normalized),
        "first_day": pd.Timestamp(normalized.index[0]).date().isoformat(),
        "last_day": pd.Timestamp(normalized.index[-1]).date().isoformat(),
    }


def store_frozen_history(
    dataset_root: Path,
    dataset_epoch: str,
    *,
    scope_id: str,
    ticker: str,
    frame: object,
) -> dict[str, object]:
    normalized = normalized_research_history(frame)
    descriptor = frozen_history_descriptor(
        dataset_root,
        dataset_epoch,
        scope_id=scope_id,
        ticker=ticker,
        frame=normalized,
    )
    destination = frozen_history_path(
        dataset_root,
        dataset_epoch,
        scope_id=scope_id,
        ticker=ticker,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            existing = normalized_research_history(pd.read_parquet(destination))
        except Exception:
            existing = pd.DataFrame()
        if (
            not existing.empty
            and str(descriptor["history_fingerprint"])
            in research_history_compatible_fingerprints(ticker, existing)
        ):
            return descriptor
    descriptor_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=".tmp.parquet", dir=destination.parent
    )
    os.close(descriptor_fd)
    temporary = Path(temporary_name)
    try:
        normalized.to_parquet(temporary, index=True)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return descriptor


def _manifest_fingerprint_payload(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        "manifest_version": manifest.get("manifest_version"),
        "dataset_epoch": manifest.get("dataset_epoch"),
        "scopes": manifest.get("scopes"),
        "provider_policy": manifest.get("provider_policy"),
    }


def finalize_research_dataset_manifest(
    dataset_root: Path,
    dataset_epoch: str,
    *,
    scopes: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    manifest_path = research_dataset_manifest_path(dataset_root, dataset_epoch)
    if manifest_path.exists():
        return load_research_dataset_manifest(manifest_path)
    normalized_scopes = {
        str(scope_id): {
            "contract": dict(scope["contract"]),
            "assets": {
                str(ticker).strip().upper(): dict(descriptor)
                for ticker, descriptor in sorted(dict(scope.get("assets") or {}).items())
            },
        }
        for scope_id, scope in sorted(scopes.items())
    }
    manifest: dict[str, object] = {
        "manifest_version": SWING_RESEARCH_DATASET_MANIFEST_VERSION,
        "dataset_epoch": str(dataset_epoch),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "finalized",
        "scopes": normalized_scopes,
        "provider_policy": {
            "provider": "Yahoo Finance über yfinance",
            "provider_access_after_finalize": False,
            "cache_miss_after_finalize": "fail_closed",
            "corrupt_file_after_finalize": "fail_closed",
            "adjusted_ohlcv": True,
            "automatic_revision": False,
        },
    }
    fingerprint = _fingerprint(_manifest_fingerprint_payload(manifest))
    manifest["dataset_fingerprint"] = fingerprint
    manifest["dataset_revision"] = fingerprint
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".manifest.", suffix=".tmp", dir=manifest_path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, manifest_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return manifest


def load_research_dataset_manifest(path: Path) -> dict[str, object]:
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise FrozenResearchDatasetError(f"Research-Dataset-Manifest ist nicht lesbar: {manifest_path}") from exc
    if manifest.get("manifest_version") != SWING_RESEARCH_DATASET_MANIFEST_VERSION:
        raise FrozenResearchDatasetError("Nicht unterstützte Research-Dataset-Manifestversion.")
    if manifest.get("status") != "finalized":
        raise FrozenResearchDatasetError("Research-Dataset ist noch nicht finalisiert.")
    if not str(manifest.get("dataset_epoch") or "").strip() or not isinstance(
        manifest.get("scopes"), dict
    ):
        raise FrozenResearchDatasetError("Research-Dataset-Manifest besitzt keinen vollständigen Epoch-Vertrag.")
    expected = _fingerprint(_manifest_fingerprint_payload(manifest))
    if str(manifest.get("dataset_fingerprint") or "") != expected:
        raise FrozenResearchDatasetError("Research-Dataset-Manifest besitzt einen ungültigen Fingerabdruck.")
    if str(manifest.get("dataset_revision") or "") != expected:
        raise FrozenResearchDatasetError("Research-Dataset-Revision stimmt nicht mit dem Fingerabdruck überein.")
    return manifest


def load_frozen_histories(
    dataset_root: Path,
    manifest: Mapping[str, object],
    *,
    tickers: Sequence[str],
    start: object,
    end: object | None,
    repair_cache_path: Path | None = None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    scope_id = research_dataset_scope_id(start, end)
    scope = dict((manifest.get("scopes") or {}).get(scope_id) or {})
    if not scope:
        raise FrozenResearchDatasetError("Research-Dataset enthält das angeforderte historische Zeitfenster nicht.")
    expected_contract = research_dataset_scope(start, end)
    if dict(scope.get("contract") or {}) != expected_contract:
        raise FrozenResearchDatasetError("Research-Dataset-Zeitfenster stimmt nicht mit dem Jobvertrag überein.")
    epoch_directory = research_dataset_epoch_directory(
        dataset_root,
        str(manifest.get("dataset_epoch") or ""),
    )
    descriptors = dict(scope.get("assets") or {})
    histories: dict[str, pd.DataFrame] = {}
    unavailable: list[str] = []
    for raw_ticker in tickers:
        ticker = str(raw_ticker).strip().upper()
        descriptor = dict(descriptors.get(ticker) or {})
        if descriptor.get("status") == "missing":
            unavailable.append(ticker)
            continue
        relative = str(descriptor.get("file") or "")
        if descriptor.get("status") != "available" or not relative:
            raise FrozenResearchDatasetError(f"{ticker}: kein finalisierter Dataset-Eintrag vorhanden.")
        path = (epoch_directory / relative).resolve()
        if epoch_directory.resolve() not in path.parents:
            raise FrozenResearchDatasetError(f"{ticker}: ungültiger Pfad im Dataset-Manifest.")
        expected_history_fingerprint = str(descriptor.get("history_fingerprint") or "")
        read_error: Exception | None = None
        try:
            frame = normalized_research_history(pd.read_parquet(path))
        except Exception as exc:
            read_error = exc
            frame = pd.DataFrame()
        valid = bool(
            not frame.empty
            and expected_history_fingerprint
            in research_history_compatible_fingerprints(ticker, frame)
        )
        if not valid and repair_cache_path is not None:
            repaired = _restore_frozen_history_from_cache(
                path,
                cache_root=repair_cache_path,
                ticker=ticker,
                start=start,
                end=end,
                expected_history_fingerprint=expected_history_fingerprint,
            )
            if repaired is not None:
                frame, repair = repaired
                print(
                    _canonical_json({"frozen_dataset_auto_repair": repair}),
                    flush=True,
                )
                valid = True
        if not valid:
            if read_error is not None:
                raise FrozenResearchDatasetError(
                    f"{ticker}: eingefrorene Kursdatei ist nicht lesbar."
                ) from read_error
            raise FrozenResearchDatasetError(
                f"{ticker}: eingefrorene Kursdatei besitzt abweichende Daten."
            )
        histories[ticker] = frame
    return histories, unavailable
