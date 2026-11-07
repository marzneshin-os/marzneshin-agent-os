---
name: project-conventions
description: Core architectural constraints, safety invariants, and coding standards for Marzneshin Agent OS. Apply automatically when writing or reviewing code.
user-invocable: false
---

# Project Conventions & Invariants — Marzneshin Agent OS

Apply these standards automatically whenever writing, editing, or evaluating code in this repository:

## 1. Core Architecture & SSoT (BUILD-SPEC v2.0)
- **GitHub is sole SSoT** (I1). `state/STATE.json` is derived from event log — never edit manually.
- **Nine-Stage FSP Protocol**: SYNC → GAP SCAN → CLAIM → PLAN → SIM → EXECUTE → VERIFY → EMIT → HANDOFF.
- **Fencing & Leases**: Workstream state mutations require valid claim and fencing token (`scripts/fsp.py claim`).

## 2. Coding Rules & Constraints
- **Python stdlib-only in `scripts/lib/` and `hooks/`**: No external packages allowed in lib/hooks layers (clean, portable, <3s runtime budget).
- **Virtual Clock**: NEVER call `datetime.now()` or `time.time()` directly. Always use `lib/clock.py` (`clock.now_iso()`, `clock.now_epoch()`). Checked by `scripts/verify.py --lint-clock`.
- **Zero Circular Imports**: Clean dependency tree in `scripts/lib/`. Checked by `scripts/verify.py --lint-imports`.
- **Fail-Closed Safety**: Kill switches (K1-K5), budget checks, and lease verifications fail closed. "Unknown" equals STOP.

## 3. Two-Key Verification & Receipts
- Every mutating task must emit exactly one valid receipt in `receipts/`.
- Hand edits to `receipts/`, `state/events/`, `state/locks/`, `state/budget/`, `state/a2a/` are strictly blocked.
- Mandatory gate check before PR or completion: `python3 scripts/verify.py --all`.

## 4. Budget & Cost Governance ("Count it, cap it, then scale it")
- Hard task stop: $2.00 max spend per task.
- Subagent turn limits: `maxTurns: 8` to `12`.
- Check `/cost` and session status line regularly.
