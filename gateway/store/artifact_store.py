"""Artifact Store for HTTP Gateway (§5.3)."""

from __future__ import annotations

import hashlib
import threading
from typing import Any, Optional


class ArtifactStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._artifacts: dict[str, dict[str, Any]] = {}

    def store(self, content: bytes, metadata: Optional[dict] = None) -> dict[str, Any]:
        with self._lock:
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            artifact_id = digest.split(":")[1][:16]
            entry = {
                "artifact_id": artifact_id,
                "hash": digest,
                "size_bytes": len(content),
                "metadata": metadata or {},
                "content": content,
            }
            self._artifacts[artifact_id] = entry
            self._artifacts[digest] = entry
            return {
                "artifact_id": artifact_id,
                "hash": digest,
                "size_bytes": len(content),
                "metadata": entry["metadata"],
            }

    def retrieve(self, key: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._artifacts.get(key)


_ARTIFACT_STORE: Optional[ArtifactStore] = None


def get_artifact_store() -> ArtifactStore:
    global _ARTIFACT_STORE
    if _ARTIFACT_STORE is None:
        _ARTIFACT_STORE = ArtifactStore()
    return _ARTIFACT_STORE
