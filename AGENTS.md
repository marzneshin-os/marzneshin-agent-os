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

---

# Autonomous Ecosystem & Strict Compliance Protocol (MANDATORY)

## 1. Automatic Infrastructure Maintenance (Zero-Manual-Intervention)
The agent MUST ensure all 12 core services remain continuously active without asking:
- Verify at session/task start: `python3 scripts/dev.py status`
- If any service is DOWN, AUTOMATICALLY run: `python3 scripts/dev.py start`.
- The ecosystem components:
  1. **AgentMemory** (`:3111`) — Persistent cross-session memory and audit store.
  2. **Claude Code Router (CCR)** (`:3456`, `:3458`) — Multi-model routing gateway.
  3. **Omniroute** (`:8080`) & **LangGraph** (`:8005`) — Multi-agent orchestrators.
  4. **FreeLLMAPI** (`:3001`) — LLM endpoints provider.
  5. **Headroom** (`:8787`) — Context compression proxy (`HEADROOM_OUTPUT_SHAPER=1`) and cache retrieval.
  6. **Codeburn** (`:4790`) — AI token usage and spend intelligence dashboard.
  7. **Graphify** (stdio watcher) — Knowledge graph engine (`graphify-out/`).
  8. **MemorySync** (stdio watcher) — Continuous event-to-memory sync.
  9. **Kimi K3** (`:8085`) & **Relevance Bridge** (`:8086`) — Local LLM / Agent bridges.
  10. **Claude-Mem** (`:37700`) — Persistent memory observer.

---

# Autonomous Dispatch & Multi-Agent Execution Engine (ZERO MANUAL TYPING)

> **MANDATORY INVARIANT**: The user NEVER needs to manually type slash commands (`/boost`, `/teamwork-preview`, `/agents`) or manually delegate to subagents.
> The Orchestrator MUST automatically analyze the prompt, classify the problem, engage the appropriate paradigm, and dispatch the required subagents autonomously.

## 1. Autonomous Routing Matrix

| Condition / Trigger | Automatically Engaged Paradigm | Autonomous Action & Subagent Delegation |
|---------------------|--------------------------------|-----------------------------------------|
| **Bugs, Concurrency, Deadlocks, Race Conditions, Algorithmic Optimization, Tricky Refactors** | **🚀 Boost Deep Reasoning** | 1. Automatically engage Boost 3-phase pipeline.<br>2. Dispatch `deep-investigator` for non-mutating call graph & root-cause isolation.<br>3. Dispatch `deep-coder` for thread-safe fixes & local unit tests.<br>4. Run regression suite and auto-correction loop until green. |
| **Large-Scale Features, Multi-File Refactors, Systems Simulation, Multi-Milestone Campaigns** | **👥 Teamwork Multi-Agent Team** | 1. Automatically engage Teamwork 2-phase workflow.<br>2. Activate `sentinel` for scoping, integrity mode calibration, and workspace isolation.<br>3. Project Orchestrator breaks task into milestones with exclusive file ownership.<br>4. Route candidate code through `critic`, `challenger`, and `auditor` gates.<br>5. Execute final Success Audit before delivery. |
| **Operational Tasks, Config Changes, CI Checks, Canary Rollouts, Telemetry, Handoffs** | **⚙️ FSP 9-Step OS Fleet** | 1. Automatically dispatch specialized Tier 0 agent:<br>- `qa-gate` for tests & verify gates.<br>- `config-engineer` for VPN & canary rollouts.<br>- `infra-sre` for services & killswitches.<br>- `adversarial-reviewer` for anomaly checks.<br>- `analytics-engineer` for NSM & token spend.<br>- `handoff-guardian` for G5 receipts & compacting.<br>- `security-compliance` for secret redactions. |

## 2. Execution Protocol & Status Banner
Whenever executing a task, the agent MUST prepend a clear status badge indicating the autonomously selected execution path:
```markdown
> 🤖 **سیستم اعزام خودکار (Autonomous Dispatch Active)**
> - **الگوی عملیاتی:** [🚀 Boost Deep Reasoning / 👥 Teamwork Multi-Agent / ⚙️ FSP Tier 0 Fleet]
> - **ساب‌ایجنت‌های در حال اجرا:** [لیست ساب‌ایجنت‌های مأمور شده]
> - **وضعیت زیرساخت:** ۱۲ سرویس محلی بررسی و فعال شدند
```

---

## 3. Mandatory Superpowers Workflow
Every agent action MUST follow the Superpowers skills framework in `.agents/skills/`:
- **Exploration & Feature Design**: ALWAYS invoke `brainstorming` (`SKILL.md`) first.
- **Task Decomposition**: ALWAYS invoke `writing-plans` (`SKILL.md`) before implementation.
- **Code Authoring**: Enforce `test-driven-development` (`SKILL.md`) — write failing test, verify failure, write minimal code, verify green.
- **Bug Resolution**: Enforce `systematic-debugging` (`SKILL.md`) — investigate, isolate, fix, verify.
- **Task Completion**: Enforce `verification-before-completion` (`SKILL.md`) before claiming completion.

## 4. Mandatory Knowledge Graph & Memory Consultation
- **Graphify First**: Query `graphify-out/GRAPH_REPORT.md` or run `graphify query` / MCP `query_graph` before architectural changes.
- **AgentMemory First**: Query `http://127.0.0.1:3111` for historical decisions and lessons learned at the beginning of each task.

## 5. No Guessing & Fail-Closed Governance
- Never invent function signatures or schema shapes — read the actual source code with `view_file` or `grep_search`.
- Fail-closed: if safety controls or permissions are ambiguous, STOP and fail closed (Iron Rule 6).
- All changes must pass `python3 scripts/health.py` (260 tests, 6 verify gates, 51 sim scenarios).

---

# CLAUDE.md Behavioral Guidelines

## 1. Think Before Coding
- State assumptions explicitly. Never assume silently.
- If multiple interpretations exist, present them.
- In case of uncertainty: STOP and ask.

## 2. Simplicity First
- Minimum code that solves the problem. No speculative abstractions.
- Match existing style.

## 3. Surgical Changes
- Touch only what you must.
- Never delete or modify unrelated code.

## 4. Goal-Driven Execution
- Define verifiable success criteria. Loop until verified green.
