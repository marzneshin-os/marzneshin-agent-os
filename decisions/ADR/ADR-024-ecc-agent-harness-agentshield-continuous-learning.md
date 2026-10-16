# ADR-024: Everything Claude Code (ECC) Universal Agent Harness, AgentShield Security Auditor & Continuous Learning Architecture

**Date:** 2026-10-01  
**Status:** Accepted  
**Author:** Autonomous Architecture Council  
**Workstream:** agentic-core / security-compliance  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-018, ADR-022, ADR-023

---

## 1. Context & Problem Statement

As demonstrated in the reference analysis of **Everything Claude Code (ECC)** (Affaan Mustafa / Anthropic Hackathon Winner), high-velocity AI coding requires more than conversational LLMs. It requires a resilient, multi-agent harness with:
1. **AgentShield Proactive Security**: Automated scanning of harness configurations, rules, MCP tool permissions, and code diffs before execution.
2. **Continuous Learning & Instincts**: Capturing successful patterns and architectural rules with confidence scoring into persistent memory.
3. **Cross-Agentic Consistency**: Uniform rules and workflow surfaces across Antigravity IDE, Claude Code, Cursor, OpenCode, Cline, Windsurf, and Kilo.

Without this, autonomous agents in Marzneshin Agent OS operate with session amnesia, risk unsafe tool invocation or secret leaks, and suffer from prompt bloat.

---

## 2. Decisions & Architecture

### D1: Core Shared Infrastructure (`scripts/lib/ecc_harness.py`)
- Python standard library only (strictly compliant with `scripts/verify.py --lint-imports`).
- Strict virtual time conformance with `scripts.lib.clock` (`scripts/verify.py --lint-clock`).
- Secret redaction with `scripts.lib.redact`.
- Components:
  - `AgentShieldScanner`: Analyzes configurations, prompts, and code against OWASP LLM vulnerabilities, secret exposures, command injections, and excessive tool permissions.
  - `InstinctStore`: Persists confidence-scored architectural and coding heuristics in `state/instincts/catalog.json`.
  - `HarnessAudit`: Verifies parity and absence of configuration drift across all agentic harnesses.

### D2: L0 System Adapter Protocol Conformance (`adapters/ecc.py`)
- Subclasses `adapters.base.Adapter`.
- Exposes capabilities: `agentshield_scan`, `instinct_learn`, `instinct_query`, `instinct_update_confidence`, `harness_audit`, `harness_sync_rules`.
- Enforces Circuit Breaker (5 failures -> 60s cooldown) and IdempotencyStore.
- Genuine `dry_run` support.
- Simulation Fake (`sim/fakes/ecc.py`) passing the exact same 9 contract tests in `adapters/contract.py`.

### D3: LangGraph Worker Operational Integration (`agents/graph_nodes.py`)
- Adds `ecc_agentshield_audit` and `ecc_instinct_lookup` to `WORKER_TOOLS`.
- Equips ReAct workers (`coder`, `reviewer`, `supervisor`) with real-time security auditing and instinct recall.

### D4: Universal MCP & CLI Interfaces (`scripts/mcp_ecc.py` & `scripts/ecc_cli.py`)
- `scripts/mcp_ecc.py`: Zero-dependency JSON-RPC 2.0 stdio server registered in root `.mcp.json`.
- `scripts/ecc_cli.py`: Command-line interface for manual operator audits, instinct querying, and harness synchronization.

### D5: Cross-Agent Unified Directives
- Antigravity IDE: `.agents/skills/ecc-harness/SKILL.md` and `.agents/rules/ecc-harness.md`.
- Claude Code: `.claude/skills/ecc-harness/SKILL.md` and `CLAUDE.md`.
- Cursor: `.cursor/rules/ecc-harness.mdc` and `.cursorrules`.
- Cline, Windsurf, Kilo: `.clinerules`, `.windsurfrules`, `.kilorules`.

---

## 3. Consequences & Invariant Validation

- **Positive:** Agents gain permanent memory of invariants, automated security screening prevents accidental secrets/vulnerabilities, and unified cross-harness configuration prevents configuration drift.
- **Negative:** Slight CPU overhead during security scanning (<50ms per scan).
- **Invariants Upheld:**
  - I1 (GitHub SSoT): Instincts and reports are committed or derived cleanly.
  - I6 (No Raw Secrets): AgentShield flags any unredacted secret.
  - I12 (Fail-Closed): Security scan defaults to fail if critical issues or unreadable files occur.
  - I17 (Single Writer): State writes to `state/instincts/catalog.json` are atomic and isolated.
