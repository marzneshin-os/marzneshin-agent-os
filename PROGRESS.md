# PROGRESS.md — Marzneshin Agent OS Operational Milestones

## Current Operational State
- **Active Phase:** P1-agentic-core
- **Active Slice:** VS-12 (Post-Milestone Autonomous Operational Protocol)
- **Latest Receipt:** T-0030 (`receipts/2026/11/T-0030.json`)
- **Baseline Health:**
  - Unit tests: 471 / 471 PASS (`python3 -m unittest discover -s tests`)
  - Verification gates: 6 / 6 PASS (`python3 scripts/verify.py --all`)
  - Simulation scenarios: 51 / 51 PASS (`python3 scripts/sim.py run --all`)
  - Core services: 13 / 13 UP & healthy (`python3 scripts/dev.py status`)
  - Killswitch: Inactive (`global=False`)

---

## Milestone Execution History

### [T-0030] Telemetry Sanitization, Worktree Pruning, MCP Protection & Workflow Resilience (2026-11-09)
- **Task ID:** `T-0030`
- **Agent:** `orchestrator`
- **Scope & Objectives:**
  1. **Telemetry & Artifact Sanitization:** Purged 1,191 untracked hook telemetry files (`batch-pretooluse-*`, `batch-posttooluse-*`, `session_*`, 64-char hex cache blobs) from `.mimosa/` and 2 plan files from `.zcode/`. Hardened `.gitignore` to prevent any telemetry leakage into version control.
  2. **Worktree Hygiene:** Verified commit `e194848d` was already merged into `origin/main`; cleanly removed and pruned the detached `abstracted-yew` Git worktree.
  3. **Hermetic MCP Configuration:** Cleaned `.mcp.json` of local host paths (`C:\Ubuntu\...` and `wsl.exe -d Ubuntu`), restoring portable relative python entrypoints (`scripts/mcp_agentrouter.py`, `scripts/mcp_tavily.py`).
  4. **Compact Workflow Self-Healing:** Identified recurring sequence gaps in scheduled `compact.yml` caused by `file_pattern` omitting new event files in `state/events/`. Aligned pattern with `heartbeat.yml` (`file_pattern: "state/"`) and enhanced `scripts/verify.py` with gap formatting.
  5. **Verification & Pipeline Health:** Validated via 1,874 Vitest tests, 471 unit tests, 6/6 verification gates, 51/51 sim scenarios, and verified live green GitHub Actions runs for both `validate` (run `42674087638`) and `compact` (run `42674169645`).

### [T-0029] CI, Compact & Validate Workflows Self-Healing (2026-11-09)
- **Task ID:** `T-0029`
- **Agent:** `orchestrator`
- **Scope & Objectives:**
  1. **Workspace Hygiene & Branch Alignment:** Fast-forwarded local `main` to `origin/main` (commit `644e06d`), resolved submodule tracking discrepancies for `.agents/plugins/claudex-loop` and `engines/turbo-fieldfare` in `.gitmodules`.
  2. **Test & Build Cache Hygiene:** Updated `.gitignore` to strictly ignore `.pytest_cache/`, `tests/.pytest_cache/`, `.codex-vitest-root/`, and `.codex-vitest-tmp/`.
  3. **Event Stream Gap Resolution (Compact Workflow):** Identified missing actor sequence `243` for actor `system-compact` on `2026-11-07`. Registered anomaly in `state/events/_anomalies.json` under ADR-006 with audit logging.
  4. **Submodule URL Resolution:** Configured missing URLs in `.gitmodules` so `actions/checkout` submodule recursion succeeds cleanly without exit code 128.
  5. **Infrastructure Verification:** Verified and started all 13 local OS daemons including `headroom` (port 8787).
  6. **Comprehensive Verification:** Ran full health suite (`scripts/health.py`), passing all 471 unit tests, all 6 verification checks, and all 51 sim scenarios.

### [T-0028] Hermeticize Unit Tests for CI (2026-11-07)
- **Task ID:** `T-0028`
- **Scope:** Mocked HTTP probes and subprocess calls for offline execution; sqlite in-memory testing for db queries.

### [T-0027] Pyrefly Type Narrowing & Activity Monitor Fix (2026-11-07)
- **Task ID:** `T-0027`
- **Scope:** Resolved type narrowing and simulation module shadowing in activity monitor.

### [T-0026] Local Loopback Proxy Bypass (2026-11-07)
- **Task ID:** `T-0026`
- **Scope:** Bypassed proxy for local loopback probes in `service_probes.py`.

### [T-0025] 100% Production Milestone & 3-Tier Harness-Loop-Graph (2026-10-16)
- **Task ID:** `T-0025`
- **Scope:** 3-Tier harness-loop-graph, AWS Bedrock Zero-Cost Credit Pool, 428 passing tests.

