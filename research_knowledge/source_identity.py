from __future__ import annotations

"""Deterministic, conservative identity handling for external research sources."""

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


_TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "si",
    "feature",
    "app",
    "src",
    "source",
    "share_app_id",
    "share_link_id",
    "share_item_id",
    "sender_device",
    "sender_web_id",
    "is_copy_url",
    "is_from_webapp",
    "is_from_webapp_button",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )


def _sha256_text(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def normalize_source_title(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[a-z0-9äöüß]+", text))


def _platform_name(value: object, *, hostname: str = "") -> str | None:
    text = str(value or "").strip().casefold()
    aliases = {
        "yt": "youtube",
        "youtube.com": "youtube",
        "youtu.be": "youtube",
        "tiktok.com": "tiktok",
        "www.tiktok.com": "tiktok",
    }
    if text:
        return aliases.get(text, text)
    host = hostname.casefold().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be" or host.endswith("youtube.com"):
        return "youtube"
    if host.endswith("tiktok.com"):
        return "tiktok"
    return None


def _clean_url_input(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "://" not in text and re.match(r"^[a-z0-9.-]+\.[a-z]{2,}/", text, re.I):
        text = "https://" + text
    parsed = urlsplit(text)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return None
    return text


def extract_platform_content_id(url: object, *, platform: object = None) -> tuple[str | None, str | None]:
    clean = _clean_url_input(url)
    if clean is None:
        return _platform_name(platform), None
    parsed = urlsplit(clean)
    host = str(parsed.hostname or "").casefold().removeprefix("www.").removeprefix("m.")
    detected = _platform_name(platform, hostname=host)
    path_parts = [item for item in parsed.path.split("/") if item]
    content_id: str | None = None
    if detected == "youtube":
        if host == "youtu.be" and path_parts:
            content_id = path_parts[0]
        elif path_parts and path_parts[0].casefold() in {"shorts", "embed", "live"} and len(path_parts) > 1:
            content_id = path_parts[1]
        else:
            query = dict(parse_qsl(parsed.query, keep_blank_values=False))
            content_id = query.get("v")
        if content_id and not re.fullmatch(r"[A-Za-z0-9_-]{6,32}", content_id):
            content_id = None
    elif detected == "tiktok":
        match = re.search(r"/(?:video|v)/(\d{6,32})(?:\.html)?(?:/|$)", parsed.path, re.I)
        if match:
            content_id = match.group(1)
    return detected, content_id


def normalize_source_url(value: object, *, platform: object = None) -> str | None:
    clean = _clean_url_input(value)
    if clean is None:
        return None
    parsed = urlsplit(clean)
    host = str(parsed.hostname or "").casefold().rstrip(".")
    host = host.removeprefix("m.")
    if host.startswith("www."):
        host = host[4:]
    detected, content_id = extract_platform_content_id(clean, platform=platform)
    if detected == "youtube" and content_id:
        return f"https://youtube.com/watch?v={quote(content_id, safe='_-')}"
    if detected == "tiktok" and content_id:
        return f"https://tiktok.com/video/{content_id}"
    port = parsed.port
    netloc = host
    if port and not ((parsed.scheme.casefold() == "http" and port == 80) or (parsed.scheme.casefold() == "https" and port == 443)):
        netloc = f"{host}:{port}"
    clean_query = []
    for key, query_value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.casefold()
        if lowered.startswith("utm_") or lowered in _TRACKING_PARAMETERS:
            continue
        clean_query.append((key, query_value))
    clean_query.sort(key=lambda item: (item[0].casefold(), item[1]))
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", netloc, path, urlencode(clean_query, doseq=True), ""))


def sha256_file(path: Path, *, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def _validated_sha256(value: object) -> str | None:
    text = str(value or "").strip().casefold()
    if not text:
        return None
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise ValueError("Datei-SHA-256 muss aus genau 64 Hex-Zeichen bestehen.")
    return text


def inspect_source_identity(
    *,
    title: str,
    platform: str | None = None,
    creator: str | None = None,
    direct_url: str | None = None,
    profile_url: str | None = None,
    published_date: str | None = None,
    local_file: Path | None = None,
    local_filename: str | None = None,
    file_sha256: str | None = None,
    file_size: int | None = None,
) -> dict[str, Any]:
    file_path = None if local_file is None else Path(local_file)
    calculated_sha: str | None = None
    calculated_size: int | None = None
    if file_path is not None:
        if not file_path.is_file():
            raise FileNotFoundError(f"Quelldatei nicht gefunden: {file_path}")
        calculated_sha = sha256_file(file_path)
        calculated_size = file_path.stat().st_size
        if local_filename is None:
            local_filename = file_path.name
    provided_sha = _validated_sha256(file_sha256)
    if provided_sha and calculated_sha and provided_sha != calculated_sha:
        raise ValueError("Angegebener Datei-SHA-256 stimmt nicht mit der Quelldatei überein.")
    sha_value = provided_sha or calculated_sha
    if file_size is not None:
        size_value = int(file_size)
        if size_value < 0:
            raise ValueError("Dateigröße darf nicht negativ sein.")
        if calculated_size is not None and size_value != calculated_size:
            raise ValueError("Angegebene Dateigröße stimmt nicht mit der Quelldatei überein.")
    else:
        size_value = calculated_size
    normalized_url = normalize_source_url(direct_url, platform=platform)
    platform_value, content_id = extract_platform_content_id(direct_url, platform=platform)
    creator_value = str(creator or "").strip() or None
    profile_normalized = normalize_source_url(profile_url, platform=platform_value)
    identity_keys: list[tuple[str, str]] = []
    if platform_value and content_id:
        identity_keys.append(("platform_content_id", f"{platform_value}:{content_id}"))
    if normalized_url:
        identity_keys.append(("normalized_url", normalized_url))
    if sha_value:
        identity_keys.append(("file_sha256", sha_value))
    if platform_value and content_id:
        fingerprint_basis = f"platform_content_id:{platform_value}:{content_id}"
        exact_basis = "platform_content_id"
    elif normalized_url:
        fingerprint_basis = f"normalized_url:{normalized_url}"
        exact_basis = "normalized_url"
    elif sha_value:
        fingerprint_basis = f"file_sha256:{sha_value}"
        exact_basis = "file_sha256"
    else:
        fingerprint_basis = _canonical_json(
            {
                "kind": "conservative_metadata",
                "platform": platform_value,
                "creator": normalize_source_title(creator_value),
                "title": normalize_source_title(title),
                "published_date": str(published_date or "").strip() or None,
                "local_filename": str(local_filename or "").strip() or None,
            }
        )
        exact_basis = None
    source_fingerprint = _sha256_text(fingerprint_basis)
    provenance_payload: dict[str, Any] = {
        "platform": platform_value,
        "creator": creator_value,
        "provenance_title": str(title or "").strip() or None,
        "direct_url": str(direct_url or "").strip() or None,
        "normalized_url": normalized_url,
        "content_id": content_id,
        "profile_url": profile_normalized,
        "published_date": str(published_date or "").strip() or None,
        "local_filename": str(local_filename or "").strip() or None,
        "file_sha256": sha_value,
        "file_size": size_value,
        "source_fingerprint": source_fingerprint,
    }
    provenance_fingerprint_payload = dict(provenance_payload)
    # Raw tracking/share URL variants are retained as provenance text, but do
    # not manufacture a new provenance event when their normalized identity is
    # unchanged.
    provenance_fingerprint_payload.pop("direct_url", None)
    provenance_payload["provenance_fingerprint"] = _sha256_text(
        _canonical_json(provenance_fingerprint_payload)
    )
    provenance_payload["identity_keys"] = identity_keys
    provenance_payload["exact_identity_basis"] = exact_basis
    return provenance_payload


def verify_source_fingerprint(identity: Mapping[str, object]) -> bool:
    expected = str(identity.get("source_fingerprint") or "")
    exact_basis = identity.get("exact_identity_basis")
    platform = str(identity.get("platform") or "")
    content_id = str(identity.get("content_id") or "")
    normalized_url = str(identity.get("normalized_url") or "")
    file_hash = str(identity.get("file_sha256") or "")
    if exact_basis == "platform_content_id":
        basis = f"platform_content_id:{platform}:{content_id}"
    elif exact_basis == "normalized_url":
        basis = f"normalized_url:{normalized_url}"
    elif exact_basis == "file_sha256":
        basis = f"file_sha256:{file_hash}"
    else:
        return bool(expected)
    return bool(expected) and expected == _sha256_text(basis)
