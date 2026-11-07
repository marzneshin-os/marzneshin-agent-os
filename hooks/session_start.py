#!/usr/bin/env python3
"""SessionStart hook (BUILD-SPEC §7.2, class A <3s).

Fails (exit != 0) when:
  - STATE.json exists but is corrupt (fail closed — never act on guessed state)
  - STATE.json is older than 24h AND a local re-compact cannot refresh it
  - the kill switch is KILLED at global scope (a stopped system stays stopped)

Warns (exit 0 with context) when:
  - the repo has never been bootstrapped (guidance, not a failure)
  - the kill switch verdict is UNKNOWN: only L3/L4 (read / internal-artifact)
    work is permitted until the heartbeat workflow reconciles (§6.3)
"""

from __future__ import annotations

import json
from pathlib import Path

import _common as H  # noqa: F401 — sets sys.path and MARZNESHIN_OPS_ROOT
from lib import killswitch, state, agentmemory


def main() -> None:
    data = H.read_stdin()

    # --- STATE plane -------------------------------------------------------
    stale = False
    try:
        s = state.read()
        stale = state.is_stale()
    except state.StateError as exc:
        if "does not exist" in str(exc):
            H.emit("session.started", "session", H.session_id(),
                   {"bootstrap_needed": True})
            H.allow("marzneshin-ops: fresh clone — STATE.json is absent. Run "
                    "`python3 scripts/fsp.py bootstrap` then "
                    "`python3 scripts/fsp.py claim <workstream> --agent <id>`.")
        H.fail_closed(f"STATE.json unreadable: {exc}")

    if stale:
        # A stale snapshot is recoverable locally: compaction is deterministic
        # and network-free. Only if THAT fails does the session halt.
        import subprocess, sys
        fix = subprocess.run(
            [sys.executable, str(Path(H.REPO_ROOT) / "scripts" / "compact.py")],
            capture_output=True, text=True, timeout=30)
        if fix.returncode != 0 or state.is_stale():
            H.fail_closed("STATE.json is older than 24h and re-compaction did not "
                          f"refresh it: {fix.stdout[-300:]}")

    # --- kill switch ---------------------------------------------------------
    ks = killswitch.read_state()
    if ks.verdict is killswitch.Verdict.KILLED:
        global_kill = any(e.scope in ("global", "budget") for e in ks.entries)
        if global_kill:
            H.block("kill switch is ENGAGED: " + "; ".join(e.reason for e in ks.entries),
                    event_type="killswitch.unknown", subject_kind="killswitch",
                    subject_id="global")
        scope_note = "; ".join(f"{e.scope}:{e.target}" for e in ks.entries)
        context = (f"marzneshin-ops: scoped kill(s) active [{scope_note}]. "
                   f"Check `scripts/killswitch.py status` before acting in those scopes.")
    elif ks.verdict is killswitch.Verdict.UNKNOWN:
        context = ("marzneshin-ops: kill-switch verdict UNKNOWN (fail-closed). Only "
                   "read/internal work (L3/L4) is permitted until the heartbeat "
                   "workflow reconciles. Run `scripts/killswitch.py status` for detail.")
    else:
        context = None

    # Fetch context from AgentMemory
    workstream = data.get("workstream")
    if workstream:
        mem_resp = agentmemory.call_mcp_tool("memory_smart_search", {"query": workstream, "limit": 10})
        if mem_resp and not mem_resp.startswith("AgentMemory error"):
            am_ctx = f"\n\n[AgentMemory Context for {workstream}]\n{mem_resp}"
            context = (context + am_ctx) if context else am_ctx

    # --- Relevance AI health check (auto-rotate on failure) ----------------
    try:
        from lib import relevance_health as _rai
        _rai_status = _rai.quick_check()
        if _rai_status == _rai.DEAD:
            _rot = _rai.auto_rotate()
            if _rot["success"]:
                _rai_ctx = (f"\n🔄 Relevance AI: auto-rotated to "
                            f"'{_rot['new_account']}'. .env updated.")
            elif _rot.get("all_dead"):
                _rai_ctx = ("\n❌ Relevance AI: ALL accounts exhausted. "
                            "Run: python3 scripts/relevance_manager.py add-account")
            else:
                _rai_ctx = (f"\n❌ Relevance AI: rotation failed — "
                            f"{_rot.get('error', 'unknown')}")
            context = (context + _rai_ctx) if context else _rai_ctx
        elif _rai_status == _rai.LOW_CREDITS:
            _rai_ctx = ("\n⚠️ Relevance AI: credits running low "
                        "on active account.")
            context = (context + _rai_ctx) if context else _rai_ctx
    except Exception:
        pass  # Never let Relevance AI check break session start

    # If resuming from compaction (Idle Compaction or /compact), inject state
    source = data.get("source", "startup")
    if source == "compact":
        from lib import leases as _leases
        sid = data.get("session_id") or H.session_id()
        cp_file = Path(H.REPO_ROOT) / "state" / "checkpoints" / f"claude_compact_{sid}.json"
        cp_data = {}
        if cp_file.exists():
            try:
                cp_data = json.loads(cp_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        active_leases_info = ""
        leases_list = cp_data.get("active_leases") or [l.to_dict() for l in _leases.list_all() if not l.expired()]
        if leases_list:
            lease_lines = [f"  - Workstream: {l.get('workstream')} | Holder: {l.get('holder')} | Token: {l.get('fencing_token')}" for l in leases_list]
            active_leases_info = "\n" + "\n".join(lease_lines)
        else:
            active_leases_info = " None"

        compact_restore_ctx = (
            f"\n🔄 [Marzneshin State Restored Post-Compaction]\n"
            f"- Active Slice: {s.get('active_slice', 'Unknown')} (Sense: {s.get('sense_level', 'Tick-A')})\n"
            f"- Active Leases:{active_leases_info}\n"
            f"- Open Tasks: {len(s.get('open_tasks', []))}\n"
            f"- Invariants Reminder: I3 (Task Receipt), I6 (No Raw Secrets), I7 (Reversible/Rollback), "
            f"I11 (Sim Green), I12 (Fail-Closed), I15 (Receipt Chain), I17 (Single Writer).\n"
            f"- Verify status anytime: `python3 scripts/verify.py --all`"
        )
        context = (context + compact_restore_ctx) if context else compact_restore_ctx

    H.emit("session.started", "session", H.session_id(),
           {"state_age_s": int(state.age_seconds()), "kill_switch": ks.verdict.value,
            "source": source})
    H.allow(context)


if __name__ == "__main__":
    main()
