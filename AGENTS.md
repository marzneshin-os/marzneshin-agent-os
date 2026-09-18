# AGENTS.md — Instructions for Autonomous Coding Agents

## Architecture Overview
Marzneshin Autonomous OS is an event-sourced control plane for multi-agent workflows.

### Integrated Agent Services
1. **AgentMemory** (Port 3111):
   - Project-scoped persistent memory daemon.
   - Command: `python3 scripts/dev.py start --only agentmemory`
2. **Claude Code Router (CCR)** (Ports 3456 / 3458):
   - Multi-model routing gateway and dashboard.
   - Command: `python3 scripts/dev.py start --only ccr`
3. **Graphify** (Knowledge Graph Engine):
   - Local deterministic AST parsing, Leiden community detection, and queryable knowledge graph.
   - Outputs in `graphify-out/` (`graph.json`, `graph.html`, `GRAPH_REPORT.md`).
   - Query: `graphify query "<question>"`
   - Path: `graphify path "<nodeA>" "<nodeB>"`
   - Auto-sync watcher: `graphify . --watch`
   - MCP Server: `graphify-mcp graphify-out/graph.json` (exposes `query_graph`, `get_node`, `god_nodes`, `shortest_path`, etc.)
4. **Headroom** (Context Compression & CCR Cache):
   - Context compression proxy running on port 8787 (`HEADROOM_OUTPUT_SHAPER=1`).
   - Reversible CCR cache with `headroom_retrieve` tool for on-demand unabridged retrieval.
   - Health check: `headroom doctor`
   - Savings report: `headroom savings`, `headroom output-savings`
   - MCP Server: `headroom mcp serve` (exposes `headroom_compress`, `headroom_retrieve`, `headroom_stats`)
5. **Codeburn** (AI Token Spend & Waste Optimization):
   - Local token usage and cost intelligence across 41 AI coding tools and agents.
   - Web Dashboard: `codeburn web --port 4747 --no-open`
   - Overview: `codeburn overview --no-color`
   - Waste audit: `codeburn optimize`
   - MCP Server: `codeburn mcp` (exposes `get_usage`, `get_savings`)

### Unified Process Management
Run `python3 scripts/dev.py status` to inspect all services.
Run `python3 scripts/dev.py start` to launch all local services in background.

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
