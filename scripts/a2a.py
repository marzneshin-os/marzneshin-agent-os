#!/usr/bin/env python3
"""a2a.py — agent-to-agent bus CLI (BUILD-SPEC §5, VS-3).

    a2a.py send --to qa-gate --capability qa.gate.run [--input JSON]
                [--transport T1|T2] [--priority high] [--env-epoch TS]
    a2a.py process --agent qa-gate           # drain the agent's T1 inbox
    a2a.py status                            # queues, transport health, idem
    a2a.py verify                            # CI gate for the bus itself

Handlers live here, not in lib: they may subprocess (verify.py) which lib
must never do (G9). lib/a2a.py is the bus; this file is the agents' edge.

Exit codes: 0 green, 1 a gate/task failed, 2 the CLI itself could not run
(fail closed).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

from lib import a2a, atomic, clock, events, paths  # noqa: E402

PY = sys.executable


# --- handlers: the real work agents do when a task arrives -------------------

def handle_qa_gate_run(env: dict) -> dict:
    """Run the repo's own verification gates and return the verdict.

    This is the VS-3 DoD task: a real capability with real evidence, not a
    stub — the same gates CI runs, driven through the bus.
    """
    suite = env.get("input", {}).get("suite", "all")
    flag = f"--{suite}" if suite in ("chain", "events", "schemas", "agent-cards",
                                     "lint-imports", "lint-clock") else "--all"
    out = subprocess.run(
        [PY, str(REPO / "scripts" / "verify.py"), flag],
        capture_output=True, text=True, timeout=300, cwd=REPO,
        env={**os.environ, "MARZNESHIN_OPS_ROOT": str(paths.repo_root())})
    checks = [line for line in out.stdout.splitlines() if line.startswith("[")]
    verdict = "green" if out.returncode == 0 else "red"
    if out.returncode not in (0, 1):
        raise RuntimeError(f"verify.py itself failed: {out.stderr[-300:]}")
    return {"verdict": verdict, "suite": suite, "checks": checks,
            "ran_at": clock.iso()}


def handle_probe_echo(env: dict) -> dict:
    """Minimal liveness capability: proves the bus round-trips real payloads."""
    return {"echo": env.get("input", {}), "agent": env.get("to"),
            "tick_ts": clock.iso()}


HANDLERS = {
    "qa.gate.run": handle_qa_gate_run,
    "probe.echo": handle_probe_echo,
}


# --- commands -----------------------------------------------------------------

def cmd_send(args) -> int:
    input_doc = json.loads(args.input) if args.input else {}
    provenance = json.loads(args.provenance) if args.provenance else [
        {"field": "$.input", "source": f"cli:{args.sender}", "trust": "internal"}]
    env = a2a.build_envelope(
        sender=args.sender, to=args.to, capability=args.capability,
        input=input_doc, input_provenance=provenance,
        priority=args.priority, transport=args.transport,
        env_epoch=args.env_epoch or clock.iso())
    result = a2a.send(env, actor=events.Actor(kind="agent", id=args.sender,
                                              session=os.environ.get("MARZ_SESSION")))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 1


def cmd_process(args) -> int:
    results = a2a.process_inbox(
        args.agent, HANDLERS,
        actor=events.Actor(kind="agent", id=args.agent,
                           session=os.environ.get("MARZ_SESSION")))
    payload = [r.to_dict() for r in results]
    print(json.dumps({"processed": len(payload), "results": payload},
                     indent=2, ensure_ascii=False))
    return 0 if all(r.ok for r in results) else 1


def cmd_process_t2(args) -> int:
    result = a2a.process_t2_record(
        args.task_id, HANDLERS, agent_id=args.agent,
        actor=events.Actor(kind="agent", id=args.agent,
                           session=os.environ.get("MARZ_SESSION")))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 1


def cmd_status(args) -> int:
    reg = a2a.registry()
    health = atomic.read_json(paths.transport_health_file(), default={}) or {}
    lines = [f"a2a bus status at {clock.iso()}"]
    for agent_id in sorted(reg.get("agents", {})):
        entry = reg["agents"][agent_id]
        pref = entry.get("transports", {}).get("preferred", "T1")
        lines.append(f"  {agent_id}: inbox={a2a.queue_depth(agent_id)} preferred={pref}")
    for name, st in sorted(health.items()):
        lines.append(f"  transport {name}: degraded={st.get('degraded')} "
                     f"failures={st.get('consecutive_failures', 0)} "
                     f"successes={st.get('consecutive_successes', 0)}")
    idem_dir = paths.a2a_idem_dir()
    n_idem = len(list(idem_dir.glob("*.json"))) if idem_dir.exists() else 0
    lines.append(f"  idempotency records: {n_idem}")
    print("\n".join(lines))
    return 0


def cmd_verify(args) -> int:
    """Bus self-check (CI gate): registry sane, in-flight envelopes valid."""
    problems: list[str] = []
    try:
        reg = a2a.registry(reload=True)
    except a2a.A2AError as exc:
        print(f"[FAIL] registry: {exc}")
        return 1
    agents = reg.get("agents", {})
    for agent_id, entry in agents.items():
        for cap in entry.get("capabilities", []):
            if cap not in reg.get("capabilities", {}):
                problems.append(f"{agent_id}: capability {cap!r} not in registry capabilities")
        pref = entry.get("transports", {}).get("preferred", "T1")
        if pref not in entry.get("transports", {}).get("allowed", []):
            problems.append(f"{agent_id}: preferred transport {pref} not in allowed")
    for agent_id in agents:
        inbox = paths.a2a_inbox(agent_id)
        if not inbox.exists():
            continue
        for path in sorted(inbox.glob("A2A-*.json")):
            doc = atomic.read_json(path, default=None)
            if doc is None:
                problems.append(f"{paths.rel(path)}: unreadable envelope")
                continue
            errs = a2a.validate_envelope(doc)
            problems.extend(f"{paths.rel(path)}: {e}" for e in errs)
    if problems:
        for p in problems:
            print(f"[FAIL] {p}")
        return 1
    print(f"[PASS] a2a bus: registry {len(agents)} agents, in-flight envelopes valid")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="a2a.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("send", help="route one envelope through policy + transports")
    p.add_argument("--to", required=True)
    p.add_argument("--capability", required=True)
    p.add_argument("--sender", default="orchestrator")
    p.add_argument("--input", help="JSON object")
    p.add_argument("--provenance", help="JSON array of provenance records")
    p.add_argument("--transport", choices=["T1", "T2"])
    p.add_argument("--priority", default="normal",
                   choices=["low", "normal", "high", "critical"])
    p.add_argument("--env-epoch")
    p.set_defaults(fn=cmd_send)

    p = sub.add_parser("process", help="drain an agent's inbox")
    p.add_argument("--agent", required=True)
    p.set_defaults(fn=cmd_process)

    p = sub.add_parser("process-t2", help="execute one T2-delivered task (§5.2)")
    p.add_argument("--agent", required=True)
    p.add_argument("--task-id", required=True)
    p.set_defaults(fn=cmd_process_t2)

    p = sub.add_parser("status", help="queue depths + transport health")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("verify", help="CI gate for the bus")
    p.set_defaults(fn=cmd_verify)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"a2a: broken: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
