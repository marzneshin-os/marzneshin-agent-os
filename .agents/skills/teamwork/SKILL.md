---
name: teamwork
description: "Deploy collaborative multi-agent teams (/teamwork-preview) in Google Antigravity to tackle large software projects, multi-file refactors, systems simulation, and deep research across multi-day milestones with adversarial verification gates and structured handoffs."
---

# Teamwork Agent Teams (/teamwork-preview)

Use this skill when tackling engineering challenges that are too large, complex, or long-running for a single agent session. Teamwork coordinates specialized agents across orchestration, implementation, and adversarial verification tiers.

## When to Use

- **Multi-File Refactoring & Migrations**: Updating frameworks, modernizing APIs, or touching dozens of coupled files.
- **Systems Research & Simulation**: Building distributed consensus engines, CPU simulators, or OS kernels requiring continuous oracle validation.
- **Mathematical Proofs & Research**: Formal bounds, conjecture testing, automated counterexample exploration.
- **Multi-Day Projects**: Tasks spanning multiple milestones where fresh successor orchestrators prevent context bloat.

## Multi-Agent Architecture & Roles

```
[User]
   │  /teamwork-preview
   ▼
[Sentinel] ◄─── Phase 1: Scoping Interview (Specify What, Not How)
   │  Produces Prompt Artifact & Dedicated Workspace
   ▼
[Project Orchestrator] ◄─── Phase 2: Milestone Decomposition & Execution
   ├─► [Explorers] (Read-only repo exploration & call chains)
   └─► [Workers]   (Focused implementation with exclusive file ownership)
          │
          ├──► [Critic Gate]      (Correctness, style, interface conformance)
          ├──► [Challenger Gate]  (Adversarial stress-testing, worst-case inputs)
          └──► [Auditor Gate]     (Integrity mode validation, real command output)
                  │
                  ▼
          [Success Auditor] (End-to-end full verification before delivery)
                  │
                  ▼
          [Sentinel] ──► Delivers finished, verified project to User
```

## Two-Phase Workflow

### Phase 1: Prompt Crafting (Scoping Interview)
Follow the principle: **Specify What, Not How**.
1. **Scope & Objectives**: Clarify what to build, its purpose (`demo`, `production`, `eval`, `exploration`), and target users.
2. **Requirements**: Draft requirement blocks defining what the user actually cares about.
3. **Independent Verification**: Agree on an objective check for each requirement (test suite, benchmark script, or rubric).
4. **Acceptance Criteria**: Formulate clear, testable criteria for considering the project complete.
5. **Project Working Directory**: Set up a dedicated workspace folder (default: `~/teamwork_projects/{PROJECT_NAME}`).
6. **Prompt Artifact**: Output a reviewable artifact (`request.md`). Await user approval.

### Phase 2: Autonomous Execution (Structured Handoffs)
Once approved, Sentinel hands off to the **Project Orchestrator**:
- **Artifacts Maintained**:
  - `request.md`: Captures prompt, objectives, constraints, acceptance criteria.
  - `project_plan.md`: Tracks milestones, active workstreams, dependency graph.
  - `progress.md`: Records live milestone status, test evidence, completed tracks.
- **Exclusive File Ownership**: Workers are assigned non-overlapping file sets. Two workers never touch the same file concurrently.
- **Per-Agent Scratch**: Helper scripts, scratch notes, and debug logs stay in per-agent scratch directories.
- **Successor Handoffs**: Between milestones, the Project Orchestrator hands off state to a fresh successor orchestrator to maintain maximum reasoning clarity.

## Integrity Modes

| Mode | Purpose | Verification Behavior |
|------|---------|-----------------------|
| `development` | Rapid iteration | Flags only fabricated outputs & facade implementations. Code reuse and libraries allowed. (Default) |
| `demo` | Reproducible presentation | Prohibits copying core logic from open source, delegating core work to external tools, or reading tests to reverse-engineer behavior. |
| `benchmark` | Maximum evaluation strictness | Fully independent, from-scratch implementation. Standard library only. No mocked passes. |

## Adversarial Verification Gates

Before any milestone is accepted:
1. **Critic**: Performs independent code review (logic, completeness, interface contracts, style).
2. **Challenger**: Runs adversarial tests, edge cases, failure-path probes, and worst-case resource inputs.
3. **Auditor**: Inspects raw command execution evidence. Fails any mocked or skipped tests.
4. **Success Auditor**: Conducts the final comprehensive E2E audit across all components before Sentinel presents completion.
