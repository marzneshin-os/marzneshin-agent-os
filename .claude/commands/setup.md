---
description: Run Anthropic Claude Code Setup & Automation Recommender (ADR-031 / claude-code-setup)
---

Run the **Claude Code Automation Recommender** for Marzneshin Agent OS:

1. **Analyze Project Profile**:
   - Runtime: Python 3.12 (venv in `.venv`), TypeScript / Node tooling
   - Core Engines: LangGraph, FreeLLM Pool, WebCMD Browser, MemWAL, Reason Network P2P
   - Governance: BUILD-SPEC v2.0, Two-Key verification gate (`scripts/verify.py --all`), FSP protocol, Killswitch K1-K5, Budget tracking (`scripts/cost_tracker.py`)

2. **Evaluate Extensibility Pillars**:
   - **Hooks**: Protection hooks (`hooks/pre_tool.py`), formatting (`hooks/post_tool.py`), notifications (`hooks/notification.py`)
   - **MCP Servers**: `context7` (live library docs), `docker`, `memwal`, `reason-network`, `marzneshin-langgraph`
   - **Skills**: `project-conventions` (Claude-only background rules), `gen-test` (test generator), `claude-automation-recommender`
   - **Subagents**: `architect`, `config-engineer`, `security-reviewer`, `infraops-sre`, `qa-gate`, `watchdog-reviewer`
   - **Plugins**: Official marketplace (`/plugin install claude-code-setup@claude-plugins-official`)

3. **Output Tailored Recommendations**:
   - Present the top 1-2 actionable automations for the requested task.
   - Show exact config snippets for `.claude/settings.json`, `.mcp.json`, or `.claude/skills/`.
