# Everything Claude Code (ECC) Universal Agent Harness & AgentShield Security Architecture Spec

**Title:** Everything Claude Code (ECC) Universal Agent Harness, AgentShield Security Auditor & Continuous Learning Instincts Engine  
**Date:** 2026-10-01  
**Author:** Antigravity AI Engineering & Architecture Council  
**Workstream:** agentic-core / security-compliance  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-018, ADR-022, ADR-023, ADR-024  
**Video Reference:** https://youtube.com/shorts/g3Mh8Hws-jo?is=SANuR_GiRb5OD6xW (InsiderForce / Affaan Mustafa - Everything Claude Code)

---

## 1. Executive Summary & Video Analysis

The reference video (*"This Anthropic Hackathon Winner Just Released His Entire Claude Code Setup for Free - ECC"*, created by InsiderForce) documents the open-source release of **Everything Claude Code (ECC)** by **Affaan Mustafa**, who won the Anthropic NYC Hackathon by developing a production application in 8 hours utilizing a multi-agent harness rather than monolithic prompt interaction.

### The Fundamental Problem
Standard AI coding agents across tools (Claude Code, Antigravity IDE, Cursor, OpenCode, Codex) operate with critical structural deficits:
1. **Stateless Amnesia & Repeated Failures:** When an agent solves a tricky defect or adopts a project architectural invariant, that knowledge disappears when the session closes. In subsequent sessions, the agent commits the exact same mistake.
2. **Missing Pre-Execution Security Gate (AgentShield Deficit):** Agents generate code, modify system configurations (`CLAUDE.md`, `.cursorrules`, `.mcp.json`), or invoke terminal commands without an automated adversarial security auditor scanning for OWASP LLM vulnerabilities, command injections, secret leakage, or excessive MCP tool privileges.
3. **Monolithic Prompt Bloat vs. Dynamic Skills:** Stuffing all project rules, coding standards, and role guidelines into the system prompt wastes massive context (30k-80k tokens per turn) and degrades instruction following.
4. **Configuration Drift Across Agentic Harnesses:** Teams use multiple agentic environments (Antigravity IDE, Claude Code, Cursor, OpenCode, Cline, Windsurf). Without an SSOT synchronization engine, directives diverge, causing erratic agent behavior across developers.

### The Solution: ECC Architecture Integration
Marzneshin Agent OS integrates the complete architectural pattern of Everything Claude Code into its canonical L0/L2 hierarchy:
1. **AgentShield Security Engine:** Automated AST and pattern scanner auditing configuration surfaces, prompt files, rules, MCP manifests, and git diffs against prompt injection, secret exposure, command injection, and untrusted execution paths.
2. **Continuous Learning & Instincts Lifecycle:** Automated capture of coding patterns, architectural decisions, and bug-fix lessons into persistent, confidence-scored **Instincts** stored in `state/instincts/catalog.json`.
3. **Universal Harness Adapter (BUILD-SPEC ?4):** Standard L0 adapter (`adapters/ecc.py`) with matching airgapped simulation fake (`sim/fakes/ecc.py`) exposing deterministic security scanning and instinct management with circuit breakers and idempotency.
4. **LangGraph Worker Integration:** ReAct workers in `agents/graph_nodes.py` gain native access to `ecc_agentshield_audit` and `ecc_instinct_lookup`.
5. **Universal MCP & CLI Interfaces:** Stdio JSON-RPC 2.0 MCP server (`scripts/mcp_ecc.py`) and CLI management utility (`scripts/ecc_cli.py`).
6. **Cross-Agentic SSOT Matrix:** Synchronized rules and skills across Antigravity (`.agents/`), Claude Code (`.claude/`), Cursor (`.cursor/`), Cline (`.clinerules`), Windsurf (`.windsurfrules`), and Kilo (`.kilorules`).

---

## 2. Comprehensive System-Level Thinking Map

```text
Marzneshin Autonomous Agent OS (BUILD-SPEC v2.0)
?
??? Core Architecture & Invariants
?     ??? I1 (GitHub SSoT) & I3 (Receipt per task)
?     ??? I6 (No raw secrets / lib.redact)
?     ??? I12 (Fail-closed safety) & I17 (Single writer)
?     ??? FSP Protocol (?0)
?
??? Shared Infrastructure (scripts/lib/)
?     ??? lib/clock.py (Strict virtualized time)
?     ??? lib/redact.py (Secret sanitation)
?     ??? lib/policy.py & lib/adversarial_reviewer.py
?     ??? lib/ecc_harness.py  <-- [CORE SHARED CAPABILITY]
?           ??? AgentShield Security Scanner
?           ??? Continuous Learning Instincts Engine
?           ??? Harness Rules & Consistency Auditor
?
??? System Adapter Layer (adapters/ & sim/fakes/)
?     ??? adapters/base.py (Protocol, CircuitBreaker, Idempotency)
?     ??? adapters/ecc.py     <-- [L0 PRODUCTION ADAPTER]
?     ??? sim/fakes/ecc.py    <-- [SIMULATION FAKE FOR ?16]
?
??? Orchestration & Agent Runtime
?     ??? LangGraph Workflow (agents/graph_nodes.py)
?     ?     ??? Worker Tools: ecc_agentshield_audit, ecc_instinct_lookup
?     ?     ??? Pre-Commit Security Audit Hook
?     ??? A2A Dispatch & Envelopes (state/a2a/)
?
??? Cross-Agentic Coding Harnesses (SSOT Synchronization)
?     ??? Antigravity IDE: .agents/skills/ecc-harness/, .agents/rules/ecc-harness.md
?     ??? Claude Code:     .claude/skills/ecc-harness/, CLAUDE.md
?     ??? Cursor:          .cursorrules, .cursor/rules/
?     ??? OpenCode / Cline:.clinerules
?     ??? Windsurf:        .windsurfrules
?     ??? Kilo:            .kilorules
?
??? External Interfaces & Tooling
?     ??? CLI: scripts/ecc_cli.py (status, scan, instincts, sync, audit)
?     ??? MCP: scripts/mcp_ecc.py (Universal JSON-RPC 2.0 stdio server)
?     ??? Root Config: .mcp.json registration
?
??? Persistent State Layer (state/)
      ??? state/instincts/catalog.json (Learned instincts with confidence)
      ??? state/reports/agentshield_latest.json (Security audit telemetry)
```

---

## 3. Dependency & Blast Radius Analysis

- **What depends on it:** LangGraph workers, verification scripts, CI security checks, CLI operator commands, MCP callers.
- **What it depends on:** `scripts.lib.clock`, `scripts.lib.paths`, `scripts.lib.redact`, Python stdlib (`json`, `re`, `hashlib`, `pathlib`, `argparse`).
- **Blast radius:** Zero disruption to existing workflows. AgentShield scans read-only; instinct learning is append-only with atomic writes; adapter calls are guarded by circuit breaker and idempotency store.
- **Fail-Closed Behavior:** If AgentShield encounters an unreadable file or parse error in strict mode, it reports an audit failure (fail-closed, I12). If the instincts store is corrupted, it safely falls back to empty defaults without crashing the calling agent.
