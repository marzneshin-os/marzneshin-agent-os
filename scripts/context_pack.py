#!/usr/bin/env python3
"""scripts/context_pack.py (Prefix-Cache Optimized Upgrade)
Rebuilds CONTEXT-PACK.md using Static-First, Dynamic-Tail ordering.
Preserves fail-closed verification, backward compatibility, and zero side-effects on STATE.json (I1).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lib import atomic, killswitch, paths, receipts, state
from lib.prefix_cache import (
    CACHE_BREAKPOINT_MARKER,
    PrefixEnvelope,
    canonical_json,
    strip_volatile_fields,
)

SLICES = {
    "VS-1": "Spine — repo, hooks, state plane, receipt chain, core CI",
    "VS-2": "Simulation Harness — sim/, virtual clock, fakes, chaos",
    "VS-3": "A2A over T1/T2 — envelope, dispatcher, registry, minimal policy",
    "VS-4": "Continuity + Kill Switch — succession, reaper, dead-man, escrow",
    "VS-5": "Tier 0 Agents — 7 agent cards, budget, heartbeat, two-key",
    "VS-6": "Control Room — Moxt Workflow mirror + approval path",
    "VS-7": "Config Pipeline — statistical canary, probe fleet, auto-rollback",
    "VS-8": "Growth Spine — event taxonomy, schemas, funnel, first journey",
    "VS-9": "Experiment Loop — guardrails, SRM, readouts",
    "VS-10": "Revenue Command Center — dashboards, unit economics",
    "VS-11": "Autonomy Ratchet + Shadow Mode",
    "VS-12": "(optional) HTTP Gateway — latency cache only",
}


def _read_safe(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return default


def build_context_pack(repo_root: Path | None = None) -> PrefixEnvelope:
    root = repo_root or paths.repo_root()

    # 1. Tier 0: Immutable Governance & Standing Invariants (Never changes within a slice)
    claude_md = _read_safe(root / "CLAUDE.md", "# CLAUDE.md missing")
    tradeoffs = _read_safe(root / "decisions" / "TRADEOFF-REGISTER.md", "")
    session_protocol = (
        "## The session protocol (BUILD-SPEC §0)\n\n"
        "1. SYNC — `scripts/fsp.py status` + HANDOFF.md + recent receipts + kill switch\n"
        "2. GAP SCAN — distance to the current slice's Definition of Done (§17)\n"
        "3. CLAIM — `scripts/fsp.py claim <workstream> --agent <id>` (TTL 90m)\n"
        "4. PLAN — at most 7 steps, each with a named artifact\n"
        "5. SIM — run the related sim/ scenario first; red means no production\n"
        "6. EXECUTE — real code, never placeholders\n"
        "7. VERIFY — run tests, report real output\n"
        "8. EMIT — event + receipt (with prev_receipt_hash) + atomic commit\n"
        "9. HANDOFF — rewrite HANDOFF.md, release the lease\n\n"
        "## Iron rules\n\n"
        "1. No config reaches users without QA.  2. No campaign without hypothesis and stop condition.  "
        "3. No session ends without a HANDOFF.  4. No secret enters the repo.  "
        "5. No decision without owner, evidence and rollback.  "
        "6. \"I don't know\" equals \"stop\" — an unreadable safety control is engaged, not clear."
    )
    tier0 = (
        f"# [TIER-0: IMMUTABLE OS GOVERNANCE]\n\n"
        f"{claude_md}\n\n"
        f"{session_protocol}\n\n"
        f"## Tradeoff Register\n{tradeoffs}"
    )

    # 2. Tier 1: Agent Registry & Skill Discovery Metadata (Sorted deterministically)
    cards_dir = root / "agents" / "cards"
    card_summaries = []
    if cards_dir.exists():
        for card_file in sorted(cards_dir.glob("*.json")):
            try:
                raw_card = json.loads(card_file.read_text(encoding="utf-8"))
                static_card, _ = strip_volatile_fields(raw_card)
                card_summaries.append(f"- `{card_file.name}`: {canonical_json(static_card)}")
            except Exception:
                continue
    tier1 = "# [TIER-1: AGENT CARDS & CAPABILITIES]\n" + "\n".join(card_summaries)

    # 3. Tier 2: Semi-Static Architectural Decisions (Sorted ADR list)
    adr_dir = root / "decisions" / "ADR"
    adr_list = []
    if adr_dir.exists():
        for adr_file in sorted(adr_dir.glob("*.md")):
            first_line = _read_safe(adr_file).splitlines()[0] if _read_safe(adr_file) else adr_file.name
            adr_list.append(f"- `{adr_file.name}`: {first_line}")
    tier2 = "# [TIER-2: APPROVED ADRs]\n" + "\n".join(adr_list)

    # 4. Tier 3: Dynamic Execution Tail (Evaluated fresh; placed strictly after breakpoint!)
    state_path = root / "state" / "STATE.json"
    handoff_path = root / "state" / "HANDOFF.md"
    kill_path = root / "state" / "KILL"

    try:
        ks = killswitch.read_state()
        kill_status = f"**{ks.verdict.value}** ({ks.detail})"
    except Exception:
        kill_status = "ENGAGED (FAIL-CLOSED STOP)" if kill_path.exists() else "CLEAR"

    try:
        s = state.read()
        snapshot = state.summarize(s)
    except Exception:
        s = None
        snapshot = "(STATE.json unavailable)"

    try:
        rstats = receipts.stats()
        receipt_summary = f"{rstats['total']} receipts · crash_rate {rstats['crash_rate']:.2%} (budget 2%)"
    except Exception:
        receipt_summary = "receipt stats unavailable"

    state_raw = _read_safe(state_path, "{}")
    handoff_raw = _read_safe(handoff_path, "# HANDOFF.md not found")

    heads = []
    chain_dir = root / "receipts" / "_chain"
    if chain_dir.exists():
        try:
            from lib.atomic import read_json
            for f in sorted(chain_dir.glob("*.head.json")):
                h = read_json(f, default={}) or {}
                heads.append(f"  - {f.name[:-10]}: {h.get('count', 0)} receipts, head `{str(h.get('hash'))[:18]}…`")
        except Exception:
            pass
    head_lines = "\n".join(heads) or "  (no receipts yet)"

    slice_now = (s or {}).get("active_slice", "VS-1")

    tier3 = (
        f"# [TIER-3: DYNAMIC SESSION TAIL — DO NOT CACHE]\n"
        f"## Safety & Live Controls\n"
        f"- Kill switch: {kill_status}\n"
        f"- Receipt chain: {receipt_summary}\n"
        f"- Active slice: **{slice_now}** — {SLICES.get(slice_now, '?')}\n\n"
        f"## State Snapshot\n```\n{snapshot}\n```\n\n"
        f"## Receipt chains\n{head_lines}\n\n"
        f"- **Active State Snapshot (`state/STATE.json`)**:\n```json\n{state_raw}\n```\n\n"
        f"## Active Handoff (`state/HANDOFF.md`)\n{handoff_raw}"
    )

    return PrefixEnvelope(
        tier0_os_kernel=tier0,
        tier1_agent_persona=tier1,
        tier2_session_snapshot=tier2,
        tier3_dynamic_tail=tier3,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="context_pack.py")
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args(argv)

    envelope = build_context_pack()
    text = envelope.render_markdown()

    if args.stdout:
        print(text)
    else:
        out_file = paths.context_pack_file()
        atomic.write_text_atomic(out_file, text)
        print(f"[OK] wrote {paths.rel(out_file)} ({len(text)} bytes) | static_prefix_sha256={envelope.prefix_sha256[:12]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"context_pack: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
