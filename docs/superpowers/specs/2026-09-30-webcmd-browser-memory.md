# Architectural Specification: WebCMD Self-Learning Browser Memory Infrastructure

- **Title**: Cross-Agentic WebCMD Self-Learning Browser Memory & Token Optimization Layer
- **Status**: Accepted
- **Author**: Autonomous Architecture Council
- **Date**: 2026-09-30
- **Governing Standard**: BUILD-SPEC.md v2.0, ADR-018, ADR-022

---

## 1. Executive Summary & Problem Formulation

Standard AI agent web interactions are stateless, un-cached, and brute-force. Whenever an agent accesses external documentation, API endpoints, web dashboards, or cloud consoles:
1. **Redundant DOM Exploration**: The agent re-fetches and parses complete HTML/DOM structures (typically 30,000 to 100,000+ tokens per page).
2. **Context Window Exhaustion**: A multi-step web workflow (3-5 navigations) rapidly consumes 200k+ tokens, degrading reasoning fidelity and accelerating rate limits.
3. **Flaky Selectors & Bot Obstacles**: Traditional scripts fail when dynamic DOM structures change or when encountering basic anti-bot heuristics.
4. **Agent Siloing**: Parallel agents (Coder, Reviewer, Supervisor) re-discover identical pages independently without sharing navigational intelligence.

### The Solution: WebCMD Integration
As demonstrated in the reference technology, **WebCMD** acts as a **persistent self-learning memory layer** between agents and the web. It caches sitemaps, domain navigation graphs, interactive element shortcuts, and page state recipes, reducing web browsing token consumption by up to **90%** while maintaining real-time freshness verification and cross-agent session isolation.

---

## 2. System Thinking Map (نقشه تفکر سیستمی)

```mermaid
graph TD
    %% Core Inputs & Trigger
    AgentGoal[Agent Goal / Web Task] --> Harness{Agent Environment}
    Harness -->|Antigravity IDE| AGSkill[.agents/skills/webcmd-browser]
    Harness -->|Claude Code| CCSkill[.claude/skills/webcmd-browser]
    Harness -->|OpenCode / Codex| OCSkill[.codex / .clinerules]
    Harness -->|LangGraph Fleet| LGWorker[agents/graph_nodes.py]

    %% Shared Protocol Layer
    AGSkill --> MCP[scripts/mcp_webcmd.py / .mcp.json]
    CCSkill --> CLI[scripts/webcmd_cli.py]
    OCSkill --> MCP
    LGWorker --> Adapter[adapters/webcmd.py: WebCmdAdapter]
    MCP --> Adapter
    CLI --> CoreLib[scripts/lib/webcmd_memory.py]

    %% Adapter Protocol & Governance
    Adapter -->|Circuit Breaker & Idempotency| CoreLib
    CoreLib -->|Checks Cache & Fingerprint| MemoryStore[(state/web_memory/)]
    
    %% Engine Execution Paths
    CoreLib --> Decision{Known & Fresh?}
    Decision -->|Yes (Hit)| ReplayEngine[Replay Shortcut / Compressed Extraction]
    Decision -->|No (Miss / Drift)| FetchEngine[Stealth Fetch & Semantic Compressor]
    
    %% Semantic Compression (90% Reduction)
    FetchEngine --> Compressor[DOM Semantic Reducer & Action Mapper]
    Compressor -->|Save Learned Route| MemoryStore
    Compressor -->|Record Token Metrics| BudgetLedger[(state/budget/webcmd_savings.ndjson)]
    
    %% Feedback & Output
    ReplayEngine --> Result[Token-Optimized Action Map / Content]
    Compressor --> Result
    Result --> AgentGoal
```

---

## 3. Architectural Decomposition & Shared Layering

In strict accordance with the **Cross-Agentic Architecture Mandate**, WebCMD is integrated at the **Shared Agentic Infrastructure Layer** as an L0 Adapter and Python stdlib core module:

