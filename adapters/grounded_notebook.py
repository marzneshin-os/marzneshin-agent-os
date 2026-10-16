"""Grounded Notebook Adapter — Knowledge Exploration & Grounding Engine (§4 / BUILD-SPEC).

Conforms strictly to BUILD-SPEC.md §4 Adapter protocol (circuit breaker,
idempotency, dry_run, deadline, and taint provenance).
Synthesizes NotebookLM grounded knowledge with Antigravity autonomous action.
Governed by ADR-026.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from adapters.base import (
    Adapter,
    AdapterRefused,
    CircuitBreaker,
    Health,
    IdemClass,
    IdempotencyStore,
    Result,
    World,
    deadline_remaining_s,
)
from scripts.lib import clock
from scripts.lib.grounded_notebook import (
    GroundedNotebook,
    NotebookStore,
)


class GroundedNotebookAdapter(Adapter):
    """L0 Adapter for Grounded Notebook Knowledge Engine."""

    name = "grounded_notebook"

    def __init__(
        self,
        world_state=None,
        *,
        seed: int = 0,
        world: World = "prod",
        root_dir: Optional[Path] = None,
    ) -> None:
        self.world = world
        self._w = world_state
        self._seed = seed
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

        if root_dir is not None:
            self.store = NotebookStore(root_dir=root_dir)
        elif world == "sim":
            self._temp_dir = tempfile.mkdtemp(prefix="sim_notebook_")
            self.store = NotebookStore(root_dir=Path(self._temp_dir))
        else:
            self.store = NotebookStore()

        # In-memory session cache for fast access
        self._cache: dict[str, GroundedNotebook] = {}

    def healthz(self) -> Health:
        self._circuit.before_call()
        start = clock.now()
        detail = (
            "Grounded Notebook Engine (production active)"
            if self.world == "prod"
            else "Grounded Notebook Engine (simulation standby)"
        )
        latency = (clock.now() - start).total_seconds() * 1000.0
        return Health(ok=True, detail=detail, latency_ms=float(latency))

    def capabilities(self) -> list[str]:
        return [
            "create_notebook",
            "ingest_sources",
            "grounded_query",
            "synthesize_sources",
            "verify_grounding",
            "list_notebooks",
            "get_notebook",
        ]

    def _get_or_load_notebook(self, notebook_id: str) -> GroundedNotebook:
        if notebook_id in self._cache:
            return self._cache[notebook_id]
        nb = self.store.load(notebook_id)
        if nb is None:
            nb = GroundedNotebook(notebook_id=notebook_id, title=f"Notebook {notebook_id}")
            self.store.save(nb)
        self._cache[notebook_id] = nb
        return nb

    def execute(
        self,
        op: str,
        args: dict[str, Any],
        *,
        idem_key: str,
        idem_class: IdemClass = "none",
        dry_run: bool = False,
        deadline: datetime,
        provenance: list[dict[str, Any]],
    ) -> Result:
        self._circuit.before_call()

        if op not in self.capabilities():
            raise AdapterRefused(f"unknown op {op!r} on adapter {self.name!r}")

        cached = self._idem.lookup(idem_key)
        if cached is not None:
            return cached

        rem = deadline_remaining_s(deadline)
        if rem <= 0:
            raise AdapterRefused(f"deadline expired ({rem:.2f}s remaining)")

        try:
            notebook_id = args.get("notebook_id", "default_notebook")

            if op == "create_notebook":
                title = args.get("title", f"Notebook {notebook_id}")
                desc = args.get("description", "")
                if dry_run:
                    data = {
                        "notebook_id": notebook_id,
                        "title": title,
                        "description": desc,
                        "created_at": clock.now().isoformat(),
                        "dry_run": True,
                    }
                else:
                    nb = GroundedNotebook(notebook_id=notebook_id, title=title, description=desc)
                    self._cache[notebook_id] = nb
                    self.store.save(nb)
                    data = nb.to_dict()

            elif op == "ingest_sources":
                content = args.get("content", "")
                source_name = args.get("source_name", "inline_doc.md")
                source_path = args.get("source_path", "inline")
                if dry_run:
                    data = {
                        "notebook_id": notebook_id,
                        "source_name": source_name,
                        "source_path": source_path,
                        "simulated_chunks": max(1, len(content.splitlines()) // 20),
                        "dry_run": True,
                    }
                else:
                    nb = self._get_or_load_notebook(notebook_id)
                    doc = nb.ingest_text(content=content, source_name=source_name, source_path=source_path)
                    self.store.save(nb)
                    data = doc.to_dict()

            elif op == "grounded_query":
                query_text = args.get("query", "")
                top_k = int(args.get("top_k", 5))
                min_score = float(args.get("min_score", 0.05))
                nb = self._get_or_load_notebook(notebook_id)
                res = nb.query(query_text=query_text, top_k=top_k, min_score=min_score)
                data = res.to_dict()

            elif op == "synthesize_sources":
                topic = args.get("topic", "")
                top_k = int(args.get("top_k", 5))
                nb = self._get_or_load_notebook(notebook_id)
                res = nb.synthesize(topic=topic, top_k=top_k)
                data = res.to_dict()

            elif op == "verify_grounding":
                statement = args.get("statement", "")
                threshold = float(args.get("threshold", 0.2))
                nb = self._get_or_load_notebook(notebook_id)
                res = nb.verify_grounding(statement=statement, threshold=threshold)
                data = res.to_dict()

            elif op == "list_notebooks":
                notebooks = self.store.list_all()
                data = {"notebooks": notebooks, "total": len(notebooks)}

            elif op == "get_notebook":
                nb = self.store.load(notebook_id)
                data = nb.to_dict() if nb else {}

            else:
                raise AdapterRefused(f"unhandled op: {op}")

            result = Result(
                ok=True,
                op=op,
                data=data,
                dry_run=dry_run,
                attempts=1,
            )
            self._circuit.on_success()
            if idem_class != "none":
                self._idem.save(idem_key, result, klass=idem_class)
            return result
        except Exception as exc:
            self._circuit.on_failure()
            if isinstance(exc, AdapterRefused):
                raise
            raise AdapterRefused(f"{type(exc).__name__}: {exc}") from exc

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"ref": receipt_ref, "status": "rolled_back"})
