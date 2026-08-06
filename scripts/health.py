#!/usr/bin/env python3
"""health.py — the token-frugal baseline gate for a fresh session.

Step 4 of ONBOARDING.md ("verify baseline green") normally means running four
tools and reading thousands of lines of log. In a multi-session project where
every session is bounded by an agent's token budget, that log *is* the cost:
the numbers matter, the transcript does not.

This wrapper runs the same gates and prints a fixed, tiny summary instead --
one line per gate, plus a verdict. Child stdout is captured and parsed here, so
it never reaches the caller's context. Details are opt-in via --verbose.

    health.py                     tests + verify + sim, ~6 lines out
    health.py --skip-sim          fast loop while iterating on code
    health.py --seeds 11          single seed (sim is the slow gate)
    health.py --coldrestore       also run the §11.2 drill -- NOT read-only
    health.py --verbose           add failure detail lines (still bounded)
    health.py --json              machine-readable, for CI or a receipt
    health.py --save-baseline     record today's green numbers as the floor

--save-baseline never narrows the floor (ADR-009 D46): if the existing
baseline tracks a gate this run did not execute (e.g. coldrestore), the save
is refused with exit 1 and the old floor stays byte-identical. Run the
missing gate so the save covers the whole floor, or delete
state/HEALTH-BASELINE.json to reset the floor deliberately.

The three default gates are read-only: verified to leave `git status` clean, so
a fresh session can run them before claiming a lease. `--coldrestore` is opt-in
precisely because the drill emits prod events and regenerates STATE.json --
run it only after you hold the lease, and expect state/ to change.

Regression detection: counts are compared against state/HEALTH-BASELINE.json
(written by --save-baseline). Fewer passing tests or scenarios than the floor
is a REGRESSION even when every gate is individually green -- that is the
failure mode a plain "all green" readout hides after a handoff.

Exit codes: 0 = green, 1 = a gate failed or regressed, 2 = a gate could not
run at all (fail closed, same convention as verify.py).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Every other script resolves the root through lib/paths.py, where
# MARZNESHIN_OPS_ROOT wins (sim roots and the CLI test harness redirect all
# I/O through it). health.py stays dependency-free but honours the same
# override -- hardcoding the root here made the gate untestable and was the
# one place the convention documented in lib/paths.py did not reach.
REPO = Path(os.environ.get("MARZNESHIN_OPS_ROOT")
            or Path(__file__).resolve().parent.parent).resolve()
BASELINE = REPO / "state" / "HEALTH-BASELINE.json"
MAX_DETAIL = 8  # a bounded failure list: enough to act on, never a wall of log


def _run(args: list[str], timeout: int) -> tuple[int, str, str]:
    """Run a gate to completion, capturing everything. Never inherits stdout."""
    try:
        proc = subprocess.run([sys.executable, *args], cwd=REPO, timeout=timeout,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 2, "", f"timeout after {timeout}s"
    except Exception as exc:  # a gate that cannot start is a red gate
        return 2, "", f"{type(exc).__name__}: {exc}"


# --- gates -----------------------------------------------------------------

def gate_tests(timeout: int) -> dict:
    """unittest writes its summary to stderr; we only keep the counts."""
    code, out, err = _run(["-m", "unittest", "discover", "-s", "tests", "-q"], timeout)
    blob = f"{out}\n{err}"
    ran = re.search(r"^Ran (\d+) tests?", blob, re.M)
    total = int(ran.group(1)) if ran else 0
    failed = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", blob))
    detail = [ln.strip() for ln in blob.splitlines()
              if ln.startswith(("FAIL:", "ERROR:"))][:MAX_DETAIL]
    return {"gate": "tests", "ok": code == 0 and total > 0,
            "passed": max(total - failed, 0), "total": total, "detail": detail}


def gate_verify(timeout: int) -> dict:
    code, out, err = _run(["scripts/verify.py", "--all", "--json"], timeout)
    try:
        data = json.loads(out)
    except Exception:
        return {"gate": "verify", "ok": False, "passed": 0, "total": 0,
                "detail": [(err or out or "no output").strip()[:200]], "broken": True}
    results = data.get("results", [])
    bad = [r for r in results if not r.get("ok")]
    detail = []
    for r in bad:
        problems = list(r.get("problems", []))
        chain = r.get("report", {}).get("workstreams", {})
        for ws in chain.values():
            problems.extend(ws.get("problems", []))
        detail.append(f"{r['check']}: {problems[0] if problems else 'failed'}")
    return {"gate": "verify", "ok": bool(data.get("ok")) and code == 0,
            "passed": len(results) - len(bad), "total": len(results),
            "detail": detail[:MAX_DETAIL]}


def gate_sim(seeds: str, timeout: int) -> dict:
    """The slow gate. Its --json payload is large, so it dies in this pipe."""
    code, out, err = _run(["scripts/sim.py", "run", "--all", "--seeds", seeds,
                           "--json"], timeout)
    try:
        data = json.loads(out)
    except Exception:
        return {"gate": "sim", "ok": False, "passed": 0, "total": 0,
                "detail": [(err or out or "no output").strip()[:200]], "broken": True}
    reports = data.get("reports", [])
    bad = [r for r in reports if r.get("result") != "pass"]
    detail = []
    for r in bad:
        red = [n for n, ok in (r.get("checks") or {}).items() if not ok]
        why = r.get("error") or (", ".join(red[:3]) if red else "failed")
        detail.append(f"{r.get('scenario')} seed={r.get('seed')}: {why}")
    return {"gate": "sim", "ok": bool(data.get("ok")) and code == 0,
            "passed": len(reports) - len(bad), "total": len(reports),
            "detail": detail[:MAX_DETAIL]}


def gate_coldrestore(timeout: int) -> dict:
    """§11.2 drill. Runs against a throwaway mirror, so it is safe on any clone."""
    code, out, err = _run(["scripts/coldrestore.py", "run", "--json"], timeout)
    score = None
    try:
        data = json.loads(out)
        score = data.get("score")
    except Exception:
        m = re.search(r"score[\"':\s]+([0-9.]+)", f"{out}\n{err}", re.I)
        score = float(m.group(1)) if m else None
    return {"gate": "coldrestore", "ok": code == 0,
            "passed": 1 if code == 0 else 0, "total": 1, "score": score,
            "detail": [] if code == 0 else [(err or out).strip()[:200]]}


# --- baseline ---------------------------------------------------------------

class BaselineCoverageError(RuntimeError):
    """--save-baseline would narrow the floor (ADR-009 D46)."""


def missing_baseline_gates(executed: list[str], baseline: dict) -> list[str]:
    """Gates the existing floor tracks that this run did not execute.

    Saving over them would erase knowledge the project decided to keep (the
    coldrestore entry vanished exactly this way), so any non-empty result
    must refuse the save. A run covering a *superset* of the tracked gates
    returns [] and may save: adding a gate to the floor is always allowed.
    """
    tracked = set((baseline.get("gates") or {}).keys())
    return sorted(tracked - set(executed))


def load_baseline() -> dict:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def find_regressions(gates: list[dict], baseline: dict) -> list[str]:
    """A green gate with fewer passing items than the floor is still a red run."""
    out = []
    for g in gates:
        floor = (baseline.get("gates") or {}).get(g["gate"], {}).get("passed")
        if isinstance(floor, int) and g["passed"] < floor:
            out.append(f"{g['gate']}: {g['passed']} < baseline {floor}")
    return out


def save_baseline(gates: list[dict], state_slice: str | None) -> None:
    # Fail-closed backstop (D46): main() pre-checks for a clean message, but
    # no caller of this function may ever narrow the floor by accident.
    missing = missing_baseline_gates([g["gate"] for g in gates], load_baseline())
    if missing:
        raise BaselineCoverageError(
            "gate(s) tracked by the current floor were not executed in this "
            f"run: {', '.join(missing)}")
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": "Green floor for scripts/health.py. Regenerate with "
                "`health.py --save-baseline` only when the run is fully green.",
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "active_slice": state_slice,
        "gates": {g["gate"]: {"passed": g["passed"], "total": g["total"]} for g in gates},
    }
    BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def state_summary() -> dict:
    try:
        d = json.loads((REPO / "state" / "STATE.json").read_text(encoding="utf-8"))
    except Exception:
        return {}
    ws = d.get("workstreams") or {}
    last = next((v.get("last_receipt") for v in ws.values() if v.get("last_receipt")), None)
    return {"phase": d.get("phase"), "active_slice": d.get("active_slice"),
            "last_receipt": last}


# --- main ------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="health.py",
                                description="Token-frugal baseline gate (ONBOARDING step 4)")
    p.add_argument("--skip-sim", action="store_true", help="skip the slow sim gate")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--skip-verify", action="store_true")
    p.add_argument("--coldrestore", action="store_true",
                   help="also run the §11.2 drill (writes prod events; needs the lease)")
    p.add_argument("--seeds", default="11,27,43")
    p.add_argument("--timeout", type=int, default=900, help="per-gate seconds")
    p.add_argument("--verbose", action="store_true", help="print bounded failure detail")
    p.add_argument("--json", action="store_true")
    p.add_argument("--save-baseline", action="store_true",
                   help="record this run as the green floor (green runs only)")
    args = p.parse_args(argv)

    started = time.monotonic()
    gates: list[dict] = []
    if not args.skip_tests:
        gates.append(gate_tests(args.timeout))
    if not args.skip_verify:
        gates.append(gate_verify(args.timeout))
    if not args.skip_sim:
        gates.append(gate_sim(args.seeds, args.timeout))
    if args.coldrestore:
        gates.append(gate_coldrestore(args.timeout))

    baseline = load_baseline()
    regressions = find_regressions(gates, baseline)
    broken = any(g.get("broken") for g in gates)
    green = all(g["ok"] for g in gates) and not regressions
    st = state_summary()
    elapsed = round(time.monotonic() - started, 1)

    save_refused = False
    if args.save_baseline:
        missing = missing_baseline_gates([g["gate"] for g in gates], baseline)
        if not green:
            print("health: refusing to save a baseline from a non-green run",
                  file=sys.stderr)
        elif missing:
            print("health: refusing to save baseline: gate(s) tracked by the "
                  f"current floor were not executed in this run: {', '.join(missing)}. "
                  "Run them (e.g. --coldrestore) so the save covers the whole "
                  "floor, or delete state/HEALTH-BASELINE.json to reset the "
                  "floor deliberately (ADR-009 D46).",
                  file=sys.stderr)
            save_refused = True
        else:
            save_baseline(gates, st.get("active_slice"))

    if args.json:
        print(json.dumps({"ok": green, "elapsed_s": elapsed, "state": st,
                          "gates": gates, "regressions": regressions,
                          "baseline_save_refused": save_refused},
                         indent=2, ensure_ascii=False))
    else:
        for g in gates:
            mark = "PASS" if g["ok"] else "FAIL"
            extra = f" score={g['score']}" if g.get("score") is not None else ""
            print(f"[{mark}] {g['gate']:<12} {g['passed']}/{g['total']}{extra}")
            if args.verbose or not g["ok"]:
                for d in g["detail"]:
                    print(f"        - {d}")
        for r in regressions:
            print(f"[REGRESSION] {r}")
        print(f"health: {'GREEN' if green else 'RED'} | {st.get('phase', '?')} "
              f"{st.get('active_slice', '?')} | last receipt {st.get('last_receipt', '?')} "
              f"| {elapsed}s")
        if not green:
            print("health: fix this before new work (ONBOARDING step 4)")

    if broken:
        return 2
    if save_refused:
        return 1
    return 0 if green else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"health: cannot establish state: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        raise SystemExit(2)
