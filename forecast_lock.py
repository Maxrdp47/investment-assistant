from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class ForecastRunAlreadyActiveError(RuntimeError):
    """Raised when another forecast process owns the exclusive runtime lock."""


def lock_path_for_database(database_path: Path) -> Path:
    path = Path(database_path)
    return path.with_name(f"{path.name}.run.lock")


class ForecastRunLock:
    """Small cross-platform advisory lock released automatically when a process exits."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise ForecastRunAlreadyActiveError(
                "Ein anderer Prognoseprozess ist bereits aktiv. "
                "Der parallele Start wurde zum Schutz vor Doppelabfragen abgelehnt."
            ) from exc
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    def __enter__(self) -> ForecastRunLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
