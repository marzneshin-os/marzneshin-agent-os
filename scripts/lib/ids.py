"""ULID generation and id conventions.

ADR-001 D4 removed the global monotonic `seq`. Ordering now comes from:
  - ULID          lexicographically sortable by time, zero coordination
  - actor_seq     per-actor monotonic counter, detects dropped events
  - causation_id  the real causal chain

A ULID is 128 bits: 48-bit big-endian millisecond timestamp + 80 random bits,
rendered as 26 chars of Crockford base32.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from typing import Any

from . import clock as _clock

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # no I, L, O, U
_LOCK = threading.Lock()
_LAST_MS = 0
_LAST_RAND = 0


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_ulid() -> str:
    """Monotonic ULID.

    Within the same millisecond the random component is incremented rather
    than redrawn, so two events emitted in the same ms still sort in creation
    order. This matters for the virtual clock, where thousands of events can
    share one timestamp.
    """
    global _LAST_MS, _LAST_RAND
    c = _clock.get_clock()
    ms = int(c.now().timestamp() * 1000)
    with _LOCK:
        if ms == _LAST_MS:
            _LAST_RAND += 1
            if _LAST_RAND >= (1 << 80):  # overflow: wait for next ms
                _LAST_RAND = c.rng().getrandbits(80)
                ms += 1
        else:
            _LAST_MS = ms
            _LAST_RAND = c.rng().getrandbits(80)
        rand = _LAST_RAND
    return _encode(ms, 10) + _encode(rand, 16)


def ulid_timestamp_ms(ulid: str) -> int:
    """Extract the embedded millisecond timestamp. Used by compaction."""
    if len(ulid) < 10:
        raise ValueError(f"not a ULID: {ulid!r}")
    value = 0
    for ch in ulid[:10].upper():
        idx = _CROCKFORD.find(ch)
        if idx < 0:
            raise ValueError(f"invalid ULID char {ch!r} in {ulid!r}")
        value = (value << 5) | idx
    return value


def new_task_id(prefix: str = "T") -> str:
    """Human-referenceable task id: T-01JBX7... (prefix + ULID)."""
    return f"{prefix}-{new_ulid()}"


def new_correlation_id() -> str:
    return f"C-{new_ulid()}"


def new_session_id() -> str:
    return f"S-{new_ulid()}"


# --- hashing ---------------------------------------------------------------

def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no incidental whitespace.

    Every hash in this system (inputs_hash, prev_receipt_hash, content_hash)
    is taken over this representation, so the same logical object always
    hashes identically regardless of dict insertion order.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_str(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_str(canonical_json(obj))


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def idempotency_key(parts: list[str]) -> str:
    """A2A idempotency key. Composition per capability is decided by
    policy.idempotency_spec() — this only hashes what it is given (G4)."""
    return sha256_str("|".join(parts))
