"""test_revenue_command_center.py — Unit tests for Revenue Command Center (BUILD-SPEC §9.4, §13.5, VS-10).

Tests:
  1. MRR, ARR, ARPU, and NRR calculation backed by audit events.
  2. Live agent token cost injection into the SaaS unit economics profit formula.
  3. Autonomous Agent Fleet Leverage Ratio calculation.
  4. Counter-KPI Guardrail Matrix with independent ownership (Rule I13).
  5. Grafana dashboard JSON schema validity and panel coverage.
  6. Mini App web dashboard artifact completeness.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from lib import budget, growth, paths, revenue  # noqa: E402


class TestRevenueCommandCenter(unittest.TestCase):
    def test_mrr_and_revenue_calculation(self):
        res = revenue.compute_mrr_and_revenue(window_days=30)
        self.assertIn("mrr", res)
        self.assertIn("arr", res)
        self.assertIn("arpu", res)
        self.assertIn("nrr_pct", res)
        self.assertGreaterEqual(res["mrr"], 0.0)
        self.assertEqual(round(res["arr"], 2), round(res["mrr"] * 12.0, 2))
        self.assertGreater(res["arpu"], 0.0)
        self.assertGreaterEqual(res["nrr_pct"], 0.0)

    def test_live_agent_token_cost_injection_in_unit_economics(self):
        data = revenue.get_revenue_command_center(window_days=30)
        ue = data["unit_economics"]
        te = data["token_economics"]

        # Invariant: live token cost from budget must be present in unit economics
        self.assertEqual(ue["agent_token_cost_per_user"], te["live_token_cost_per_active_user"])
        # Invariant: GrossProfit = ARPU - (infra + payment + support + agent_token_cost)
        total_costs = (
            ue["infra_per_user"]
            + ue["payment_fee"]
            + ue["support_cost"]
            + ue["agent_token_cost_per_user"]
        )
        expected_profit = round(ue["arpu"] - total_costs, 2)
        self.assertAlmostEqual(ue["gross_profit_per_user"], expected_profit, places=2)

    def test_agent_leverage_ratio(self):
        leverage = revenue.compute_agent_leverage()
        self.assertIn("agent_leverage_ratio", leverage)
        self.assertIn("autonomous_tasks", leverage)
        self.assertIn("manual_interventions", leverage)
        self.assertGreater(leverage["autonomous_tasks"], 0)
        self.assertGreater(leverage["agent_leverage_ratio"], 0.0)

    def test_counter_kpi_panel_independent_ownership(self):
        ckpi = revenue.compute_counter_kpi_panel()
        self.assertEqual(ckpi["panel_status"], "healthy")
        self.assertEqual(ckpi["total_agents"], 8)

        for agent in ckpi["agents"]:
            # Rule I13: No agent can own its own counter-KPI
            self.assertNotEqual(
                agent["id"],
                agent["counter_kpi_owner"],
                f"Agent {agent['id']} owns its own counter-KPI! (Rule I13 violation)",
            )
            self.assertEqual(agent["status"], "healthy")

    def test_grafana_dashboard_validity(self):
        g_path = REPO / "dashboards" / "grafana" / "revenue_command_center.json"
        self.assertTrue(g_path.exists(), "Grafana dashboard file missing")
        with open(g_path, encoding="utf-8") as f:
            dash = json.load(f)

        self.assertEqual(dash.get("uid"), "marz-revenue-cmd-v1")
        self.assertEqual(dash.get("schemaVersion"), 38)
        self.assertIn("Revenue Command Center", dash.get("title", ""))

        panel_titles = [p.get("title", "") for p in dash.get("panels", [])]
        # Verify key rows / panels exist
        self.assertTrue(any("North Star" in t for t in panel_titles))
        self.assertTrue(any("Monthly Recurring" in t for t in panel_titles))
        self.assertTrue(any("Unit Economics" in t for t in panel_titles))
        self.assertTrue(any("Counter-KPI" in t for t in panel_titles))

    def test_miniapp_dashboard_artifact(self):
        m_path = REPO / "dashboards" / "miniapp" / "index.html"
        self.assertTrue(m_path.exists(), "Mini App index.html missing")
        content = m_path.read_text(encoding="utf-8")
        self.assertIn("Revenue Command Center", content)
        self.assertIn("North Star Metric", content)
        self.assertIn("Counter-KPI Guardrail Matrix", content)


if __name__ == "__main__":
    unittest.main()
