#!/usr/bin/env python3
"""Kill switch driver — the K4 path, and the reconciler for K2/K3/K5.

BUILD-SPEC §6.3 defines five activation paths. Only K1 (repo file) and K2 (env
var) can be read without a network, so they are the only two a worker consults
directly. This script is what makes the other three real (ADR-002 D15):

    K1  state/KILL                  read by every worker, no network
    K2  KILL_SWITCH env var         read by every worker, no network
    K3  Moxt Workflow task status   polled here -> reconciled into K1
    K4  this CLI                    engage/release locally, instantly
    K5  automatic triggers          evaluated here -> reconciled into K1

Why reconcile instead of polling everywhere: hooks get a 3-second budget and are
forbidden from doing network I/O (§7.2, G9). A hook that called the Moxt API to
ask "am I killed?" would be both slow and flaky, and a flaky safety check is
worse than none because it teaches people to bypass it. So the network paths are
polled on a schedule and folded into the local file.

Usage:
    killswitch.py status  [--agent A] [--capability C] [--workstream W] [--json]
    killswitch.py engage  SCOPE [--target T] --reason R [--by WHO] [--ttl MINUTES]
    killswitch.py release SCOPE [--target T] [--by WHO]
    killswitch.py reconcile [--k3-status STATUS] [--k3-reason R] [--skip-auto]
    killswitch.py auto     [--json]
    killswitch.py verify   [--json]

Exit codes:
    0  clear to operate / command succeeded
    1  a kill is engaged, or the requested drill failed
    2  state unreadable -> fail closed (§6.3: "I don't know" == "stop")
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import budget, clock, killswitch, leases, paths  # noqa: E402
from lib.killswitch import KillEntry, Scope, Verdict  # noqa: E402

# Moxt Workflow statuses that mean "stop". The Control Room task for the kill
# switch is human-facing, so we accept the words a human would actually use.
K3_KILL_STATUSES = {"engaged", "kill", "killed", "stop", "stopped", "halt", "in progress"}
K3_CLEAR_STATUSES = {"clear", "cleared", "running", "done", "resolved", "backlog"}


# --- K5: automatic triggers -------------------------------------------------

def evaluate_auto(*, spike_multiplier: float = 3.0) -> list[dict]:
    """Evaluate the K5 automatic conditions from §6.3.

    Lives in the script rather than in lib/killswitch.py on purpose: the import
    DAG in lib/__init__.py puts killswitch above budget and leases, and pulling
    them in would create the cycle that the DAG exists to prevent. The script
    layer is allowed to depend on everything.

    Returns a list of findings. Each is a candidate kill, not an engaged one —
    engaging is the caller's decision so that `auto` can be run read-only.
    """
    findings: list[dict] = []

    # Cost spike: projected end-of-day above a multiple of the median baseline.
    try:
        spike = budget.spike_detected(multiplier=spike_multiplier)
        if spike.get("detected"):
            findings.append({
                "scope": Scope.BUDGET.value, "target": None,
                "reason": f"cost spike: {spike['reason']}",
                "trigger": "cost_spike", "evidence": spike,
            })
    except Exception as exc:  # a broken ledger must not silence the others
        findings.append({
            "scope": Scope.BUDGET.value, "target": None,
            "reason": f"budget ledger unreadable ({type(exc).__name__}: {exc}); "
                      f"failing closed on spend",
            "trigger": "budget_unreadable", "evidence": None,
        })

    # Budget exhaustion: 100% of a cap is a hard stop (§6.4).
    try:
        st = budget.status("workspace")
        if st["exhausted"]:
            findings.append({
                "scope": Scope.BUDGET.value, "target": None,
                "reason": f"workspace budget exhausted: utilization "
                          f"{st['utilization']:.0%} of cap",
                "trigger": "budget_exhausted", "evidence": st,
            })
    except Exception:
        pass  # already reported above if the ledger is unreadable

    # Three consecutive missed heartbeats => the agent is presumed dead (§6.3 K5).
    try:
        for zombie in leases.find_zombies():
            missed = zombie["heartbeat_age_seconds"] / (leases.DEFAULT_HEARTBEAT_SLA_MINUTES * 60)
            if missed >= 3:
                findings.append({
                    "scope": Scope.WORKSTREAM.value, "target": zombie["workstream"],
                    "reason": f"agent {zombie['holder']} missed {int(missed)} consecutive "
                              f"heartbeats on {zombie['workstream']}",
                    "trigger": "heartbeats_missed", "evidence": zombie,
                })
    except leases.LeaseError as exc:
        findings.append({
            "scope": Scope.GLOBAL.value, "target": None,
            "reason": f"lease state unverifiable ({exc}); failing closed",
            "trigger": "lease_unreadable", "evidence": None,
        })

    return findings


# --- K3: Moxt Control Room --------------------------------------------------

def read_k3(status: str | None, reason: str | None) -> list[KillEntry]:
    """Interpret the Moxt Control Room kill-switch task status.

    The status is passed in rather than fetched: this repo has no Moxt
    credential (GAP-REPORT-002 §2 — zero secrets stored), and inventing an API
    call that cannot run would be a fake safety path. The heartbeat workflow
    supplies it via `adapters/moxt.read_killswitch_task` once that adapter and
    its token exist. Until then K3 is driven manually or left absent, and
    `verify` reports it as such instead of claiming it works.
    """
    if not status:
        return []
    normalized = status.strip().lower()
    if normalized in K3_CLEAR_STATUSES:
        return []
    if normalized in K3_KILL_STATUSES:
        return [KillEntry(scope=Scope.GLOBAL.value, target=None,
                          reason=reason or f"Moxt Control Room task status: {status}",
                          engaged_at=clock.iso(), engaged_by="moxt:control-room",
                          source="K3")]
    # An unrecognised status is not a clearance. Fail closed on ambiguity.
    return [KillEntry(scope=Scope.GLOBAL.value, target=None,
                      reason=f"Moxt Control Room status {status!r} is not recognised as "
                             f"either engaged or clear; treating as engaged (§6.3 fail-closed)",
                      engaged_at=clock.iso(), engaged_by="moxt:control-room",
                      source="K3")]


# --- commands ---------------------------------------------------------------

def cmd_status(args) -> int:
    state = killswitch.check(agent=args.agent, capability=args.capability,
                             workstream=args.workstream,
                             autonomy_level=args.autonomy)
    if args.json:
        print(json.dumps(state.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"verdict:   {state.verdict.value}")
        print(f"sources:   {', '.join(state.sources_consulted)}")
        fresh = state.freshness_seconds
        print(f"freshness: {int(fresh)}s" if fresh is not None else "freshness: unknown")
        print(f"detail:    {state.detail}")
        for e in state.entries:
            target = f":{e.target}" if e.target else ""
            print(f"  [{e.source}] {e.scope}{target} — {e.reason} (by {e.engaged_by})")
        print(f"L{args.autonomy} permitted: {state.allows(args.autonomy)}")
    if state.verdict is Verdict.KILLED:
        return 1
    if state.verdict is Verdict.UNKNOWN:
        return 2
    return 0


def cmd_engage(args) -> int:
    expires = None
    if args.ttl:
        from datetime import timedelta
        expires = clock.to_iso(clock.now() + timedelta(minutes=args.ttl))
    state = killswitch.engage(args.scope, target=args.target, reason=args.reason,
                              engaged_by=args.by, expires_at=expires, source="K4")
    scoped = f"{args.scope}" + (f":{args.target}" if args.target else "")
    print(f"engaged {scoped} — {args.reason}")
    print(f"verdict now: {state.verdict.value} ({len(state.entries)} active entry/entries)")
    if expires:
        print(f"expires at:  {expires}")
    print("\nDisengaging is always a human decision and always needs an ADR (§6.3).")
    return 0


def cmd_release(args) -> int:
    state = killswitch.release(args.scope, target=args.target, released_by=args.by)
    scoped = f"{args.scope}" + (f":{args.target}" if args.target else "")
    print(f"released {scoped} by {args.by}")
    print(f"verdict now: {state.verdict.value}")
    if state.verdict is Verdict.KILLED:
        print("NOTE: other kill entries are still active — the system remains stopped.")
    return 0


def cmd_auto(args) -> int:
    findings = evaluate_auto()
    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False, default=str))
    elif not findings:
        print("no automatic (K5) trigger conditions met")
    else:
        for f in findings:
            print(f"  [{f['trigger']}] {f['scope']}"
                  f"{':' + f['target'] if f['target'] else ''} — {f['reason']}")
    return 1 if findings else 0


def cmd_reconcile(args) -> int:
    """Fold K2/K3/K5 into K1 and refresh the freshness timestamp.

    Run by the `heartbeat` workflow every 15 minutes. That cadence is the same
    as FRESHNESS_LIMIT_SECONDS by design: if reconciliation stops, the local
    verdict goes stale and every worker fails closed on its own.
    """
    external: list[KillEntry] = []
    sources = ["K1:state/KILL", "K2:env/KILL_SWITCH"]

    k3 = read_k3(args.k3_status, args.k3_reason)
    external.extend(k3)
    if args.k3_status:
        sources.append("K3:moxt/control-room")

    auto_findings: list[dict] = []
    if not args.skip_auto:
        auto_findings = evaluate_auto()
        sources.append("K5:auto")
        for f in auto_findings:
            external.append(KillEntry(scope=f["scope"], target=f["target"],
                                      reason=f["reason"], engaged_at=clock.iso(),
                                      engaged_by=f"orchestrator:{f['trigger']}",
                                      source="K5"))

    state = killswitch.reconcile(external=external, sources=sources,
                                 verified_by=args.by,
                                 prune_sources=["K3", "K5"])
    result = {
        "verdict": state.verdict.value,
        "sources": sources,
        "k3_entries": len(k3),
        "k5_findings": [f["trigger"] for f in auto_findings],
        "active_entries": len(state.entries),
        "reconciled_at": clock.iso(),
    }
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"reconciled from: {', '.join(sources)}")
        print(f"K3 entries: {len(k3)} · K5 findings: {len(auto_findings)}")
        print(f"verdict now: {state.verdict.value} ({len(state.entries)} active)")
        for f in auto_findings:
            print(f"  K5 [{f['trigger']}] {f['reason']}")
    return 1 if state.verdict is Verdict.KILLED else 0


def cmd_verify(args) -> int:
    """Actually exercise every path. §6.3: an untested kill switch does not exist.

    Runs against a throwaway repo root so a drill can never leave a real kill
    engaged — the previous shape of this idea (test in place, remember to clean
    up) fails exactly once and then the system is stopped for a reason nobody
    can find.
    """
    import shutil
    import tempfile

    real_root = paths.repo_root()
    tmp = Path(tempfile.mkdtemp(prefix="killswitch-verify-"))
    checks: list[dict] = []

    def record(path: str, ok: bool, detail: str) -> None:
        checks.append({"path": path, "ok": ok, "detail": detail})

    try:
        (tmp / "state").mkdir(parents=True, exist_ok=True)
        (tmp / "BUILD-SPEC.md").write_text("drill\n", encoding="utf-8")
        os.environ[paths.ROOT_ENV] = str(tmp)
        os.environ.pop("KILL_SWITCH", None)

        # Fresh clone must be UNKNOWN, and UNKNOWN must stop real work.
        st = killswitch.read_state()
        record("K0:fail-closed-on-fresh-clone",
               st.verdict is Verdict.UNKNOWN and not st.allows(2) and st.allows(4),
               f"verdict={st.verdict.value}, L2={st.allows(2)}, L4={st.allows(4)}")

        killswitch.touch_heartbeat(verified_by="drill", sources=["drill"])
        st = killswitch.read_state()
        record("K0:running-after-heartbeat", st.verdict is Verdict.RUNNING,
               f"verdict={st.verdict.value}")

        # K1: the repo file stops the system, and releasing clears it.
        killswitch.engage("global", reason="drill K1", engaged_by="drill", source="K1")
        st = killswitch.read_state()
        k1_killed = st.killed and not st.allows(2)
        killswitch.release("global", released_by="drill")
        k1_cleared = killswitch.read_state().verdict is Verdict.RUNNING
        record("K1:state/KILL", k1_killed and k1_cleared,
               f"engaged->killed={k1_killed}, released->clear={k1_cleared}")

        # K2: the environment variable stops the system on its own.
        os.environ["KILL_SWITCH"] = "global"
        k2_killed = killswitch.read_state().killed
        os.environ["KILL_SWITCH"] = "agent:lifecycle-growth"
        scoped_hit = killswitch.check(agent="lifecycle-growth").killed
        scoped_miss = not killswitch.check(agent="config-engineer").killed
        os.environ.pop("KILL_SWITCH", None)
        k2_cleared = killswitch.read_state().verdict is Verdict.RUNNING
        record("K2:env/KILL_SWITCH", k2_killed and scoped_hit and scoped_miss and k2_cleared,
               f"global={k2_killed}, scoped_hit={scoped_hit}, "
               f"scoped_miss_unaffected={scoped_miss}, cleared={k2_cleared}")

        # K3: a Control Room status reconciles into K1, and an unknown status
        # fails closed rather than being read as a clearance.
        killswitch.reconcile(external=read_k3("Engaged", "drill K3"),
                            sources=["K3:drill"], verified_by="drill",
                            prune_sources=["K3", "K5"])
        k3_killed = killswitch.read_state().killed
        killswitch.reconcile(external=read_k3("Clear", None), sources=["K3:drill"],
                            verified_by="drill", prune_sources=["K3", "K5"])
        k3_cleared = killswitch.read_state().verdict is Verdict.RUNNING
        killswitch.reconcile(external=read_k3("banana", None), sources=["K3:drill"],
                            verified_by="drill", prune_sources=["K3", "K5"])
        k3_ambiguous_stops = killswitch.read_state().killed
        killswitch.reconcile(external=[], sources=["K3:drill"], verified_by="drill",
                            prune_sources=["K3", "K5"])
        record("K3:moxt/control-room",
               k3_killed and k3_cleared and k3_ambiguous_stops,
               f"engaged={k3_killed}, cleared={k3_cleared}, "
               f"unknown_status_fails_closed={k3_ambiguous_stops}")

        # K4: this CLI's own engage/release, scoped to a capability.
        killswitch.engage("capability", target="cfg.publish.*", reason="drill K4",
                          engaged_by="drill", source="K4")
        hit = killswitch.check(capability="cfg.publish.canary").killed
        miss = not killswitch.check(capability="doc.write").killed
        killswitch.release("capability", target="cfg.publish.*", released_by="drill")
        cleared = killswitch.read_state().verdict is Verdict.RUNNING
        record("K4:cli", hit and miss and cleared,
               f"glob_hit={hit}, unrelated_unaffected={miss}, cleared={cleared}")

        # K5: an automatic finding reconciles in and stops the system.
        synthetic = [KillEntry(scope=Scope.BUDGET.value, target=None,
                               reason="drill K5 synthetic cost spike",
                               engaged_at=clock.iso(), engaged_by="orchestrator:drill",
                               source="K5")]
        killswitch.reconcile(external=synthetic, sources=["K5:drill"],
                            verified_by="drill", prune_sources=["K3", "K5"])
        k5_killed = killswitch.read_state().killed
        killswitch.reconcile(external=[], sources=["K5:drill"], verified_by="drill",
                            prune_sources=["K3", "K5"])
        k5_cleared = killswitch.read_state().verdict is Verdict.RUNNING
        record("K5:auto", k5_killed and k5_cleared,
               f"engaged={k5_killed}, cleared={k5_cleared}")
        # The evaluator itself must run without exploding on an empty repo.
        try:
            findings = evaluate_auto()
            record("K5:evaluator-runs", True, f"{len(findings)} finding(s) on empty repo")
        except Exception as exc:
            record("K5:evaluator-runs", False, f"{type(exc).__name__}: {exc}")

        # Corrupt K1 must read as a global kill, not as an absence of one.
        paths.kill_file().write_text("{ this is not json", encoding="utf-8")
        corrupt = killswitch.read_state()
        record("K1:corrupt-file-fails-closed",
               corrupt.killed and not corrupt.allows(2),
               f"verdict={corrupt.verdict.value}")
        paths.kill_file().unlink(missing_ok=True)

        # A stale verdict must decay to UNKNOWN rather than staying RUNNING.
        beat = tmp / "state" / "KILL.heartbeat.json"
        beat.write_text(json.dumps({"verified_at": "2020-01-01T00:00:00.000Z",
                                    "verified_by": "drill", "sources": ["drill"]}),
                        encoding="utf-8")
        stale = killswitch.read_state()
        record("K0:stale-verdict-decays-to-unknown",
               stale.verdict is Verdict.UNKNOWN and not stale.allows(2),
               f"verdict={stale.verdict.value}, freshness="
               f"{int(stale.freshness_seconds or 0)}s > {killswitch.FRESHNESS_LIMIT_SECONDS}s")
    finally:
        os.environ[paths.ROOT_ENV] = str(real_root)
        shutil.rmtree(tmp, ignore_errors=True)

    passed = sum(1 for c in checks if c["ok"])
    failed = [c for c in checks if not c["ok"]]
    report = {"checked_at": clock.iso(), "total": len(checks), "passed": passed,
              "failed": len(failed), "ok": not failed, "checks": checks}

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for c in checks:
            print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['path']}\n        {c['detail']}")
        print(f"\n{passed}/{len(checks)} checks passed")
        if failed:
            print("\nAn untested kill switch does not exist (§6.3). Fix before shipping:")
            for c in failed:
                print(f"  - {c['path']}: {c['detail']}")
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="killswitch.py", description="Kill switch driver (BUILD-SPEC §6.3)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="read the current verdict")
    p.add_argument("--agent")
    p.add_argument("--capability")
    p.add_argument("--workstream")
    p.add_argument("--autonomy", type=int, default=2,
                   help="autonomy level of the intended operation (default 2)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("engage", help="engage a kill (K4)")
    p.add_argument("scope", choices=[s.value for s in Scope])
    p.add_argument("--target", help="agent id, capability glob, or workstream")
    p.add_argument("--reason", required=True)
    p.add_argument("--by", default=os.environ.get("USER", "owner"))
    p.add_argument("--ttl", type=int, help="auto-expire after N minutes")
    p.set_defaults(func=cmd_engage)

    p = sub.add_parser("release", help="release a kill (always a human decision)")
    p.add_argument("scope", choices=[s.value for s in Scope])
    p.add_argument("--target")
    p.add_argument("--by", default=os.environ.get("USER", "owner"))
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("reconcile", help="fold K2/K3/K5 into K1 (heartbeat workflow)")
    p.add_argument("--k3-status", help="Moxt Control Room kill-switch task status")
    p.add_argument("--k3-reason")
    p.add_argument("--skip-auto", action="store_true", help="skip K5 evaluation")
    p.add_argument("--by", default="workflow:heartbeat")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("auto", help="evaluate K5 triggers read-only")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_auto)

    p = sub.add_parser("verify", help="drill all five paths (nightly CI)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"killswitch: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("state could not be established — failing closed (§6.3)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
