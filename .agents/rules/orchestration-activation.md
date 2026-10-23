# Multi-Agent Orchestration Activation Rule

## Automatic Orchestration Detection

When ANY of these signals appear in a user request, activate the `unified-orchestration-hub` skill:

1. Task touches 3+ files or subsystems
2. User mentions "orchestrate", "multi-agent", "parallel", "dispatch", "team"
3. Task requires specialist agents (config, security, QA, infra, analytics)
4. Task spans multiple domains (frontend + backend + infra + tests)
5. User invokes `/teamwork-preview`, `/goal`, or `/plan`

## Mandatory Pre-Flight

Before ANY orchestrated task:
1. Read `state/STATE.json` — verify `kill_switch.verdict == running`
2. Read `state/HANDOFF.md` — understand session context
3. Run `python3 scripts/killswitch.py status` — exit code must be 0
4. Invoke the Superpowers cycle (brainstorm → plan → TDD → verify)

## Layer Selection Priority

1. If task is trivial (1 file, few lines): skip orchestration, just do it
2. If task is small (1 function): use Superpowers cycle only
3. If task is standard (2-5 files): use Marzneshin 9-step protocol
4. If task is large (5+ files): use full parallel dispatch with Two-Key
5. If task is epic (multi-day): recommend `/teamwork-preview` to user

## Active MCP Servers for Orchestration

Leverage these MCP servers during orchestrated tasks when available:
- **memwal**: persist decisions between sessions
- **graphify**: understand codebase structure before planning
- **headroom**: compress context when dispatching multiple agents
- **codeburn**: track token costs across parallel agents

## Consistency Rules

When modifying core project files during orchestration, follow AGENTS.md:
- Adding/removing MCP tools: update ALL 8 locations listed in AGENTS.md
- Adding REST endpoints: update ALL 3 locations listed in AGENTS.md
- Bumping version: update ALL 7 locations listed in AGENTS.md
- All tests must pass before completing work (`npm test`)

## Harness² Two-Level Recursive Optimization (`harness2-recursion`)
- **Auto-Activation Triggers:** `/goal`, `/boost`, `/teamwork-preview`, or any task touching `>= 3` files.
- **Level-1 Loop:** Execute `Propose -> Probe -> Compose` using parallel `C_inv` (Invariant) and `C_dom` (Domain) candidates.
- **Level-2 Persistence:** Record `[Cue / Lesson / Empirical Evidence]` into `state/EXPERIENCE.md` via `python3 scripts/harness2.py record-experience` and `memwal_remember`.
