# ADR-021: Autonomy Ratchet, Shadow Mode Agreement, and 72-Hour Autonomous Marathon (VS-11)

**Date:** 2026-09-18
**Status:** Accepted
**Author:** Momo (Tier 0 Lead Agent)
**Workstream:** agentic-core
**Active Slice:** VS-11 (Autonomy Ratchet & Shadow Mode)

---

## 1. Context & Problem Statement
In autonomous systems, naive level promotion based solely on "runs without crashing" is dangerous because an agent operating with human oversight never proves what it would do *without* human intervention. Conversely, leaving an agent permanently bound to L1/L2 wastes the leverage of the autonomous architecture.
To solve this, BUILD-SPEC §6.2 requires empirical counterfactual evidence (Shadow Mode), strict 3-condition promotion gating, immediate fail-closed demotion with 72-hour quarantine on breaches, and proof of 72-hour unsupervised operation across multiple random seeds before production activation.

---

## 2. Decisions & Architecture

### D1: Shadow Mode Counterfactual Decision Recording (§6.2)
- While an agent operates at autonomy level $L_n$, it records the exact action it would have taken at $L_{n+1}$ without executing it (`record_shadow_decision`).
- Shadow decisions are compared against human actions to calculate empirical shadow agreement rate:
  $$S_A = \frac{\text{matching decisions}}{\text{total samples}}$$
- Emits `autonomy.shadow_decision` events.

### D2: The 3-Condition Promotion Gate (§6.2)
Promotion from $L_n \rightarrow L_{n+1}$ requires ALL three conditions to be satisfied simultaneously (Boolean AND):
1. **30 consecutive clean runs:** 0 rollbacks, 0 guardrail breaches, 100% complete receipts, KPI drift < 2%, 0 counter-KPI regressions.
2. **$\ge 95\%$ shadow agreement:** over $\ge 20$ approved shadow vs human samples.
3. **Green simulation suite:** all required scenarios pass across $\ge 3$ seeds.
- **Rule I17 Hard Ceiling:** Money, pricing, security mutations, and untrusted inputs are permanently capped at L1.

### D3: Immediate Demotion & 72-Hour Quarantine (§6.2)
- Any critical guardrail breach or metric regression immediately demotes the agent by 1 level.
- Enforces an immutable 72-hour quarantine (`quarantine_until = clock.now() + 72h`), during which promotion is strictly forbidden.
- Emits `autonomy.demoted` and `autonomy.quarantined` audit events.

### D4: Machine-Readable Review Contract (`/autonomy-review`)
- Contract generated per `(agent, capability)` wrapped in a valid `A2ATaskEnvelope` (`analytics/schemas/a2a-envelope.schema.json`).
- Written directly to the Orchestrator's inbox (`state/a2a/inbox/orchestrator/autonomy_review_<agent>_<ts>.json`).

### D5: 72-Hour Unsupervised Autonomous Marathon (§16, §17)
- Executed 72 virtual hours across 10 random seeds (seeds 101 to 110, totaling 720 virtual hours) using the simulation harness.
- Result: 10/10 seeds passed with score 1.0, 0 human interventions required, 100% receipt coverage.

---

## 3. Invariants & Guarantees Maintained
- **Invariant I1 (Append-Only Event Truth):** All shadow decisions, reviews, promotions, and demotions emit immutable audit events.
- **Invariant I12 (Fail-Closed Safety):** Breaches demote immediately and lock into 72-hour quarantine.
- **Invariant I17 (Autonomy Ceilings):** L1 permanent ceiling strictly enforced on money, pricing, security, and untrusted inputs.
- **Rule G5 (Continuous Receipt Chains):** Closed with receipt `T-0023` linked to `T-0022`.

---

## 4. Verification Evidence
- 260 unit tests pass with 100% green status (`pytest tests/`).
- 6 verify checks pass (`scripts/verify.py`).
- 51 simulation scenarios across 3 seeds pass with score 1.0.
- 72-hour unsupervised marathon passes across 10 random seeds (score 1.0).
- Cold-restore drill passes with score 1.0.
