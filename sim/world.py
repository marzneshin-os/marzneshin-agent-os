"""sim/world.py — the deterministic world the harness proves claims in (§16).

The world holds PHYSICAL truth: nodes that are actually up or down, users
whose connections actually succeed or fail, payments that actually settle.
Adapters (sim/fakes/) are windows into this truth; chaos (sim/chaos.py) is
how it goes wrong. Agents never see the world directly — they see what the
fakes report, which is the whole point of testing the control loop.

Everything here is deterministic given a seed: all randomness comes from a
single seeded RNG stream owned by the world, and time comes from the injected
VirtualClock. A failure replay is therefore exact, which is what makes `seed`
in a receipt meaningful.

Modelled (minimal but causal):
  nodes     Marzneshin nodes; up/down, capacity, load. Down nodes serve 0%.
  users     attempt connections each tick; success depends on node health.
  csr       connection success rate over a rolling window (the SLO, §14).
  funnel    trials -> first connection -> paid; bad CSR suppresses conversion.
  revenue   settled payments; refunds rise when CSR degrades.
  cost      infra $/node-hour + agent token spend fed back from the ledger.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Node:
    id: str
    up: bool = True
    in_rotation: bool = True      # excluded from serving by config action
    capacity: int = 5000          # concurrent connections
    load: float = 0.35            # fraction of capacity in use
    flap_rate: float = 0.0005     # per-tick probability of a spontaneous flap
    down_ticks_left: int = 0      # counts down to auto-recovery for flaps

    def success_prob(self, rng: random.Random) -> float:
        if not self.up:
            return 0.0
        # Overloaded nodes drop connections; healthy ones are ~99%.
        penalty = max(0.0, self.load - 0.7) * 0.5
        return max(0.5, 0.99 - penalty)


@dataclass
class WorldConfig:
    nodes: int = 3
    users: int = 2000
    tick_s: int = 300             # 5-minute ticks
    duration_h: int = 72
    trials_per_tick: float = 2.0
    paid_conversion: float = 0.35
    price_usd: float = 9.0
    node_cost_h: float = 0.05


class World:
    def __init__(self, config: WorldConfig, *, seed: int) -> None:
        self.config = config
        # clock-ok: the world owns its PHYSICAL randomness as a private seeded
        # stream (D6 reproducibility). It must NOT share clock.rng() with fakes
        # and actors — one consumer's draws would perturb the physical stream
        # and make replay order-dependent. Deliberate, per §16 world design.
        self.rng = random.Random(seed)  # clock-ok: private seeded physical stream (see above)
        self.tick = 0
        self.nodes = [Node(id=f"node-{i+1}") for i in range(config.nodes)]
        self.attempts_window: list[bool] = []     # rolling CSR window
        self.window_max = 2000
        self.users_active = 0
        self.trials_total = 0
        self.paid_total = 0
        self.revenue_usd = 0.0
        self.refunds_usd = 0.0
        self.payments_provider_up = True
        self.alerts: list[dict] = []
        self.events_log: list[dict] = []          # physical-truth log (not repo events)
        self.profiles: dict[str, dict] = {"reality-v6": {"canary_pct": 100, "good": True}}
        self.active_profile = "reality-v6"
        self.checkouts: dict[str, dict] = {}
        self.suppressed: set[str] = set()
        self._trial_backlog = 0.0

    # --- physical dynamics -------------------------------------------------

    def step(self) -> None:
        """Advance one tick: flaps, recoveries, connection attempts, funnel."""
        self.tick += 1
        for node in self.nodes:
            if node.up and self.rng.random() < node.flap_rate:
                node.up = False
                node.down_ticks_left = self.rng.randint(1, 3)
                self.events_log.append({"tick": self.tick, "kind": "node_flap",
                                        "node": node.id})
            elif not node.up and node.down_ticks_left > 0:
                node.down_ticks_left -= 1
                if node.down_ticks_left == 0:
                    node.up = True
                    self.events_log.append({"tick": self.tick, "kind": "node_recovered",
                                            "node": node.id})
            # Load mean-reverts to baseline (+ a share of any excluded peer's
            # traffic); without reversion the random walk saturates every node
            # and CSR never recovers — a broken world proves nothing.
            excluded = sum(1 for n in self.nodes if not n.in_rotation)
            target = 0.35 + 0.1 * (excluded / max(1, len(self.nodes)))
            node.load = min(1.0, max(0.05,
                node.load + 0.05 * (target - node.load) + self.rng.uniform(-0.01, 0.01)))

        # Users attempt connections against the ROTATION pool: a down node
        # still in rotation fails its share of attempts until a config action
        # excludes it — that is the lever the control loop acts through.
        healthy = [n for n in self.nodes if n.up]
        base_active = int(self.config.users * (0.25 + 0.1 * len(healthy)))
        self.users_active = min(self.config.users, base_active)
        attempts = max(20, int(self.users_active * 0.2))
        pool = [n for n in self.nodes if n.in_rotation] or self.nodes
        for _ in range(attempts):
            node = self.rng.choice(pool)
            ok = self.rng.random() < node.success_prob(self.rng)
            self.attempts_window.append(ok)
        if len(self.attempts_window) > self.window_max:
            del self.attempts_window[: len(self.attempts_window) - self.window_max]

        # Funnel: trials convert to paid only when the service works.
        csr = self.csr()
        self._trial_backlog += self.config.trials_per_tick
        new_trials = int(self._trial_backlog)
        self._trial_backlog -= new_trials
        self.trials_total += new_trials
        if self.payments_provider_up:
            for _ in range(new_trials):
                p = self.config.paid_conversion * max(0.1, csr - 0.85) / 0.14
                if self.rng.random() < min(self.config.paid_conversion, p):
                    self.paid_total += 1
                    self.revenue_usd += self.config.price_usd
        # Refund pressure when CSR is bad.
        if csr < 0.95 and self.paid_total > 0 and self.rng.random() < 0.3:
            amount = self.config.price_usd
            self.refunds_usd += amount
            self.revenue_usd = max(0.0, self.revenue_usd - amount)
            self.events_log.append({"tick": self.tick, "kind": "refund",
                                    "amount": amount, "csr": round(csr, 4)})

    # --- observations (what fakes report) ----------------------------------

    def csr(self) -> float:
        if not self.attempts_window:
            return 1.0
        return sum(self.attempts_window) / len(self.attempts_window)

    def nodes_healthy(self) -> int:
        return sum(1 for n in self.nodes if n.up)

    def metrics(self) -> dict:
        return {
            "tick": self.tick,
            "csr": round(self.csr(), 4),
            "nodes_up": self.nodes_healthy(),
            "nodes_total": len(self.nodes),
            "users_active": self.users_active,
            "trials_total": self.trials_total,
            "paid_total": self.paid_total,
            "revenue_usd": round(self.revenue_usd, 2),
            "refunds_usd": round(self.refunds_usd, 2),
            "payments_provider_up": self.payments_provider_up,
            "active_profile": self.active_profile,
        }

    # --- chaos entry points (called by sim/chaos.py) ------------------------

    def publish_config(self, profile: str, *, canary_pct: int = 1,
                       exclude_nodes: list[str] | None = None,
                       include_all: bool = False) -> dict:
        """The control loop's lever: rotate out dead nodes (CSR recovers) or
        restore full rotation on rollback."""
        self.profiles[profile] = {"canary_pct": canary_pct, "good": True,
                                  "exclude_nodes": exclude_nodes or []}
        self.active_profile = profile
        for node in self.nodes:
            if include_all:
                node.in_rotation = True
            elif exclude_nodes and node.id in exclude_nodes:
                node.in_rotation = False
        self.events_log.append({"tick": self.tick, "kind": "config_published",
                                "profile": profile, "exclude_nodes": exclude_nodes or []})
        return {"published": profile, "rotation": [n.id for n in self.nodes if n.in_rotation]}

    def node_down(self, node_id: str | None = None, *, ticks: int = 12) -> dict:
        node = (next((n for n in self.nodes if n.id == node_id), None)
                or self.rng.choice(self.nodes))
        node.up = False
        node.down_ticks_left = ticks
        event = {"tick": self.tick, "kind": "chaos_node_down", "node": node.id,
                 "ticks": ticks}
        self.events_log.append(event)
        return event

    def payment_provider_down(self, *, ticks: int = 24) -> dict:
        self.payments_provider_up = False
        self._payments_down_left = ticks
        event = {"tick": self.tick, "kind": "chaos_payments_down", "ticks": ticks}
        self.events_log.append(event)
        return event

    def tick_maintenance(self) -> None:
        """Per-tick housekeeping for timed chaos effects."""
        if getattr(self, "_payments_down_left", 0) > 0:
            self._payments_down_left -= 1
            if self._payments_down_left == 0:
                self.payments_provider_up = True
                self.events_log.append({"tick": self.tick,
                                        "kind": "payments_recovered"})
