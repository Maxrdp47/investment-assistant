from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from long_term_analysis import (
    ENTRY_TIMING_SECTION,
    LONG_TERM_MODEL_TYPE,
    LONG_TERM_MODEL_VERSION,
    LONG_TERM_SECTION_REQUIREMENTS,
    LongTermEvidence,
    LongTermSource,
    source_freshness_issues,
    source_validation_issues,
)


LONG_TERM_CACHE_SCHEMA_VERSION = 1
DEFAULT_LONG_TERM_CACHE_DIR = Path(__file__).resolve().parent / "runtime" / "long_term_research"


@dataclass(frozen=True)
class LongTermResearchCache:
    schema_version: int
    model_type: str
    model_version: str
    ticker: str
    collected_at: str
    expires_at: str
    sources: tuple[LongTermSource, ...]
    evidence: tuple[LongTermEvidence, ...]


@dataclass(frozen=True)
class LongTermCacheLoadResult:
    available: bool
    usable: bool
    stale: bool
    status: str
    cache: LongTermResearchCache | None
    warnings: tuple[str, ...]


def _parse_aware_datetime(value: object) -> datetime | None:
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def cache_path_for_ticker(
    ticker: str,
    cache_dir: Path = DEFAULT_LONG_TERM_CACHE_DIR,
) -> Path:
    raw = str(ticker or "").strip().upper()
    if not raw:
        raise ValueError("Ticker für Long-Term-Cache fehlt.")
    slug = re.sub(r"[^A-Z0-9._-]+", "_", raw).strip("._-")
    if not slug:
        slug = "ASSET"
    if slug != raw:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
        slug = f"{slug}-{digest}"
    return Path(cache_dir) / f"{slug}.json"


def _validated_cache(
    *,
    ticker: str,
    collected_at: str,
    expires_at: str,
    sources: Iterable[LongTermSource],
    evidence: Iterable[LongTermEvidence],
    schema_version: int = LONG_TERM_CACHE_SCHEMA_VERSION,
    model_type: str = LONG_TERM_MODEL_TYPE,
    model_version: str = LONG_TERM_MODEL_VERSION,
) -> LongTermResearchCache:
    clean_ticker = str(ticker or "").strip().upper()
    if not clean_ticker:
        raise ValueError("Ticker für Long-Term-Cache fehlt.")
    if schema_version != LONG_TERM_CACHE_SCHEMA_VERSION:
        raise ValueError("Nicht unterstützte Long-Term-Cache-Schemaversion.")
    if model_type != LONG_TERM_MODEL_TYPE:
        raise ValueError("Long-Term-Cache enthält eine falsche Modellart.")
    if model_version != LONG_TERM_MODEL_VERSION:
        raise ValueError("Long-Term-Cache gehört zu einer anderen Modellversion.")

    collected = _parse_aware_datetime(collected_at)
    expires = _parse_aware_datetime(expires_at)
    if collected is None or expires is None:
        raise ValueError("Sammel- und Ablaufzeitpunkt müssen ISO-Zeitpunkte mit Zeitzone sein.")
    if expires <= collected:
        raise ValueError("Ablaufzeitpunkt muss nach dem Sammelzeitpunkt liegen.")

    source_items = tuple(sources)
    source_ids = [str(item.source_id or "").strip() for item in source_items]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Quellen-IDs im Long-Term-Cache müssen eindeutig sein.")
    for source in source_items:
        issues = (
            *source_validation_issues(source),
            *source_freshness_issues(source, as_of=collected),
        )
        if issues:
            raise ValueError(
                f"Ungültige Long-Term-Quelle {source.source_id or '<ohne-id>'}: {' '.join(issues)}"
            )

    known_source_ids = set(source_ids)
    allowed_sections = set(LONG_TERM_SECTION_REQUIREMENTS) | {ENTRY_TIMING_SECTION}
    evidence_items = tuple(evidence)
    for item in evidence_items:
        section = str(item.section or "").strip()
        statement = str(item.statement or "").strip()
        if section not in allowed_sections:
            raise ValueError(f"Unbekannter Long-Term-Bereich im Cache: {section or '<leer>'}.")
        if not statement:
            raise ValueError(f"Leere Long-Term-Aussage im Bereich {section}.")
        cited_ids = tuple(str(source_id or "").strip() for source_id in (item.source_ids or ()))
        if not cited_ids:
            raise ValueError(f"Long-Term-Aussage im Bereich {section} besitzt keine Quelle.")
        missing_ids = sorted({source_id for source_id in cited_ids if source_id not in known_source_ids})
        if missing_ids:
            raise ValueError(
                f"Long-Term-Aussage im Bereich {section} verweist auf unbekannte Quellen: "
                f"{', '.join(missing_ids)}."
            )

    return LongTermResearchCache(
        schema_version=schema_version,
        model_type=model_type,
        model_version=model_version,
        ticker=clean_ticker,
        collected_at=collected_at,
        expires_at=expires_at,
        sources=source_items,
        evidence=evidence_items,
    )


