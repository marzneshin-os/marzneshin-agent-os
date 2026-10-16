# ADR-023: Cross-Agentic WebCMD Self-Learning Browser Memory & Token Optimization Infrastructure

**Date:** 2026-09-30  
**Status:** Accepted  
**Author:** Autonomous Architecture Council  
**Workstream:** agentic-core  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-018, ADR-022

---

## 1. Context & Problem Statement

Modern AI coding agents frequently perform external web interactions: querying API specifications, exploring developer documentation, inspecting cloud consoles, and executing web-based research.
However, standard web browsing in AI harnesses (Claude Code, Antigravity IDE, Cursor, OpenCode, Codex) is stateless and un-cached:
1. **Redundant DOM Re-Exploration**: Every web query downloads and parses full, verbose HTML/DOM trees (30,000 to 100,000+ tokens per page).
2. **Context Window Degradation**: Exploring 3-5 pages easily consumes 200k+ tokens, increasing latency and accelerating rate limits.
3. **Flaky Navigation & Bot Challenges**: Exploratory scripts repeatedly stumble on dynamic DOM layouts and anti-bot verification hurdles.
4. **Agent Siloing**: Parallel agents within the OS (Coder, Reviewer, Supervisor) lack shared navigational memory and rediscover identical endpoints independently.

As demonstrated in the reference technology (**WebCMD**), a persistent **self-learning browser memory layer** can cache domain navigation graphs, remember element action shortcuts, and filter DOM boilerplate to permanently cut web browsing token spend by up to **90%**.

---

## 2. Decisions & Architecture

### D1: Core Shared Infrastructure (`scripts/lib/webcmd_memory.py`)
- Integrated at the shared system layer with zero third-party runtime dependencies (Python stdlib-only).
- Uses `scripts.lib.clock` for all time calls, complying with `scripts/verify.py --lint-clock`.
- Features implemented:
  - **Sitemap Navigation Store**: Persists domain routes, page titles, action counts, and selector shortcuts in `state/web_memory/sitemaps.json`.
  - **90% Token Reduction Engine**: Semantic parser strips styles, scripts, SVG, iframe, and boilerplate, extracting interactive action targets (`[@1]`, `[@2]`, ...) with concise CSS selector mapping.
  - **Structural Fingerprinting**: Computes structural skeleton hashes to verify DOM freshness on live visits. If layout drift occurs, the stale route is invalidated and relearned autonomously.
  - **Session & Profile Isolation**: Manages isolated workspaces and cookie jars per agent profile in `state/web_memory/profiles/`.
  - **Token Savings Ledger**: Logs telemetry to `state/budget/webcmd_savings.ndjson`.

### D2: L0 System Adapter Protocol Conformance (`adapters/webcmd.py`)
- Complies strictly with `BUILD-SPEC.md` §4 Adapter Protocol:
  - `healthz() -> Health`
  - `capabilities() -> list[str]` (`web_browse`, `web_extract`, `web_sitemap_get`, `web_learn_route`, `web_purge_cache`, `web_profile_manage`)
  - `execute(...)`: Circuit breaker (5 consecutive failures -> 60s cooldown), idempotency store (`IdemClass = none / scoped / forever`), and real `dry_run` support.
  - `rollback(...)`: Safe refusal / cache rollback.
- Simulation Fake (`sim/fakes/webcmd.py`): Enables deterministic, airgapped execution during §16 simulations and CI test runs.
- Passes all 9 contract checks in `adapters/contract.py`.

### D3: LangGraph Operational Integration (`agents/graph_nodes.py`)
- Exposes `webcmd_browse_optimized` tool to LangGraph ReAct workers (`coder`, `reviewer`, `supervisor`).
- Injects compressed action maps and article prose directly into agent scratchpads, eliminating context bloat during external documentation research.

### D4: Extended RTK Tool Filter (`scripts/lib/tokensaver.py`)
- Extended the token-saving gateway with an `html-web` autodetect pattern.
- Any tool result emitting HTML is automatically routed through the WebCMD semantic compressor before reaching model reasoning loops.

### D5: Universal MCP & CLI Interfaces (`scripts/mcp_webcmd.py` & `scripts/webcmd_cli.py`)
- **CLI (`scripts/webcmd_cli.py`)**: Provides interactive subcommands (`status`, `browse`, `sitemap`, `learn`, `purge`, `check-node`).
- **MCP Server (`scripts/mcp_webcmd.py`)**: Universal Model Context Protocol server exposing `webcmd_browse`, `webcmd_get_sitemap`, `webcmd_learn_route`, and `webcmd_status` over stdio/JSON-RPC.
- Registered in root `.mcp.json` for universal discovery.

### D6: Cross-Agent Unified Directives
- **Antigravity IDE**: `.agents/skills/webcmd-browser/SKILL.md`, `.agents/rules/webcmd-browser.md`, and `GEMINI.md`.
- **Claude Code**: `.claude/skills/webcmd-browser/SKILL.md` and `CLAUDE.md`.
- **Cursor / OpenCode / Codex**: `.cursor/rules/webcmd-browser.mdc`, `.cursorrules`, `.clinerules`, `.kilorules`, `.windsurfrules`.

---

## 3. Invariants & Governance

1. **Rule I3 (Task Receipt)**: Any automated workflow utilizing WebCMD emits valid cryptographic receipts.
2. **Rule I6 (No Raw Secrets)**: Web memory sanitizes authorization tokens and query parameters before persisting.
3. **Rule I11 (Sim-First Delivery)**: Airgapped simulation fake `sim/fakes/webcmd.py` ensures 100% of simulation scenarios pass without external network access.
4. **Rule I12 (Fail-Closed)**: Any network timeout or transport failure results in `Result(ok=False)` with zero state corruption.
5. **Rule I15 (Receipt Chain)**: Cache operations write exclusively to `state/web_memory/` and never mutate `receipts/` hash chains.
6. **Rule I17 (Single Writer)**: Profile caches are scoped to the executing agent lease.

---

## 4. Verification Evidence

- **Unit Tests**: 11 new tests (`tests/test_webcmd_memory.py`, `tests/test_webcmd_adapter.py`, `tests/test_router.py`).
- **Adapter Contract Checks**: 9/9 checks GREEN for both `WebCmdAdapter` and `WebCmdFake`.
- **Verify Gates**: 6/6 GREEN (`scripts/verify.py --all`).
- **Master Health Gate**: 347/347 tests PASS, 6/6 verify PASS, 51/51 sim scenarios PASS (score 1.0).
- **Regression Check**: 0 regressions against `state/HEALTH-BASELINE.json`.
