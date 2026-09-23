---
name: codeburn
description: Local AI coding token usage, cost tracking, and optimization across 41 tools and agents (Claude Code, Cursor, Codex, Gemini CLI, Antigravity IDE). Analyzes spend, detects token waste, and manages budget guard rails.
trigger: /codeburn
---

# Codeburn — AI Token Usage & Cost Intelligence

Codeburn tracks AI coding token usage and costs across 41 tools and agents, reading session files directly from local disk with zero telemetry or API keys required.

## Key Capabilities

- **Overview & Totals**: Complete breakdown of spend, tokens (input, output, cache-read, cache-write), and cache hit ratios by model, tool, and project.
- **Waste Detection (`codeburn optimize`)**: Identifies re-read files, low read:edit ratios, bloated system prompts, uncapped terminal outputs, and ghost MCP servers/skills.
- **Budget Guard (`codeburn guard`)**: Soft caps, hard caps, and session checkpoints to prevent accidental token burn.
- **Commit Attribution (`codeburn yield`)**: Correlates AI token spend with delivered git commits.
- **Web Dashboard (`codeburn web`)**: Interactive local dashboard on port 4747.

## Available MCP Tools

When the Codeburn MCP server is active, agents can directly query:

1. `get_usage`:
   - Returns spend, token counts, and breakdowns by tool, model, project, and task.
   - Arguments: `period` ('today', 'week', '30days', 'month', 'all'), `provider`, `include_project_names` (boolean).
2. `get_savings`:
   - Analyzes sessions to find cost reductions, retry tax, and routing inefficiencies.

## Common Commands

- Overview report:
  ```bash
  codeburn overview
  codeburn overview --no-color
  ```
- Find waste:
  ```bash
  codeburn optimize
  codeburn optimize -p today
  ```
- Start web dashboard:
  ```bash
  codeburn web --port 4747 --no-open
  ```
- Install budget guard hooks:
  ```bash
  codeburn guard install
  codeburn guard status
  ```
- Model benchmark comparison:
  ```bash
  codeburn compare
  ```
