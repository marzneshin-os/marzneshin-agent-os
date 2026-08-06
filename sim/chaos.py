"""sim/chaos.py — seeded fault injection (§16).

Chaos is scripted per scenario (YAML) but executed through one injector so
every injection is logged with the tick it fired at — with the seed, that
makes any failure exactly reproducible.

Kinds:
  node_down             world: a Marzneshin node dies for N ticks
  payment_provider_down world: provider refuses for N ticks
  adapter_down          fakes: a whole adapter is unreachable for N ticks
  adapter_flaky         fakes: the next N calls on an adapter raise
  agent_kill            actors: an agent actor is killed mid-task (crash test)
  clock_skew            clock: jump forward/backward without warning
  cost_spike            budget: multiply recorded costs for N ticks
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Injection:
    kind: str
    at_tick: int
    params: dict
    fired: bool = False
    detail: str = ""


class Chaos:
    def __init__(self, *, world, fakes: dict, clock, actors: dict | None = None,
                 injections: list[dict] | None = None) -> None:
        self.world = world
        self.fakes = fakes
        self.clock = clock
        self.actors = actors or {}
        self.injections = [Injection(kind=i["kind"], at_tick=int(i.get("at_tick", 0)),
                                     params={k: v for k, v in i.items()
                                             if k not in ("kind", "at_tick")})
                           for i in (injections or [])]
        self.log: list[dict] = []

    def step(self, tick: int) -> list[dict]:
        """Fire any injection scheduled for this tick. Returns fired events."""
        fired = []
        for inj in self.injections:
            if inj.fired or tick < inj.at_tick:
                continue
            inj.fired = True
            detail = self._fire(inj)
            inj.detail = detail
            event = {"tick": tick, "kind": inj.kind, "detail": detail}
            self.log.append(event)
            fired.append(event)
        return fired

    def _fire(self, inj: Injection) -> str:
        p = inj.params
        if inj.kind == "node_down":
            ev = self.world.node_down(p.get("node"), ticks=int(p.get("ticks", 12)))
            return f"node {ev['node']} down for {ev['ticks']} ticks"
        if inj.kind == "payment_provider_down":
            ev = self.world.payment_provider_down(ticks=int(p.get("ticks", 24)))
            return f"payments down for {ev['ticks']} ticks"
        if inj.kind == "adapter_down":
            name = p["adapter"]
            self.fakes[name].set_down(True)
            ticks = int(p.get("ticks", 6))
            # schedule recovery via world maintenance list
            self.world.__dict__.setdefault("_adapter_recovery", []).append(
                {"at": self.world.tick + ticks, "adapter": name})
            return f"adapter {name} down for {ticks} ticks"
        if inj.kind == "adapter_flaky":
            name = p["adapter"]
            self.fakes[name].fail_next(int(p.get("count", 3)))
            return f"adapter {name} fails next {p.get('count', 3)} calls"
        if inj.kind == "agent_kill":
            name = p["agent"]
            actor = self.actors.get(name)
            if actor is not None:
                actor.kill(reason="chaos agent_kill")
            return f"agent {name} killed mid-task"
        if inj.kind == "agent_stall":
            name = p["agent"]
            actor = self.actors.get(name)
            if actor is not None:
                actor.kill(reason="chaos agent_stall (process hung: heartbeats stop, lease decays)")
            return f"agent {name} stalled (lease will expire)"
        if inj.kind == "clock_skew":
            minutes = float(p.get("minutes", 30))
            self.clock.advance(minutes=minutes)
            return f"clock jumped {minutes}m"
        if inj.kind == "cost_spike":
            self.world.__dict__["_cost_multiplier"] = float(p.get("multiplier", 3.0))
            self.world.__dict__["_cost_multiplier_left"] = int(p.get("ticks", 24))
            return f"cost x{p.get('multiplier', 3.0)} for {p.get('ticks', 24)} ticks"
        if inj.kind == "member_remove":
            # §11.1 administrative trigger: the member is REMOVED, not crashed.
            # No tombstone may follow (crash_rate must not move) and, when the
            # scenario disables the harness standby (MARZ_SUCCESSION_STANDBY),
            # no resurrection either: the succession flow owns the healing.
            name = p["agent"]
            actor = self.actors.get(name)
            if actor is not None:
                actor.kill(reason="chaos member_remove (§11.1: member removed)")
            return f"member {name} removed (§11.1 succession trigger)"
        if inj.kind == "owner_silent":
            # §11.2 trigger: the HUMAN stops responding. OwnerActor carries
            # replaceable=False, so harness succession will not resurrect it —
            # an absent human is the fault being modelled, not a crash.
            name = p.get("agent", "owner")
            actor = self.actors.get(name)
            if actor is not None:
                actor.kill(reason="chaos owner_silent (§11.2: owner unresponsive)")
            return f"owner {name} silent (no succession — human absence)"
        if inj.kind == "killswitch_corrupt":
            # Fault: the K1 file becomes unparseable (partial write, disk
            # corruption). §6.3 + lib: an unreadable kill file must read as an
            # ENGAGED global kill — never as permission.
            from lib import paths as _paths
            kill_path = _paths.kill_file()
            kill_path.parent.mkdir(parents=True, exist_ok=True)
            kill_path.write_text("{ this is not json !!", encoding="utf-8")
            return "state/KILL corrupted (unparseable)"
        if inj.kind == "killswitch_recover":
            # The operator path back: reconcile rewrites K1 clean and stamps a
            # fresh heartbeat; optionally restarts a dead heartbeat service.
            from lib import killswitch as _ks
            _ks.reconcile(external=[], sources=["sim:operator"],
                          verified_by="sim-operator")
            revived = ""
            name = p.get("agent")
            if name and name in self.actors and not self.actors[name].alive:
                self.actors[name].alive = True
                self.actors[name].death_reason = None
                revived = f"; {name} service restarted"
            return f"operator reconcile: K1 clean + fresh heartbeat{revived}"
        return f"unknown chaos kind {inj.kind!r} (ignored)"

    @staticmethod
    def maintenance(world, fakes) -> None:
        """Per-tick recovery bookkeeping for timed injections."""
        world.tick_maintenance()
        for item in world.__dict__.get("_adapter_recovery", []):
            if world.tick >= item["at"]:
                fakes[item["adapter"]].set_down(False)
                world.__dict__["_adapter_recovery"].remove(item)
        if world.__dict__.get("_cost_multiplier_left", 0) > 0:
            world.__dict__["_cost_multiplier_left"] -= 1
            if world.__dict__["_cost_multiplier_left"] == 0:
                world.__dict__["_cost_multiplier"] = 1.0
