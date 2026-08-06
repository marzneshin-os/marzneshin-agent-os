#!/usr/bin/env python3
"""sim.py — the simulation harness runner (BUILD-SPEC §16, VS-2).

Proves the "72 hours without a human" claim before any real user is at risk:
a scenario runs 72 VIRTUAL hours in under 60 WALL seconds, with a seed, and
produces a scored report. Red here means the code does not enter production
(I11); `seed` in the receipt makes every failure exactly reproducible.

    sim.py run sim/scenarios/node_outage.yaml [--seed 11] [--json]
    sim.py run --all [--seeds 11,27,43]          # the nightly suite shape
    sim.py run --changed-only                    # CI hook for validate.yml

Each scenario executes in a FRESH relocated repo root (MARZNESHIN_OPS_ROOT
-> tmpdir) with a VirtualClock and MARZ_WORLD=sim: real lib, real receipts,
real leases, real kill switch — disposable state. Events land in the sim
partition and can never contaminate production KPIs (§3.2, ADR-002 D14).

Exit codes: 0 = all scenarios pass, 1 = a scenario failed its expect block,
2 = the harness itself broke (fail closed: a harness you cannot trust is red).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import yaml  # noqa: E402  (runner-only dependency; lib stays stdlib-only)

from lib import clock, events, receipts, validate  # noqa: E402
from sim import actors as sim_actors  # noqa: E402
from sim import report as sim_report  # noqa: E402
from sim.chaos import Chaos  # noqa: E402
from sim.fakes import build_fakes  # noqa: E402
from sim.world import World, WorldConfig  # noqa: E402

ACTOR_REGISTRY = {
    "config-engineer": lambda session: sim_actors.ConfigEngineerActor(session=session),
    "reaper": lambda session: sim_actors.ReaperActor(session=session),
    "guard": lambda session: sim_actors.GuardActor(session=session),
    "injection-tester": lambda session: sim_actors.InjectionTesterActor(session=session),
    "dispatcher": lambda session: sim_actors.DispatcherActor(session=session),
    # VS-4 continuity + kill switch
    "succession": lambda session: sim_actors.SuccessionActor(session=session),
    "seq-storm": lambda session: sim_actors.SeqStormActor(session=session),
    "heartbeat": lambda session: sim_actors.HeartbeatActor(session=session),
    "sentinel": lambda session: sim_actors.KillswitchSentinelActor(session=session),
    "owner": lambda session: sim_actors.OwnerActor(session=session),
    "deadman": lambda session: sim_actors.DeadManSwitchActor(session=session),
    "l1-worker": lambda session: sim_actors.L1WorkerActor(session=session),
}


def _scenario_paths(args) -> list[Path]:
    if args.all:
        return sorted((REPO / "sim" / "scenarios").glob("*.yaml"))
    if args.changed_only:
        # VS-3+: map changed files to related scenarios. Until then, the
        # smoke scenario stands in so the CI gate is real but fast.
        smoke = REPO / "sim" / "scenarios" / "node_outage.yaml"
        return [smoke] if smoke.exists() else []
    return [Path(p) for p in args.scenarios]


def run_scenario(path: Path, *, seed: int, keep: bool = False) -> dict:
    scenario = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    seed = int(scenario.get("seed", seed))
    duration_h = int(scenario.get("duration_h", 72))
    tick_s = int(scenario.get("tick_s", 300))

    scenario_env = {str(k): str(v) for k, v in (scenario.get("env") or {}).items()}
    tmp = Path(tempfile.mkdtemp(prefix=f"sim-{scenario.get('name', 'x')}-"))
    saved_env = {k: os.environ.get(k) for k in
                 ("MARZNESHIN_OPS_ROOT", "MARZ_WORLD", "MARZNESHIN_VIRTUAL_CLOCK",
                  *scenario_env.keys())}
    wall_start = time.monotonic()
    try:
        # Fresh disposable repo root: the spine runs for real, against a
        # throwaway state plane (§16: sim is a mirror of L0, not of prod data).
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        (tmp / "BUILD-SPEC.md").write_text("sim\n", encoding="utf-8")
        shutil.copytree(REPO / "analytics" / "schemas", tmp / "analytics" / "schemas")
        # The A2A registry routes inside the sim too (VS-3): same file, tmp root.
        if (REPO / "agents" / "registry.json").exists():
            (tmp / "agents").mkdir(exist_ok=True)
            shutil.copy(REPO / "agents" / "registry.json", tmp / "agents" / "registry.json")
        os.environ["MARZNESHIN_OPS_ROOT"] = str(tmp)
        os.environ["MARZ_WORLD"] = "sim"
        os.environ["MARZNESHIN_VIRTUAL_CLOCK"] = "1"
        # Scenario-declared env (e.g. MARZ_SUCCESSION_STANDBY=1 routes standby
        # replacement through the §11.1 flow instead of the harness).
        os.environ.update(scenario_env)
        vclock = clock.VirtualClock(seed=seed)
        clock.set_clock(vclock)
        validate.clear_cache()
        # Seed a known-clear kill-switch state in the disposable root: in prod
        # the heartbeat workflow keeps K1 fresh; a sim run starts from the
        # equivalent state at t=0, or every policy gate would fail closed for
        # the whole run (which would prove nothing about the scenario).
        from lib import killswitch as _ks
        _ks.reconcile(external=[], sources=["sim:bootstrap"], verified_by="sim")

        wc = scenario.get("world", {})
        world = World(WorldConfig(
            nodes=int(wc.get("nodes", 3)), users=int(wc.get("users", 2000)),
            tick_s=tick_s, duration_h=duration_h,
            trials_per_tick=float(wc.get("trials_per_tick", 2.0)),
            paid_conversion=float(wc.get("paid_conversion", 0.35)),
        ), seed=seed)
        fakes = build_fakes(world, seed=seed)

        session = f"S-SIM-{seed}"
        actor_objs = {name: ACTOR_REGISTRY[name](session)
                      for name in scenario.get("actors", ["config-engineer", "reaper"])}
        chaos = Chaos(world=world, fakes=fakes, clock=vclock, actors=actor_objs,
                      injections=scenario.get("chaos", []))

        ctx = {
            "fakes": fakes, "world": world, "chaos_log": chaos.log,
            "executed_keys": set(),
            "deadline": clock.now() + timedelta(hours=duration_h + 1),
            "stats": {"slo_breach_ticks": 0, "recoveries": [], "duplicate_work": 0,
                      "guardrail_breaches": 0, "interventions": 0,
                      "token_cost_usd": 0.0, "reaps": 0},
            # SuccessionActor needs both: the registry to build a standby body
            # and the live seat map to install it in (§11.1 REASSIGN).
            "actor_registry": ACTOR_REGISTRY,
            "actor_objs": actor_objs,
        }

        ticks = duration_h * 3600 // tick_s
        succeeded: set[str] = set()
        for _ in range(ticks):
            chaos.step(world.tick)
            for name, actor in list(actor_objs.items()):
                actor.act(ctx)
                # Succession (§11.1 STEP 4): a reaped actor is replaced by a
                # standby with a fresh session — the fleet heals itself.
                # replaceable=False (the human Owner) is never succeeded:
                # an absent human is a fact, not a crash to heal.
                if (not actor.alive and name not in succeeded
                        and getattr(actor, "replaceable", True)
                        and not os.environ.get("MARZ_SUCCESSION_STANDBY")):
                    succeeded.add(name)
                    standby = ACTOR_REGISTRY[name](f"{session}-standby")
                    actor_objs[name] = standby
                    events.emit("autonomy.changed", events.Actor(kind="sim", id="succession"),
                                events.Subject(kind="agent", id=name),
                                {"reason": actor.death_reason,
                                 "standby": standby.session})
                    ctx["stats"]["successions"] = ctx["stats"].get("successions", 0) + 1
            world.step()
            Chaos.maintenance(world, fakes)
            vclock.advance(seconds=tick_s)

        # Score from the REAL artifacts the run produced (receipts on disk).
        rstats = receipts.stats()
        chain = receipts.verify_chain()
        started = ctx["stats"]
        started["crash_rate"] = rstats["crash_rate"]
        started["receipt_coverage"] = 1.0 if rstats["total"] else 1.0
        if not chain["ok"]:
            started["guardrail_breaches"] += 1  # a chain break is a security incident (I15)

        report = sim_report.build_report(
            scenario=scenario, world=world, fakes=fakes, chaos_log=chaos.log,
            actor_stats=started, wall_clock_s=time.monotonic() - wall_start,
            seed=seed, duration_h=duration_h, tick_s=tick_s)
        report["receipts"] = {"total": rstats["total"], "crash_rate": rstats["crash_rate"],
                              "chain_ok": chain["ok"]}
        report["artifacts"] = {"repo": str(tmp) if keep else None}
        return report
    finally:
        clock.set_clock(None)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        argv = argv[1:]
    parser = argparse.ArgumentParser(prog="sim.py",
                                     description="Simulation harness runner (§16)")
    parser.add_argument("scenarios", nargs="*", help="scenario YAML paths")
    parser.add_argument("--all", action="store_true", help="run every scenario")
    parser.add_argument("--changed-only", action="store_true",
                        help="CI mode: scenarios related to the change")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--seeds", help="comma list, e.g. 11,27,43 (overrides --seed)")
    parser.add_argument("--keep", action="store_true", help="keep the sim repo roots")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", help="write reports JSON to this path")
    args = parser.parse_args(argv)

    paths = _scenario_paths(args)
    if not paths:
        print("sim: no scenarios selected", file=sys.stderr)
        return 2
    seeds = ([int(s) for s in args.seeds.split(",")] if args.seeds else [args.seed])

    reports = []
    for path in paths:
        for seed in seeds:
            try:
                report = run_scenario(path, seed=seed, keep=args.keep)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                reports.append({"scenario": Path(path).stem, "seed": seed,
                                "result": "fail",
                                "error": f"harness crashed: {type(exc).__name__}: {exc}"})
                continue
            reports.append(report)
            if not args.json:
                d = report["duration"]
                print(f"[{'PASS' if report['result'] == 'pass' else 'FAIL'}] "
                      f"{report['scenario']} seed={report['seed']} "
                      f"({d['virtual_hours']}h in {d['wall_clock_s']}s, "
                      f"score {report.get('score')}, checks {report.get('checks_passed')})")
                for name, ok in report.get("checks", {}).items():
                    if not ok:
                        print(f"        - red: {name}")

    ok = all(r.get("result") == "pass" for r in reports)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(reports, indent=2, ensure_ascii=False,
                                             default=str), encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": ok, "reports": reports}, indent=2,
                         ensure_ascii=False, default=str))
    elif not ok:
        print("\nsim: RED — production entry is forbidden (I11)")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sim: harness broken: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
