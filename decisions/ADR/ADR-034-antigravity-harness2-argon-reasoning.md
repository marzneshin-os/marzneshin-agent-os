# ADR-034: Antigravity IDE Harness 2.0 & Argon-Grade Deep Reasoning Integration

**Date:** 2026-11-10  
**Status:** Accepted  
**Author:** Antigravity Argon Architect (`antigravity-argon-architect`)  
**Workstream:** agentic-core / harness-engineering / cognitive-governance  
**Governing Standard:** BUILD-SPEC.md v2.0, CLAUDE.md (I1–I17), ADR-024, ADR-028, ADR-030  

---

## 1. Context

Default fast-tier models (`gemini-3.8-flash-high`) exhibit four documented pathologies on complex multi-file architectures:
1. Reasoning excursions / overthinking on ambiguous prompts.
2. Chunked file slicing (`view_file` fragmentation) losing module-level invariants.
3. Premature one-shotting or ignoring edge-case failures without simulation gates.
4. High-effort server capacity pressure (`503`) when applied uniformly to mechanical tasks.

To achieve frontier-level reasoning and resolving reliability inside Antigravity IDE without modifying cloud model weights, we deploy a **Harness 2.0 Deterministic Cage** and **In-Context RLVR** execution loop backed directly by `marzneshin-agent-os` governance scripts (`fsp.py`, `killswitch.py`, `health.py`, `verify.py`, `compact.py`, `context_pack.py`, `lib/receipts.py`, `lib/redact.py`).

## 2. Architectural Decisions & SSoT Reconciliations

1. **Unified Root Cognitive Kernel (`GEMINI.md`):**
   - Merged the Harness 2.0 Cognitive Kernel (SSoT `I1`, Flash 3.8 cognitive overrides, 60/20/20 token budget, Iron Invariants `I1`–`I17`) with existing Boris Cherny rules, operational CLI shortcuts, and GRAVITAS invariants.
   - Kept free of YAML frontmatter (`always_on`) and concise (~6 KB) within the 24 KB per-file cap and 20,000-token total `always_on` budget.

2. **Latency-Safe Antigravity Lifecycle Hooks (`.agents/hooks.json`):**
   - `SessionStart` and `Stop` run `python3 scripts/fsp.py status` (timeout 15s).
   - `PostToolUse` on file edits runs `python3 scripts/verify.py --lint-imports --lint-clock` (timeout 15s, measured ~0.38s) instead of `python3 scripts/health.py --skip-sim` (measured ~118s), obeying the Class A hook latency budget (`CLAUDE.md §6`) while delegating full suite runs to `/sim-tdd` and `/fsp-closeout`.

3. **Hermetic Persistent Memory MCP (`.agents/mcp_config.json`):**
   - Configured `marzneshin-agentmemory` (`npx -y @agentmemory/agentmemory`, `XDG_DATA_HOME=./state`, `timeoutSeconds=120`) using repo-relative paths without bypassing OS hooks (`ONBOARDING.md §2`).

4. **Progressive-Disclosure Rules (`.agents/rules/`):**
   - Added flat `.md` rules with valid lowercase YAML frontmatter:
     - `argon-deep-reasoning.md` (`trigger: model_decision`): 5-phase protocol (Anti-Excursion & Holistic Read, Invariant Matrix, Best-of-3 Tree-of-Thoughts, Adversarial Pre-Mortem, Sim-First `I11`).
     - `marzneshin-code-invariants.md` (`trigger: glob`): stdlib-only `scripts/lib/`, forbidden derived-state hand-edits, `redact.py`, virtual clock, `agents/cards/`, fencing leases (`I17`).

5. **Operational Slash-Command Skills (`.agents/skills/`):**
   - Deployed `/fsp-start`, `/sim-tdd`, `/fsp-closeout`, and `/scar-learn`.
   - Reconciled `/fsp-start` with `ADR-030` (`prefix-caching.md`) Static-First read order and `scripts/fsp.py claim <WORKSTREAM>`.
   - Reconciled `/fsp-closeout` with `scripts/lib/receipts.py` (`Receipt`, `receipts.write`) and `hooks/task_complete.py`.
   - Preserved `.agents/skills/relevance-ai` submodule untouched.

6. **Read-Only Adversarial Critic Subagent (`.agents/agents/argon-critic.md`):**
   - Added read-only `argon-critic` (`model: pro`, `commandExecutionPolicy: sandbox`, skill `skills/scar-learn`) for pre-receipt A2A diff and invariant audits.

## 3. Rollback & Verification (`I7`, `I11`)

- **Rollback Method:** `git revert <commit>` removes or restores all 10 Harness 2.0 files + tests atomically with zero database/schema migrations (`max_ttr_s: 60`, verified via clean `health.py` before/after).
- **Verification Gates:** `tests/test_argon_harness.py` (7/7), `python3 scripts/verify.py --all` (6/6), `python3 scripts/ecc_cli.py scan` (0 CRITICAL / 0 HIGH), and full `python3 scripts/health.py` (all unit tests, verify gates, and 51 sim scenarios across seeds 11, 27, 43).

