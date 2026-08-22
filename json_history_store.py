from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def load_json_dict_list(path: Path) -> list[dict]:
    """Load a local JSON history without failing on missing or legacy content."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return []
    if isinstance(data, dict):
        for key in ("items", "records", "history", "entries", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def save_json_dict_list(path: Path, records: list[dict]) -> bool:
    """Atomically replace a JSON history after the complete payload is durable."""
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
            json.dump(records, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        return True
    except (OSError, TypeError, ValueError):
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False
