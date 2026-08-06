"""sim/fakes — fake adapters for the simulation harness (§16).

`build_fakes(world)` returns all nine. Each passes adapters/contract.py's
suite; each is killable/flaky-injectable by sim/chaos.py.
"""

from __future__ import annotations

from ._base import FakeBase


class GithubFake(FakeBase):
    name = "github"
    OPS = ["commit_atomic", "read_state", "append_event", "create_pr",
           "dispatch_workflow", "read_repo_var"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        self._files: dict[str, str] = {}
        self._vars = {"KILL_SWITCH": ""}
        self._prs: list[dict] = []
        self._commits = 0

    def _apply(self, op, payload, *, dry_run, provenance):
        if op == "commit_atomic":
            if not dry_run:
                self._files.update(payload.get("files", {}))
                self._commits += 1
            return {"commit": f"sim-{self._commits + (0 if not dry_run else 1):07d}",
                    "files": len(payload.get("files", {}))}
        if op == "read_state":
            return {"key": payload.get("key"), "found": payload.get("key") in self._files}
        if op == "append_event":
            return {"appended": True, "type": payload.get("type")}
        if op == "create_pr":
            pr = {"number": len(self._prs) + 1, "title": payload.get("title")}
            if not dry_run:
                self._prs.append(pr)
            return pr
        if op == "dispatch_workflow":
            return {"dispatched": payload.get("workflow"), "queued": True}
        if op == "read_repo_var":
            return {"name": payload.get("name"),
                    "value": self._vars.get(payload.get("name", ""), "")}
        raise AssertionError(op)


class MoxtFake(FakeBase):
    name = "moxt"
    OPS = ["upsert_task", "assign_agent", "set_status", "set_field",
           "read_approval", "read_killswitch_task"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        self._tasks: dict[str, dict] = {}
        self._ks_status = "Clear"

    def _apply(self, op, payload, *, dry_run, provenance):
        if op == "upsert_task":
            tid = payload.get("task") or f"T-sim-{len(self._tasks) + 1}"
            if not dry_run:
                self._tasks.setdefault(tid, {"title": payload.get("title"),
                                             "status": "Backlog", "fields": {}})
            return {"task": tid}
        if op == "assign_agent":
            return {"task": payload.get("task"), "agent": payload.get("agent"),
                    "dispatched": True}
        if op == "set_status":
            if not dry_run and payload.get("task") in self._tasks:
                self._tasks[payload["task"]]["status"] = payload.get("status")
            return {"task": payload.get("task"), "status": payload.get("status")}
        if op == "set_field":
            if not dry_run and payload.get("task") in self._tasks:
                self._tasks[payload["task"]]["fields"][payload.get("field")] = payload.get("value")
            return {"task": payload.get("task"), "field": payload.get("field")}
        if op == "read_approval":
            task = self._tasks.get(payload.get("task", ""), {})
            return {"approval": task.get("fields", {}).get("Approval", "pending")}
        if op == "read_killswitch_task":
            return {"status": self._ks_status}
        raise AssertionError(op)


class ClickupFake(MoxtFake):
    name = "clickup"
    OPS = ["upsert_task", "comment", "set_status", "set_custom_field", "read_approval"]

    def _apply(self, op, payload, *, dry_run, provenance):
        if op == "comment":
            return {"task": payload.get("task"), "commented": True}
        if op == "set_custom_field":
            return self._apply_fields(payload, dry_run)
        return super()._apply(op, payload, dry_run=dry_run, provenance=provenance)

    def _apply_fields(self, payload, dry_run):
        if not dry_run and payload.get("task") in self._tasks:
            self._tasks[payload["task"]]["fields"][payload.get("field")] = payload.get("value")
        return {"task": payload.get("task"), "field": payload.get("field")}


class MarzneshinFake(FakeBase):
    name = "marzneshin"
    OPS = ["list_nodes", "publish_config", "probe", "rollback_profile", "user_provision"]

    def _apply(self, op, payload, *, dry_run, provenance):
        w = self._w
        if op == "list_nodes":
            return {"nodes": [{"id": n.id, "up": n.up, "load": round(n.load, 3),
                               "in_rotation": n.in_rotation}
                              for n in w.nodes]}
        if op == "publish_config":
            profile = payload.get("profile", "unknown")
            if not dry_run:
                w.publish_config(profile, canary_pct=payload.get("canary_pct", 1),
                                 exclude_nodes=payload.get("exclude_nodes"),
                                 include_all=payload.get("include_all", False))
            return {"published": profile, "canary_pct": payload.get("canary_pct", 1)}
        if op == "probe":
            # A probe samples the PHYSICAL truth: real connection attempts.
            samples = 0
            ok = 0
            for node in w.nodes:
                for _ in range(20):
                    samples += 1
                    ok += 1 if self._w.rng.random() < node.success_prob(self._w.rng) else 0
            return {"samples": samples, "ok": ok, "csr": round(ok / max(1, samples), 4),
                    "fleet": payload.get("targets", ["asn:AS1", "asn:AS2", "asn:AS3"])}
        if op == "rollback_profile":
            profile = payload.get("profile", "unknown")
            if not dry_run:
                w.publish_config("reality-v6", canary_pct=100, include_all=True)
            return {"rolled_back": profile, "active": "reality-v6"}
        if op == "user_provision":
            return {"user_id": payload.get("user_id"), "provisioned": True}
        raise AssertionError(op)


class PaymentsFake(FakeBase):
    name = "payments"
    OPS = ["create_checkout", "verify_webhook", "reconcile", "refund"]

    def _apply(self, op, payload, *, dry_run, provenance):
        w = self._w
        if not w.payments_provider_up:
            from adapters.base import AdapterError
            raise AdapterError("payments provider is down (chaos)")
        if op == "create_checkout":
            cid = f"chk-sim-{len(w.checkouts) + 1}"
            if not dry_run:
                w.checkouts[cid] = {"amount_usd": payload.get("amount_usd"),
                                    "status": "created"}
            return {"checkout_id": cid}
        if op == "verify_webhook":
            return {"valid": payload.get("signature") not in (None, "")}
        if op == "reconcile":
            return {"day": payload.get("day"), "revenue_usd": w.revenue_usd,
                    "refunds_usd": w.refunds_usd}
        if op == "refund":
            if not dry_run:
                w.refunds_usd += float(payload.get("amount_usd", 0))
            return {"refunded": payload.get("payment_id")}
        raise AssertionError(op)


class AnalyticsFake(FakeBase):
    name = "analytics"
    OPS = ["ingest_event", "query_metric", "cohort", "experiment_readout", "sample_size"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        self._events: list[dict] = []

    def _apply(self, op, payload, *, dry_run, provenance):
        w = self._w
        if op == "ingest_event":
            if not dry_run:
                self._events.append(payload)
            return {"ingested": payload.get("name")}
        if op == "query_metric":
            metric = payload.get("metric", "csr")
            value = {"csr": w.csr(), "revenue": w.revenue_usd,
                     "trials": w.trials_total, "paid": w.paid_total}.get(metric, 0.0)
            return {"metric": metric, "value": round(float(value), 4)}
        if op == "cohort":
            return {"name": payload.get("name"), "size": w.paid_total}
        if op == "experiment_readout":
            return {"experiment": payload.get("experiment"), "n": len(self._events),
                    "conclusive": len(self._events) > 100}
        if op == "sample_size":
            import math
            mde = float(payload.get("mde", 0.02))
            p, alpha, power = 0.5, float(payload.get("alpha", 0.05)), float(payload.get("power", 0.8))
            z_a, z_b = 1.96, 0.84 if power >= 0.8 else 0.67
            n = math.ceil(2 * p * (1 - p) * ((z_a + z_b) ** 2) / (mde ** 2))
            return {"n_min": n, "mde": mde, "alpha": alpha, "power": power}
        raise AssertionError(op)


class MessagingFake(FakeBase):
    name = "messaging"
    OPS = ["send_campaign", "suppression_add", "quiet_hours_check", "out_of_band_alert"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        self.sent: list[dict] = []
        self.oob_alerts: list[dict] = []

    def _apply(self, op, payload, *, dry_run, provenance):
        w = self._w
        if op == "send_campaign":
            audience = [u for u in payload.get("audience", []) if u not in w.suppressed]
            if not dry_run:
                self.sent.append({"campaign": payload.get("campaign"), "n": len(audience)})
            return {"campaign": payload.get("campaign"), "sent": len(audience)}
        if op == "suppression_add":
            if not dry_run:
                w.suppressed.add(payload.get("user_id", ""))
            return {"suppressed": payload.get("user_id")}
        if op == "quiet_hours_check":
            return {"quiet": False, "zone": payload.get("zone")}
        if op == "out_of_band_alert":
            # The §11.2 hard requirement: if GitHub and Moxt are both gone,
            # this is how the Owner still hears about it.
            if not dry_run:
                self.oob_alerts.append({"severity": payload.get("severity"),
                                        "text": payload.get("text"),
                                        "tick": w.tick})
            return {"alerted": True, "channel": "sim-oob"}
        raise AssertionError(op)


class ObservabilityFake(FakeBase):
    name = "observability"
    OPS = ["push_metric", "query_slo", "fire_alert", "error_budget"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        self.alerts: list[dict] = []
        self.metrics: list[dict] = []

    def _apply(self, op, payload, *, dry_run, provenance):
        w = self._w
        if op == "push_metric":
            if not dry_run:
                self.metrics.append({"name": payload.get("name"),
                                     "value": payload.get("value"), "tick": w.tick})
            return {"pushed": payload.get("name")}
        if op == "query_slo":
            csr = w.csr()
            return {"slo": payload.get("slo"), "value": round(csr, 4),
                    "target": 0.98, "ok": csr >= 0.98}
        if op == "fire_alert":
            if not dry_run:
                self.alerts.append({"name": payload.get("name"),
                                    "severity": payload.get("severity"), "tick": w.tick})
            return {"alert": payload.get("name")}
        if op == "error_budget":
            csr = w.csr()
            consumed = max(0.0, (0.98 - csr) / 0.02) if csr < 0.98 else 0.0
            return {"slo": payload.get("slo"), "consumed_fraction": round(min(1.0, consumed), 3),
                    "available": consumed < 1.0}
        raise AssertionError(op)


class VaultFake(FakeBase):
    name = "vault"
    OPS = ["get_secret", "rotate", "audit"]

    def __init__(self, world_state, *, seed: int = 0) -> None:
        super().__init__(world_state, seed=seed)
        # Sandbox fixture: the contract suite's well-known secret (see
        # adapters/contract.py _payload_for). A real vault sandbox pre-seeds
        # the same name; everything else is correctly refused.
        self._secrets: dict[str, str] = {"contract/probe": "sim-probe-secret"}
        self.audit_log: list[dict] = []

    def _apply(self, op, payload, *, dry_run, provenance):
        name = payload.get("name", "")
        if op == "get_secret":
            self.audit_log.append({"op": "get", "name": name, "tick": self._w.tick})
            if name not in self._secrets:
                from adapters.base import AdapterRefused
                raise AdapterRefused(f"secret {name!r} not found")
            return {"name": name, "value": "<redacted:short-lived>"}
        if op == "rotate":
            if not dry_run:
                self._secrets[name] = "rotated"
            self.audit_log.append({"op": "rotate", "name": name, "tick": self._w.tick})
            return {"rotated": name}
        if op == "audit":
            return {"entries": len(self.audit_log)}
        raise AssertionError(op)


def build_fakes(world_state, *, seed: int = 0) -> dict[str, FakeBase]:
    """All nine fakes wired to one World (§16)."""
    return {
        "github": GithubFake(world_state, seed=seed),
        "moxt": MoxtFake(world_state, seed=seed),
        "clickup": ClickupFake(world_state, seed=seed),
        "marzneshin": MarzneshinFake(world_state, seed=seed),
        "payments": PaymentsFake(world_state, seed=seed),
        "analytics": AnalyticsFake(world_state, seed=seed),
        "messaging": MessagingFake(world_state, seed=seed),
        "observability": ObservabilityFake(world_state, seed=seed),
        "vault": VaultFake(world_state, seed=seed),
    }
