---
name: marzneshin-orchestration
description: Multi-Agent Orchestrator for Marzneshin Autonomous OS based on BUILD-SPEC.md v2.0. Dispatches Tier 0 specialist agents in isolated contexts with Two-Key verification and canonical receipts.
---

# 🎩 Marzneshin Multi-Agent Orchestrator (CEO Pattern)

Use this skill to orchestrate tasks across the marzneshin-agent-os repository strictly adhering to **BUILD-SPEC.md v2.0**.

## 👑 The CEO Role & Core Constraint
As the **Orchestrator (CEO Agent)**:
- **YOU NEVER DIRECTLY MUTATE THE DATA PLANE.** You do not edit production code or configs directly.
- **YOU NEVER APPROVE YOUR OWN WORK.**
- You decompose goals into isolated specialist tasks, grant leases, track budgets, dispatch subagents, and aggregate evidence.

---

## 🔁 The 9-Step Session Protocol (§0 of BUILD-SPEC.md)

For any task, you must execute the following sequence:

1. **SYNC:** Inspect state/STATE.json, state/HANDOFF.md, and verify kill switch status via python3 scripts/killswitch.py status.
2. **GAP SCAN:** Measure the distance between current state and the Definition of Done (DoD).
3. **CLAIM:** Ensure a valid lease exists with a fresh fencing token in state/leases/.
4. **PLAN:** Generate an execution plan of **at most 7 concrete steps**, each with a verifiable artifact.
5. **SIM:** If touching critical paths, run simulation scenarios in sim/ first. Red in sim = forbidden in production.
6. **EXECUTE:** Dispatch specialist subagents via invoke_subagent (TypeName: "self"), each with its specialized prompt.
7. **VERIFY:** Execute python3 scripts/verify.py and require real terminal evidence.
8. **EMIT:** Emit canonical Event to state/events/ and Receipt with prev_receipt_hash to eceipts/.
9. **HANDOFF:** Rewrite state/HANDOFF.md completely and release/renew the lease.

---

## 👥 The Tier 0 Specialist Team

When dispatching subagents, provide them their corresponding role prompt from .agents/skills/marzneshin-orchestration/agents/:

| Agent | Domain (owns) | Role | Autonomy |
|-------|-----------------|------|----------|
| @config-engineer | configs/** | Marzneshin config loop, canary rollouts | L2 |
| @adversarial-reviewer | Cross-cutting (no file ownership) | Independent review, counter-KPIs, raw evidence audit | L3 (reject) / L0 (approve) |
| @qa-gate | qa/**, rtifacts/qa/** | Test matrix, verification suites (scripts/verify.py) | L3 |
| @security-compliance | security/** | Secret leak prevention, prompt injection defense | L1 |
| @handoff-guardian | state/HANDOFF.md, state/leases/** | Session continuity, receipt chain integrity, lease reaper | L3 |
| @infra-sre | infra/** | Node provisioning, health, capacity, failover | L1 |
| @analytics-engineer | nalytics/** | Event taxonomy, JSON schemas, migrations | L2 |

---

## ⚖️ Two-Key Verification Rule

Before merging any change or emitting a completion receipt:
1. **Key 1 (qa-gate):** Must run python3 scripts/verify.py and confirm all 6 checks pass green.
2. **Key 2 (dversarial-reviewer):** Must review raw diffs and logs to confirm no metric gaming, no mock shortcuts, and no silent contract violations.
3. If either key fails, the change is rejected back to the responsible specialist agent.

---

## 🛡️ The Five Iron Rules
1. No changes without receipt (eceipts/).
2. Every state change through canonical schemas.
3. state/HANDOFF.md rewritten at every session end.
4. Fail-closed kill switches (scripts/killswitch.py).
5. Sim harness verification before production.

---

## ⚡ Integration with Superpowers, 265 Skills & MCP Servers

The orchestrator MUST mandate that all subagents invoke relevant project capabilities:
1. **Superpowers Cycle:** Enforce rainstorming -> writing-plans -> 	est-driven-development -> systematic-debugging -> erification-before-completion.
2. **On-Demand Skills (265 skills in .agents/skills/):**
   - @config-engineer invokes 
etwork-config-validation, docker-patterns, service-health.
   - @security-compliance invokes security-review, security-scan, prompt-optimizer.
   - @qa-gate invokes erification-loop, 	dd-workflow, eval-harness.
   - @analytics-engineer invokes schema-mapping, data-autocleaning.
   - @infra-sre invokes homelab-wireguard-vpn, 
etmiko-ssh-automation.
3. **MCP Servers:** Actively leverage moxt, memwal, kimi-moe, graphify, headroom, and codeburn.
