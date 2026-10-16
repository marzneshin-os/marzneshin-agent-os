"""Simulation Fake for GroundedNotebookAdapter.

Must pass the exact same contract test (adapters.contract.run_contract) as the real adapter.
Governed by BUILD-SPEC.md §4 and ADR-026.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

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
from scripts.lib.grounded_notebook import GroundedNotebook


class GroundedNotebookFake(Adapter):
    """In-memory simulation fake for Grounded Notebook Engine."""

    name = "grounded_notebook"

    def __init__(
        self,
        world_state=None,
        *,
        seed: int = 0,
        world: World = "sim",
    ) -> None:
        self.world = world
        self._w = world_state
        self._seed = seed
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False

        self._notebooks: dict[str, GroundedNotebook] = {}
        # Pre-seed default contract notebook
        self._get_or_create("nb-contract")

    def _get_or_create(self, notebook_id: str) -> GroundedNotebook:
        if notebook_id not in self._notebooks:
            nb = GroundedNotebook(notebook_id=notebook_id, title=f"Fake Notebook {notebook_id}")
            nb.ingest_text(
                "Contract source evidence text for grounded knowledge verification.",
                source_name="contract.md",
            )
            self._notebooks[notebook_id] = nb
        return self._notebooks[notebook_id]

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected Grounded Notebook failure", latency_ms=1.5)
        return Health(ok=True, detail="Grounded Notebook (simulated ok)", latency_ms=10.0)

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
            raise AdapterRefused(f"unknown op {op!r} on fake {self.name!r}")

        cached = self._idem.lookup(idem_key)
        if cached is not None:
            return cached

        rem = deadline_remaining_s(deadline)
        if rem <= 0:
            raise AdapterRefused(f"deadline expired ({rem:.2f}s remaining)")

        if self.fail_next_execute:
            self.fail_next_execute = False
            self._circuit.on_failure()
            if self.fail_as_refused:
                raise AdapterRefused("injected execute refusal")
            raise RuntimeError("injected execute failure")

        notebook_id = args.get("notebook_id", "nb-contract")
        nb = self._get_or_create(notebook_id)

        try:
            if op == "create_notebook":
                title = args.get("title", f"Notebook {notebook_id}")
                desc = args.get("description", "")
                if dry_run:
                    data = {"notebook_id": notebook_id, "title": title, "dry_run": True}
                else:
                    new_nb = GroundedNotebook(notebook_id=notebook_id, title=title, description=desc)
                    self._notebooks[notebook_id] = new_nb
                    data = new_nb.to_dict()

            elif op == "ingest_sources":
                content = args.get("content", "default source content")
                source_name = args.get("source_name", "source.md")
                source_path = args.get("source_path", "inline")
                if dry_run:
                    data = {"notebook_id": notebook_id, "dry_run": True}
                else:
                    doc = nb.ingest_text(content=content, source_name=source_name, source_path=source_path)
                    data = doc.to_dict()

            elif op == "grounded_query":
                query_text = args.get("query", "evidence")
                top_k = int(args.get("top_k", 5))
                res = nb.query(query_text=query_text, top_k=top_k)
                data = res.to_dict()

            elif op == "synthesize_sources":
                topic = args.get("topic", "evidence")
                top_k = int(args.get("top_k", 5))
                res = nb.synthesize(topic=topic, top_k=top_k)
                data = res.to_dict()

            elif op == "verify_grounding":
                statement = args.get("statement", "Contract source evidence text.")
                res = nb.verify_grounding(statement=statement)
                data = res.to_dict()

            elif op == "list_notebooks":
                items = [{"notebook_id": nid, "title": n.title} for nid, n in self._notebooks.items()]
                data = {"notebooks": items, "total": len(items)}

            elif op == "get_notebook":
                data = nb.to_dict()

            else:
                raise AdapterRefused(f"unhandled op {op}")

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