def save_long_term_cache(
    path: Path,
    *,
    ticker: str,
    collected_at: str,
    expires_at: str,
    sources: Iterable[LongTermSource],
    evidence: Iterable[LongTermEvidence],
) -> bool:
    cache = _validated_cache(
        ticker=ticker,
        collected_at=collected_at,
        expires_at=expires_at,
        sources=sources,
        evidence=evidence,
    )
    payload = asdict(cache)
    payload["sources"] = [asdict(source) for source in cache.sources]
    payload["evidence"] = [
        {
            "section": item.section,
            "statement": item.statement,
            "source_ids": list(item.source_ids),
        }
        for item in cache.evidence
    ]

    path = Path(path)
    temporary_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        return True
    except OSError:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False


def _cache_from_payload(payload: object) -> LongTermResearchCache:
    if not isinstance(payload, dict):
        raise ValueError("Long-Term-Cache besitzt kein JSON-Objekt als Wurzel.")
    raw_sources = payload.get("sources")
    raw_evidence = payload.get("evidence")
    if not isinstance(raw_sources, list) or not isinstance(raw_evidence, list):
        raise ValueError("Long-Term-Cache enthält keine gültigen Quellen- und Evidenzlisten.")
    try:
        sources = tuple(LongTermSource(**item) for item in raw_sources if isinstance(item, dict))
        evidence = tuple(
            LongTermEvidence(
                section=item["section"],
                statement=item["statement"],
                source_ids=tuple(item["source_ids"]),
            )
            for item in raw_evidence
            if isinstance(item, dict)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Long-Term-Cache enthält unlesbare Quellen- oder Evidenzfelder.") from exc
    if len(sources) != len(raw_sources) or len(evidence) != len(raw_evidence):
        raise ValueError("Long-Term-Cache enthält ungültige Listenzeilen.")
    try:
        schema_version = int(payload.get("schema_version"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Long-Term-Cache-Schemaversion fehlt oder ist ungültig.") from exc
    return _validated_cache(
        ticker=payload.get("ticker", ""),
        collected_at=payload.get("collected_at", ""),
        expires_at=payload.get("expires_at", ""),
        sources=sources,
        evidence=evidence,
        schema_version=schema_version,
        model_type=payload.get("model_type", ""),
        model_version=payload.get("model_version", ""),
    )


def load_long_term_cache(
    path: Path,
    *,
    now: datetime | None = None,
) -> LongTermCacheLoadResult:
    path = Path(path)
    if not path.exists():
        return LongTermCacheLoadResult(
            available=False,
            usable=False,
            stale=False,
            status="Noch keine Long-Term-Quellenablage vorhanden.",
            cache=None,
            warnings=(),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        cache = _cache_from_payload(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return LongTermCacheLoadResult(
            available=False,
            usable=False,
            stale=False,
            status="Long-Term-Quellenablage ist nicht verwendbar.",
            cache=None,
            warnings=(str(exc),),
        )

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("Prüfzeitpunkt für Long-Term-Cache benötigt eine Zeitzone.")
    expires = _parse_aware_datetime(cache.expires_at)
    stale = expires is None or expires <= current_time
    if stale:
        return LongTermCacheLoadResult(
            available=True,
            usable=False,
            stale=True,
            status="Long-Term-Quellenablage ist veraltet und muss vor einer Analyse erneuert werden.",
            cache=cache,
            warnings=("Veraltete Quellen werden nicht still als aktuelle Long-Term-Basis verwendet.",),
        )
    return LongTermCacheLoadResult(
        available=True,
        usable=True,
        stale=False,
        status="Long-Term-Quellenablage ist aktuell und technisch verwendbar.",
        cache=cache,
        warnings=(),
    )
