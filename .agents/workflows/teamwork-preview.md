---
description: Deploy collaborative multi-agent teams for large software projects, systems simulation, and multi-file refactors across milestones with adversarial verification gates.
argument-hint: "[project brief / refactoring goal]"
---

# Teamwork Multi-Agent Team (/teamwork-preview)

This workflow initiates a collaborative multi-agent team according to Google Antigravity's Teamwork architecture.

## Workflow Execution Steps

1. **Sentinel Scoping Interview (Phase 1)**:
   - Activates `sentinel` subagent.
   - Executes the "Specify What, Not How" interview.
   - Establishes scope, requirement blocks, independent verification methods, acceptance criteria, and dedicated project working directory (`~/teamwork_projects/{PROJECT_NAME}`).
   - Formulates the selected Integrity Mode (`development`, `demo`, `benchmark`).
   - Produces the reviewable prompt artifact (`request.md`).
   - Awaits user confirmation.

2. **Milestone Execution & Parallel Tracks (Phase 2)**:
   - Sentinel hands off to the `orchestrator` (Project Orchestrator).
   - Decomposes project into milestones in `project_plan.md` and tracks status in `progress.md`.
   - Assigns work to Workers with exclusive file ownership and Explorers for read-only research.

3. **Adversarial Verification Gates**:
   - Each milestone must pass:
     - `critic`: Code review for logic, architecture, and anti-facade compliance.
     - `challenger`: Adversarial stress-testing and worst-case inputs.
     - `auditor`: Raw command output validation and integrity mode enforcement.

4. **Success Auditor & Delivery**:
   - Spawns `auditor` as Success Auditor for full end-to-end verification pass.
   - Sentinel delivers verified completion summary to user.
