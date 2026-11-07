---
name: fsp-warm-start
description: Executes the mandatory Marzneshin-Agent-OS Session Start Protocol (FSP) using Static-First KV-Cache ordering so CLAUDE.md and BUILD-SPEC.md hit the prompt cache in under 1 second. Use at the beginning of every session.
---

# FSP Warm-Start Protocol (Prefix-Cache Optimized)

Follow these exact steps in order to initialize the session with maximum KV-cache hit rate and zero side-effects:

## 1. Refresh Deterministic Context Pack
Run:
```bash
python3 scripts/context_pack.py
```
This stratifies Tiers 0–2 (static prefix) above the breakpoint marker `<!-- MARZNESHIN_KV_CACHE_BREAKPOINT_V1 -->` and Tier 3 (dynamic state) below it.

## 2. Load Static Prefix First (Cache Hit Path)
Read `CLAUDE.md` and `BUILD-SPEC.md` (§0, §16, §17), followed by the static top section of `CONTEXT-PACK.md`.
> **CRITICAL**: Do NOT read volatile files (`state/STATE.json`, `state/HANDOFF.md`) before these static files.

## 3. Execute Fail-Closed Session & Kill-Switch Checks
Run the mandatory FSP commands:
```bash
python3 scripts/fsp.py status
python3 scripts/killswitch.py status
python3 scripts/health.py --skip-sim
```

## 4. Load Dynamic Tail Last
Read the bottom section of `CONTEXT-PACK.md` (or `state/STATE.json` and `state/HANDOFF.md` "Next session — start here").

## 5. Output 5-Line Owner Summary
Print strictly the 5-line status summary defined in `ONBOARDING.md`:
1. Active Phase / Slice
2. Last Receipt ID
3. Health metrics
4. Selected next task
5. Open blockers

