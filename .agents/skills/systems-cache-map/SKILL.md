---
name: systems-cache-map
description: Applies the comprehensive Systems Thinking Map to any new feature, agent card, or slice in Marzneshin-Agent-OS, ensuring Sim-First delivery (I11), KV-cache prefix alignment, and human-readable documentation.
---

# Systems Thinking Map Execution Workflow

When planning or implementing any task in `marzneshin-agent-os`, execute this 4-stage pipeline:

## Stage 1 — Architectural Synthesis (/deep-research-pro mental model)
Classify every new file or schema change into:
- **Tier 0**: OS Kernel (`CLAUDE.md`, `BUILD-SPEC.md`, `analytics/schemas/`)
- **Tier 1**: Agent Persona & Skill Index (`agents/cards/`, `.agents/skills/`)
- **Tier 2**: ADRs & Snapshots (`decisions/ADR/`, `GAP-REPORT-*`)
- **Tier 3**: Dynamic Event & State Tail (`state/events/`, `state/STATE.json`, `state/KILL`)

> **RULE**: Never place dynamic fields or volatile timestamps into Tiers 0–2.

## Stage 2 — Sim-First Gate (Invariant I11)
Write or update the failing simulation scenario in `sim/` and unit test in `tests/` first. Run:
```bash
python3 scripts/health.py --seeds 11
```
Verify the gate turns green after minimal code implementation.

## Stage 3 — Receipt & State Compaction (Invariants I1, I3, I15)
Generate the task receipt, run:
```bash
python3 scripts/verify.py --chain
```
and rebuild `state/STATE.json` from `state/events/` using:
```bash
python3 scripts/compact.py
```

## Stage 4 — Human Handoff Polish (/humanizer mental model)
Rewrite `state/HANDOFF.md` and any updates to `RECOVERY.md` or `ADR` files in clear, natural, high-precision prose free of robotic boilerplate, then refresh:
```bash
python3 scripts/context_pack.py
```

