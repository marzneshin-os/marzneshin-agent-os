# Implementation Plan: Everything Claude Code (ECC) Universal Harness & AgentShield Security

**Date:** 2026-10-01  
**Author:** Antigravity AI Engineering Council  
**Workstream:** agentic-core  
**Target:** Production-Grade Cross-Agent Integration  

---

## Phase 1: Core Shared Capability (`scripts/lib/ecc_harness.py`)
- [ ] Task 1.1: Implement `AgentShieldScanner` with AST and heuristic rule checks (secrets, injections, unsafe commands, MCP permissions).
- [ ] Task 1.2: Implement `InstinctStore` with confidence scoring, trigger matching, domain tagging, and persistence in `state/instincts/catalog.json`.
- [ ] Task 1.3: Implement `HarnessAudit` for cross-harness parity checks (`.claude`, `.cursor`, `.agents`, `.clinerules`, etc.).
- [ ] Task 1.4: Unit test `scripts/lib/ecc_harness.py` in `tests/test_ecc_harness.py`.

## Phase 2: L0 System Adapter & Simulation Fake (`adapters/ecc.py`, `sim/fakes/ecc.py`)
- [ ] Task 2.1: Implement `EccAdapter` adhering strictly to BUILD-SPEC ?4 Adapter protocol.
- [ ] Task 2.2: Implement `EccFake` in `sim/fakes/ecc.py`.
- [ ] Task 2.3: Implement contract tests in `tests/test_ecc_adapter.py` running `adapters.contract.run_contract`.

## Phase 3: LangGraph & MCP Integration
- [ ] Task 3.1: Expose `ecc_agentshield_audit` and `ecc_instinct_lookup` in `agents/graph_nodes.py` WORKER_TOOLS.
- [ ] Task 3.2: Implement `scripts/mcp_ecc.py` JSON-RPC 2.0 stdio server.
- [ ] Task 3.3: Register `ecc-harness` in root `.mcp.json`.

## Phase 4: CLI Interface & Cross-Agent Directives
- [ ] Task 4.1: Implement `scripts/ecc_cli.py` with `status`, `scan`, `instincts`, `sync`, `audit`.
- [ ] Task 4.2: Create `.agents/skills/ecc-harness/SKILL.md` and `.agents/rules/ecc-harness.md`.
- [ ] Task 4.3: Create `.claude/skills/ecc-harness/SKILL.md` and update `CLAUDE.md`.
- [ ] Task 4.4: Create `.cursor/rules/ecc-harness.mdc` and update `.cursorrules`, `.clinerules`, `.windsurfrules`, `.kilorules`, `GEMINI.md`.

## Phase 5: Verification, Validation & Health
- [ ] Task 5.1: Run `python3 scripts/verify.py --all` (all 6 gates).
- [ ] Task 5.2: Run full test suite: `python3 -m unittest discover -s tests`.
- [ ] Task 5.3: Run `scripts/ecc_cli.py audit` and `scripts/ecc_cli.py scan`.