### Layer 1: Core Shared Logic (`scripts/lib/webcmd_memory.py`)
- **Zero Third-Party Runtime Dependencies**: Python stdlib-only (`urllib`, `html.parser`, `re`, `json`, `hashlib`, `pathlib`). Safe for `verify.py --lint-imports`.
- **Domain Graph & Sitemap Store**: Structured JSON store in `state/web_memory/sitemaps.json`.
- **90% Token Reduction Engine**:
  - Eliminates scripts, stylesheets, comments, and decorative DOM trees.
  - Generates compact interactive element maps (`@action_id`, tag, label, selector, target URL).
  - Condenses prose content while preserving semantic structural hierarchies (headings, tables, lists).
- **Session & Profile Isolation**: Isolated workspaces (`state/web_memory/profiles/<profile_name>/`) supporting cookie/state isolation per agent.
- **Structural Fingerprinting & Auto-Invalidation**: Uses MD5/SHA-256 structural skeleton hashing. If a target site updates its layout, the stale route is evicted and relearned without crashing.
- **Fail-Closed Redaction**: Automatically scrubs authentication tokens and sensitive query parameters before persisting routes (I6 compliance).

### Layer 2: L0 System Adapter (`adapters/webcmd.py`)
- Implements `BUILD-SPEC.md` §4 `Adapter` Protocol:
  - `healthz() -> Health`
  - `capabilities() -> list[str]` (`web_browse`, `web_extract`, `web_sitemap_get`, `web_learn_route`, `web_purge_cache`)
  - `execute(op, payload, *, idem_key, idem_class, dry_run, deadline, provenance) -> Result`
  - `rollback(receipt_ref) -> Result`
- **Circuit Breaker**: 5 consecutive errors open the circuit for 60s.
- **Idempotency Store**: Prevents duplicate navigations and preserves deterministic results.
- **Matching Simulation Fake**: `sim/fakes/webcmd.py` passing `adapters/contract.py`.

### Layer 3: LangGraph Operational Integration (`agents/graph_nodes.py`)
- Exposes `webcmd_browse_optimized(url, action=None, selector=None, session=None)` to React agent workers (`coder`, `reviewer`, `supervisor`).
- Transparently feeds compressed action maps, eliminating context bloat during external documentation lookups.

### Layer 4: Cross-Agent Unified Facades
1. **Antigravity IDE**:
   - `.agents/skills/webcmd-browser/SKILL.md`: Autonomous instructions for triggering WebCMD during web inspection.
   - `.agents/rules/webcmd-browser.md`: Operating invariants for browser navigation.
2. **Claude Code**:
   - `CLAUDE.md`: Standing guidelines and daily CLI shortcuts.
   - `.claude/skills/webcmd-browser/SKILL.md`: Native skill for Claude Code.
   - `hooks/pre_tool.py`: Pre-tool interception to check cached web sitemaps.
3. **OpenCode / Codex / Cursor / Kilo / Windsurf**:
   - Configured in `.clinerules`, `.cursorrules`, `.kilorules`, `.windsurfrules`.
4. **Standard MCP Server (`scripts/mcp_webcmd.py`)**:
   - JSON-RPC 2.0 / stdio protocol exposing `webcmd_browse`, `webcmd_get_sitemap`, `webcmd_learn_route`.
   - Registered in `.mcp.json` for universal IDE tool invocation.

---

## 4. Invariants & Governance

1. **I3 (Receipt Tracking)**: Tasks utilizing WebCMD emit valid cryptographic receipts.
2. **I6 (No Secrets)**: Auth credentials or cookies in web memory are sanitized via `lib/redact.py`.
3. **I11 (Sim-First)**: Simulation scenarios can test web memory operations using `sim/fakes/webcmd.py`.
4. **I12 (Fail-Closed)**: If network fails or a site refuses connections, the adapter fails closed safely with `Result(ok=False)`.
5. **I15 (Receipt Chain)**: Cache operations do not tamper with `receipts/` hash chain.
6. **I17 (Single Writer)**: Profile caches are scoped to the running agent lease.

---

## 5. Verification Plan

1. **Unit Test Suite**: `tests/test_webcmd_memory.py` verifying parsing, sitemap learning, 90% token reduction ratio, and auto-invalidation.
2. **Adapter Contract Suite**: `tests/test_webcmd_adapter.py` executing all 9 contract checks (`run_contract`).
3. **System Health**: Complete run of `python3 scripts/health.py` ensuring 0 regressions across all existing tests and simulations.
