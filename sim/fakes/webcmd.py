"""Fake Adapter for WebCMD Self-Learning Browser Memory (§4 / BUILD-SPEC).

Passes the contract test suite (adapters/contract.py) for the simulation world.
"""

from __future__ import annotations

import json
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


class WebCmdFake(Adapter):
    name = "webcmd"

    def __init__(self, world_state=None, *, seed: int = 0, world: World = "sim"):
        self.world = world
        self._w = world_state
        self._circuit = CircuitBreaker(threshold=5, reset_after_s=60.0)
        self._idem = IdempotencyStore()

        self.fail_healthz = False
        self.fail_next_execute = False
        self.fail_as_refused = False

        self._sitemaps: dict[str, Any] = {
            "example.com": {
                "domain": "example.com",
                "routes": {
                    "/docs": {
                        "url": "https://example.com/docs",
                        "title": "Example Documentation",
                        "structural_hash": "sim_hash_1234",
                        "action_count": 3,
                    }
                },
                "shortcuts": {
                    "search": {"selector": "#search", "path": "/docs"}
                },
                "bot_protection": False,
            }
        }
        self._profiles: dict[str, Any] = {}

    def healthz(self) -> Health:
        if self.fail_healthz:
            return Health(ok=False, detail="Injected failure in WebCMD fake", latency_ms=1.0)
        return Health(ok=True, detail="WebCMD browser memory (simulation standby)", latency_ms=4.0)

    def capabilities(self) -> list[str]:
        return [
            "web_browse",
            "web_extract",
            "web_sitemap_get",
            "web_learn_route",
            "web_purge_cache",
            "web_profile_manage",
        ]

    def execute(
        self,
        op: str,
        payload: dict,
        *,
        idem_key: str,
        idem_class: IdemClass,
        dry_run: bool,
        deadline: datetime,
        provenance: list[dict],
    ) -> Result:
        self._circuit.before_call()

        if self.fail_next_execute:
            self.fail_next_execute = False
            self._circuit.on_failure()
            if self.fail_as_refused:
                raise AdapterRefused("Injected refusal in WebCMD fake")
            raise RuntimeError("Injected runtime failure in WebCMD fake")

        if deadline_remaining_s(deadline) <= 0:
            raise TimeoutError("Deadline exceeded before WebCMD execution")

        if op not in self.capabilities():
            raise AdapterRefused(f"Unknown operation: {op}")

        hit = self._idem.lookup(idem_key)
        if hit is not None:
            return hit

        data: dict[str, Any] = {}
        if op == "web_browse":
            url = payload.get("url", "https://example.com")
            data = {
                "url": url,
                "title": "Simulated Page",
                "compressed_text": "### Simulated Page Content\n\n[@1] [button: Search] [@2] [a: Documentation]",
                "actions": [
                    {"action_id": "@1", "tag": "button", "label": "Search", "selector": "#search"},
                    {"action_id": "@2", "tag": "a", "label": "Documentation", "selector": "a[href='/docs']"},
                ],
                "raw_chars": 15000,
                "compressed_chars": 1500,
                "savings_ratio": 0.90,
                "structural_hash": "sim_hash_abc",
                "cached": True,
            }
        elif op == "web_extract":
            data = {
                "extracted": "Simulated extracted content matching selector",
                "selector": payload.get("selector", "#main"),
            }
        elif op == "web_sitemap_get":
            domain = payload.get("domain", "example.com")
            data = self._sitemaps.get(domain, {"domain": domain, "routes": {}, "shortcuts": {}})
        elif op == "web_learn_route":
            url = payload.get("url", "https://example.com")
            data = {"learned": True, "url": url}
        elif op == "web_purge_cache":
            domain = payload.get("domain")
            if not dry_run:
                if domain and domain in self._sitemaps:
                    del self._sitemaps[domain]
                elif not domain:
                    self._sitemaps.clear()
            data = {"purged": True, "domain": domain}
        elif op == "web_profile_manage":
            profile = payload.get("profile", "default")
            action = payload.get("action", "get")
            if action == "save" and not dry_run:
                self._profiles[profile] = payload.get("state", {})
            data = {"profile": profile, "state": self._profiles.get(profile, {})}

        res = Result(
            ok=True,
            op=op,
            data=data,
            dry_run=dry_run,
            attempts=1,
            duration_ms=4.5,
        )

        self._circuit.on_success()
        if idem_class in ("forever", "scoped") and not dry_run:
            self._idem.save(idem_key, res, klass=idem_class)

        return res

    def rollback(self, receipt_ref: str) -> Result:
        return Result(ok=True, op="rollback", data={"receipt_ref": receipt_ref, "rolled_back": True})
