# Strict Project Compliance & Autonomous Multi-Agent Dispatch (ZERO MANUAL TYPING)

> **ZERO TOLERANCE POLICY**: This rule overrides ALL implicit behavior.
> The agent MUST follow the project's built-in protocols and services EXACTLY —
> never guess, never improvise, ALWAYS utilize integrated services, and **AUTOMATICALLY**
> dispatch the correct multi-agent paradigm without requiring the user to type slash commands.

---

## PHASE 0: SESSION & TASK INITIALIZATION (AUTOMATIC ON EVERY REQUEST)

At the start of EVERY turn, execute automatically:
1. **Service Auto-Verification & Auto-Start**:
   - Run `python3 scripts/dev.py status`.
   - If ANY service is DOWN, AUTOMATICALLY launch it: `python3 scripts/dev.py start`.
2. **Cold-Start Protocol**:
   - Read `state/STATE.json` → `state/HANDOFF.md` → `CONTEXT-PACK.md` → `CLAUDE.md`.
   - Read `BUILD-SPEC.md` (§0, §16, §17).
   - Check newest `decisions/ADR/` for settled architecture decisions.
3. **Safety & FSP Sync**:
   - Run `python3 scripts/fsp.py status`.
   - Run `python3 scripts/killswitch.py status` — verify fail-closed verdict is clear (`running`).
4. **Baseline Health Check**:
   - Verify baseline is GREEN (260 unit tests, 6 verify gates, 51 sim scenarios).

---

## PHASE 1: AUTONOMOUS PARADIGM CLASSIFICATION & DISPATCH (NO MANUAL TYPING)

The Orchestrator MUST classify the incoming task and automatically dispatch the appropriate workflow:

### Path A: AUTOMATIC BOOST REASONING LOOP (`/boost` behavior)
- **Triggers**: Bugs, crashes, deadlocks, race conditions, concurrency synchronization, memory leaks, performance bottlenecks, mathematical/algorithmic optimization, tricky multi-file refactoring, or questions like "why did X fail?".
- **Autonomous Execution**:
  1. Immediately engage Boost Phase 1 (Strategy Formulation & Task Breakdown).
  2. Dispatches `deep-investigator` for read-only call graph tracing and root-cause analysis (using Graphify).
  3. Dispatches `deep-coder` for surgical, thread-safe implementation and local test verification.
  4. Runs full regression suite; feeds any failure into an automated feedback correction loop until green.

### Path B: AUTOMATIC TEAMWORK MULTI-AGENT TEAM (`/teamwork-preview` behavior)
- **Triggers**: New major features, large subsystem builds, migrations across dozens of files, systems simulation, or multi-milestone research.
- **Autonomous Execution**:
  1. Immediately engage `sentinel` for scoping interview, integrity mode calibration (`development`, `demo`, `benchmark`), and dedicated workspace setup.
  2. Project Orchestrator breaks task into modular milestones in `project_plan.md` and `progress.md`.
  3. Assigns exclusive file ownership to Workers to prevent race conditions.
  4. Passes all candidate code through adversarial verification gates: `critic` (code review), `challenger` (stress testing), and `auditor` (real terminal output check).
  5. Conducts full E2E Success Audit before declaring completion.

### Path C: AUTOMATIC FSP & TIER 0 FLEET
- **Triggers**: Operational maintenance, configuration tuning, canary rollouts, killswitch reconciliations, test audits, token spend tracking, G5 receipts, state compaction.
- **Autonomous Execution**:
  - Automatically dispatches the dedicated Tier 0 subagent:
    - Tests & simulation: `qa-gate`
    - VPN configs & canary progression: `config-engineer`
    - Service supervisor & kill switch: `infra-sre`
    - Anomaly audit & red teaming: `adversarial-reviewer`
    - NSM, funnel & token spend: `analytics-engineer`
    - Receipts, compact & handoff: `handoff-guardian`
    - Secret redaction & untrusted wrap: `security-compliance`

---

## PHASE 2: SURGICAL DISCIPLINE & NO-GUESSING

1. **Never Guess Signatures or Data Shapes**:
   - Always read actual implementations via `view_file` or `grep_search`.
2. **Fail-Closed Principle (Iron Rule 6)**:
   - "I don't know" = "STOP". An unreadable safety control is engaged, not clear.

---

## PHASE 3: COMPLETION & RECEIPT RATIFICATION

Before declaring ANY task complete:
1. Run `python3 scripts/health.py` — verify all gates remain green.
2. Run `python3 scripts/verify.py --all` — verify receipt chain and invariants.
3. Emit event via `scripts/lib/events.py:emit()` and write G5 receipt via `scripts/lib/receipts.py:write()`.
4. Regenerate machine state: `python3 scripts/compact.py`.
5. Rewrite `state/HANDOFF.md` and update `CONTEXT-PACK.md`.
