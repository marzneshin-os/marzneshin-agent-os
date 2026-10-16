# Multi-Agent Orchestration Activation Rule

## Automatic Orchestration Detection

When ANY of these signals appear in a user request, activate the `unified-orchestration-hub` skill:

1. Task touches 3+ files or subsystems
2. User mentions "orchestrate", "multi-agent", "parallel", "dispatch", "team"
3. Task requires specialist agents (config, security, QA, infra, analytics)
4. Task spans multiple domains (frontend + backend + infra + tests)
5. User invokes /teamwork-preview, /goal, or /plan

## Mandatory Pre-Flight

Before ANY orchestrated task:
1. Read state/STATE.json -- verify kill_switch.verdict == running
2. Read state/HANDOFF.md -- understand session context
3. Invoke the Superpowers cycle (brainstorm -> plan -> TDD -> verify)

## Layer Selection Priority

1. If task is trivial (1 file): skip orchestration, just do it
2. If task is small (1 function): use Superpowers cycle only
3. If task is standard (2-5 files): use Marzneshin 9-step protocol
4. If task is large (5+ files): use full parallel dispatch with Two-Key
5. If task is epic (multi-day): recommend /teamwork-preview to user

## Active MCP Servers for Orchestration

Always leverage these MCP servers during orchestrated tasks:
- memwal: persist decisions between sessions
- graphify: understand codebase structure before planning
- headroom: compress context when dispatching multiple agents
- codeburn: track token costs across parallel agents
