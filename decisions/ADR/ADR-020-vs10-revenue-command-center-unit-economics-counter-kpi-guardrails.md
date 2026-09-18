# ADR-020: Revenue Command Center, Live Token Costs in Unit Economics, and Counter-KPI Guardrails (VS-10)

**Date:** 2026-09-18
**Status:** Accepted
**Author:** Momo (Tier 0 Lead Agent)
**Workstream:** agentic-core
**Active Slice:** VS-10 (Revenue Command Center)

---

## 1. Context & Problem Statement
As autonomous agent teams begin executing mutations, canaries, and growth experiments, economic visibility becomes a prerequisite for safe scaling. Standard analytics tools either:
1. Ignore AI token spend in unit economics, presenting a false illusion of profitability while agents quietly burn margins.
2. Rely on external third-party proprietary SaaS analytics, creating single-point-of-failure dependencies and violating our solo-operator zero-cost local governance principles.
3. Lack independent counter-KPI guardrails, allowing agents to optimize primary metrics (e.g. shipping volume) at the expense of stability (escalation latency, rollback rates, or gate flakiness).

---

## 2. Decisions & Architecture

### D1: Live Agent Token Cost Injection in SaaS Profit Formula (§13.3, §13.5)
- Rather than using static estimates, the unit economics engine dynamically queries the budget ledger (`scripts/lib/budget.py`) to derive actual USD spent by the agent fleet:
  $$\text{live\_agent\_token\_cost\_per\_user} = \frac{\text{Total Agent Token Spend (USD)}}{\max(1, \text{NSM Count})}$$
- This live cost is injected directly into the gross profit and margin calculation:
  $$\text{GrossProfit/User} = \text{ARPU} - \text{Infra} - \text{PaymentFee} - \text{Support} - \mathbf{LiveTokenCost/User}$$
  $$\text{LTV} = \text{ARPU} \times \text{GrossMargin} \times 12$$

### D2: Topline Revenue & Retention Backed by Raw Event Audit Chains (§13.2)
- MRR, ARR, ARPU, and Net Revenue Retention (NRR) are computed directly from `checkout.completed` audit events.
- Cohort revenue is compared across 30-day windows to detect expansion or contraction.
- Every metric traces 100% back to raw event IDs, satisfying Invariant I1 and Rule G5.

### D3: Autonomous Agent Fleet Leverage Multiplier (§10.1)
- Measures the solo-operator leverage provided by the autonomous system:
  $$\text{Agent Leverage Ratio} = \frac{\text{Autonomous Tasks } (L2+)}{\max(1, \text{Manual Interventions } (L0, \text{crashes}))}$$
- Tracked across all receipts on disk.

### D4: Counter-KPI Guardrail Matrix & Rule I13 Enforcement (§10.4)
- A unified health panel evaluates the Counter-KPI for every Tier 0 agent + Analytics Engineer:
  - **Orchestrator:** Escalation Latency (Owner: `adversarial-reviewer`)
  - **Config Engineer:** Rollback Rate (Owner: `qa-gate`)
  - **InfraOps/SRE:** Change Failure Rate (Owner: `security-compliance`)
  - **QA Gate:** Gate Flakiness (Owner: `adversarial-reviewer`)
  - **Security & Compliance:** False Positive Block Rate (Owner: `adversarial-reviewer`)
  - **Handoff Guardian:** Lease Thrash Rate (Owner: `orchestrator`)
  - **Adversarial Reviewer:** Over-Rejection Rate (Owner: `orchestrator`)
  - **Analytics Engineer:** Metric Gaming Alerts (Owner: `adversarial-reviewer`)
- Panel status verifies that no agent owns its own counter-KPI (Rule I13).

### D5: Production Dashboards: Grafana & Mini App
- **Grafana 10+ Model:** `dashboards/grafana/revenue_command_center.json` with 14 panels covering Topline, Unit Economics, Funnel, Reliability, Agent Fleet, and Counter-KPIs.
- **Telegram & Web Mini App:** `dashboards/miniapp/index.html` featuring responsive layout, dark cyber theme, live formula breakdown, and interactive funnel visualization.
- **CLI:** `scripts/dashboard.py` supporting `summary`, `json`, and `export-grafana`.

---

## 3. Invariants & Guarantees Maintained
- **Invariant I1 (Events Truth):** Revenue, NSM, and funnel numbers derive exclusively from immutable audit events.
- **Invariant I13 (Separation of Duties):** Every KPI has an independently owned Counter-KPI.
- **Invariant I16 (Zero Traffic Inspection):** Growth & revenue metrics store zero packet contents or destination IPs.
- **Rule G5 (Continuous Receipt Chains):** Closed with receipt `T-0022` linked to `T-0021`.

---

## 4. Verification Evidence
- 255 unit tests pass with 100% green status (`pytest tests/`).
- 6 verify checks pass (`scripts/verify.py`).
- 51 simulation scenarios across 3 seeds pass with score 1.0.
- Cold-restore drill passes with score 1.0.
