"""Atomic file primitives.

Everything in the state plane is written through here. Two guarantees:

1. **Atomic replace** — write to a temp file in the same directory, fsync,
   then os.replace(). A reader never sees a half-written STATE.json, even if
   the process is killed mid-write (which the chaos scenarios do on purpose).

2. **Append durability** — NDJSON appends open with O_APPEND so concurrent
   appends from separate processes cannot interleave inside a single line.

Combined with one-writer-per-file partitioning (ADR-001 D4), this removes the
need for the CAS-on-git scheme that G6 rejected.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .ids import canonical_json


def write_text_atomic(path: Path | str, text: str, *, fsync: bool = True) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            if fsync:
                os.fsync(fh.fileno())
        # Atomic rename
        for _ in range(10):
            try:
                os.replace(tmp, p)
                break
            except PermissionError:
                if os.name != "nt": raise
                __import__("time").sleep(0.01)
        else:
            os.replace(tmp, p)
    except BaseException:
        # Never leave a temp file behind; the reaper would count it as state.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if fsync:
        _fsync_dir(p.parent)
    return p


def write_json_atomic(path: Path | str, obj: Any, *, pretty: bool = True, fsync: bool = True) -> Path:
    """Pretty for human-reviewed files (STATE.json, receipts) so git diffs are
    line-oriented and reviewable; canonical for machine-only files."""
    text = (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            if pretty else canonical_json(obj) + "\n")
    return write_text_atomic(path, text, fsync=fsync)


def append_ndjson(path: Path | str, obj: Any, *, fsync: bool = True) -> Path:
    """Append one canonical JSON line. O_APPEND makes the write indivisible
    for line-sized payloads."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json(obj) + "\n"
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        if fsync:
            os.fsync(fd)
    finally:
        os.close(fd)
    return p


def read_json(path: Path | str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        # A corrupt state file is a fail-closed condition, not a default.
        # Callers that can tolerate absence pass a default; callers that
        # cannot must check for CorruptState.
        raise CorruptState(f"unreadable JSON: {p}")


def read_ndjson(path: Path | str) -> list[dict]:
    """Read an NDJSON file, skipping blank lines.

    A truncated final line (possible if the process died mid-append despite
    O_APPEND, e.g. disk full) is reported rather than silently dropped.
    """
    p = Path(path)
    if not p.exists():
        return []
    out: list[dict] = []
    with open(p, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CorruptState(f"{p}:{lineno} malformed NDJSON line: {exc}") from exc
    return out


def read_text(path: Path | str, default: str = "") -> str:
    p = Path(path)
    if not p.exists():
        return default
    return p.read_text(encoding="utf-8")


def _fsync_dir(directory: Path) -> None:
    """fsync the directory so the rename itself is durable."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass  # not supported on every filesystem; the replace is still atomic
    finally:
        os.close(fd)


class CorruptState(RuntimeError):
    """Raised when a state file exists but cannot be parsed.

    Callers must treat this as fail-closed (ADR-001 D5): unreadable state is
    'I don't know', which means halt, not proceed.
    """
