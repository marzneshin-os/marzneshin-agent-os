<div align="center">

# Marzneshin Autonomous OS

**A governance & operations framework for autonomous AI agents — everything fail-closed by design.**

[![validate](https://github.com/marzneshin-os/marzneshin-agent-os/actions/workflows/validate.yml/badge.svg)](https://github.com/marzneshin-os/marzneshin-agent-os/actions/workflows/validate.yml)
![tests](https://img.shields.io/badge/tests-169%20passing-brightgreen)
![verify](https://img.shields.io/badge/verify-6%2F6-brightgreen)
![sim](https://img.shields.io/badge/sim-33%20scenario%20runs-brightgreen)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-proprietary-lightgrey)

</div>

---

## Overview

Marzneshin Autonomous OS is an event-sourced control plane for running multi-agent work safely. Every action an agent takes is leased, logged, receipted, and reversible — and every safety control **fails closed**: an unreadable control is treated as engaged, never as clear.

The repository is the single source of truth. All machine state (`state/STATE.json`) is *derived* from an append-only event log and can be regenerated at any time.

## Key capabilities

- **🛑 Five-path kill switch** — `state/KILL` file, `KILL_SWITCH` env, Moxt control, CLI, and automatic triggers. Human disable only, always with an ADR.
- **🧾 Cryptographic receipt chain** — every task emits exactly one receipt, hash-linked to its predecessor (I15). Tampering breaks the chain; `verify.py --chain` proves integrity.
- **📜 Event-sourced state** — no hand-edited state; `compact.py` rebuilds `STATE.json` from the event log.
- **🔀 A2A envelope bus** — idempotent delivery (scoped TTL), transport-agnostic envelopes, hysteresis fallback: 3 consecutive T2 failures degrade traffic to T1, 5 consecutive health successes restore it (§5.5).
- **⏱️ Fencing-token leases** — one writer per path (I17), 90-minute TTL, zombie leases reaped automatically.
- **🧪 Sim-first delivery (I11)** — no code or config reaches production without green simulation evidence: chaos scenarios for node outage, payment-provider down, prompt injection, lease expiry, member removal, and more.
- **🗝️ Encrypted recovery escrow (§11.2)** — AES-256-CBC/PBKDF2 bundle with per-file SHA-256 manifest; drift is treated as failure, and no passphrase means *zero files written*.
- **🔄 Cold-restore drills** — a fresh-clone restore exercise scoring 1.0, runnable as a gate.

## Verified status

| Gate | Result |
|---|---|
| Unit tests | **169 / 169** |
| `verify --all` (schemas, chain, events, agent cards, lints) | **6 / 6** |
| Sim scenarios × seeds 11, 27, 43 | **33 / 33** |
| Cold-restore drill | **1 / 1** |
| Receipt chain | 20 receipts · `ok=true` |

Current phase: **P1 — agentic-core** · Active slice: **VS-4 (Continuity & Kill Switch)** · 11 ADRs · decisions through D51.

## Repository layout

```
├── agents/            # Agent registry (JSON) and agent cards
├── adapters/          # Adapter base + contracts
├── analytics/schemas/ # JSON Schemas: envelope, event, receipt, lease, state…
├── artifacts/sim/     # Simulation evidence (closeout reports)
├── decisions/         # ADRs (accepted decisions), GAP reports, tradeoff register
├── hooks/             # Lifecycle hooks (session_start, pre_commit, stop, …)
├── receipts/          # Append-only task receipts, hash-chained
├── scripts/           # CLI entry points (thin layers)
│   └── lib/           # All shared logic — Python stdlib only
├── sim/               # Chaos world, actors, fakes, scenarios (YAML)
├── state/             # Derived state, event log, locks, kill switch
└── tests/             # unittest suite (stdlib, no network)
```

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml jsonschema        # strict validation only; runtime is stdlib-only

# Start AgentMemory in a separate terminal to enable project-scoped persistent memory
XDG_DATA_HOME=$PWD/state npx -y @agentmemory/agentmemory

python3 scripts/health.py            # tests + verify + sim, ~4 lines of output
```

Exit codes: `0` green · `1` failure or regression against `state/HEALTH-BASELINE.json` · `2` gate could not run (fail-closed).

## Working on this repo

Every session follows the nine-step FSP protocol (BUILD-SPEC §0):

`SYNC → GAP SCAN → CLAIM → PLAN → SIM → EXECUTE → VERIFY → EMIT → HANDOFF`

New session? **Read [`ONBOARDING.md`](ONBOARDING.md) first** — it is the complete cold-start protocol. The iron rules:

1. No config reaches users without QA.
2. No campaign without a hypothesis and a stop condition.
3. No session ends without a HANDOFF.
4. No secret enters the repo — not in code, events, receipts, or logs.
5. No decision without an owner, evidence, and a rollback.
6. "I don't know" equals "stop" — an unreadable safety control is engaged, not clear.

## Documentation

| Document | Purpose |
|---|---|
| [`ONBOARDING.md`](ONBOARDING.md) | Cold-start protocol — read first |
| [`BUILD-SPEC.md`](BUILD-SPEC.md) | Governing spec (§0 session protocol · §16 scenarios · §17 DoD) |
| [`CLAUDE.md`](CLAUDE.md) | Standing invariants (I1…I17) and daily commands |
| [`RECOVERY.md`](RECOVERY.md) | Disaster recovery & escrow bundle usage |
| [`decisions/ADR/`](decisions/ADR/) | Architecture Decision Records (accepted, not up for debate) |
| [`state/HANDOFF.md`](state/HANDOFF.md) | Last session state + exact next step |
| [`CONTEXT-PACK.md`](CONTEXT-PACK.md) | Compressed session snapshot (machine-generated) |

---

## فارسی

**سیستم‌عامل خودگردان مرزنشین** — چارچوب حاکمیت و عملیات برای عامل‌های هوش مصنوعی: kill switch پنج‌مسیرهٔ fail-closed، زنجیرهٔ رسید رمزنگاری‌شده، state رویدادمحور، گذرگاه A2A با idempotency و fallback هیسترزیس، و تحویل sim-first. راهنمای کامل شروع در [`ONBOARDING.md`](ONBOARDING.md) (فارسی) است.

---

<div align="center">
<sub>Private repository · All rights reserved · Receipts don't lie.</sub>
</div>
