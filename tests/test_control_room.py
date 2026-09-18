"""test_control_room.py — Unit tests for Control Room integration (BUILD-SPEC §9, VS-6).

Tests:
  1. MoxtAdapter contract conformance and operational execution.
  2. GitHub -> Control Room unidirectional sync across 5 workflows.
  3. Control Room -> GitHub reverse sync restricted strictly to the 2 whitelisted exceptions (Approval, Kill Switch).
  4. Non-whitelisted reverse sync attempts are rejected (I1 violation prevention).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

from adapters.contract import run_contract  # noqa: E402
from adapters.moxt import MoxtAdapter  # noqa: E402
from lib import control_room_sync, paths  # noqa: E402
from lib.atomic import read_json  # noqa: E402


class TestMoxtAdapter(unittest.TestCase):
    """Verify MoxtAdapter obeys the adapter contract and handles ops."""

    def test_contract_suite_passes(self):
        adapter = MoxtAdapter()
        ops = [
            "upsert_task",
            "assign_agent",
            "set_status",
            "set_field",
            "read_approval",
            "read_killswitch_task",
        ]
        results = run_contract(lambda: adapter, ops)
        failed = [r for r in results if not r.ok]
        self.assertEqual(failed, [], f"Contract checks failed: {[(f.check, f.detail) for f in failed]}")

    def test_healthz_and_capabilities(self):
        adapter = MoxtAdapter()
        h = adapter.healthz()
        self.assertTrue(h.ok)
        caps = adapter.capabilities()
        self.assertIn("upsert_task", caps)
        self.assertIn("read_approval", caps)
        self.assertIn("read_killswitch_task", caps)


class TestControlRoomSync(unittest.TestCase):
    """Verify unidirectional sync and strict reverse-sync exceptions."""

    def setUp(self):
        self.adapter = MoxtAdapter()

    def test_github_to_control_room_sync(self):
        res = control_room_sync.sync_github_to_control_room(self.adapter)
        self.assertTrue(res["ok"])
        self.assertGreaterEqual(res["synced_count"], 10)
        self.assertIn("KILL-SWITCH-TASK", res["tasks"])
        self.assertIn("HEALTH-BASELINE-TASK", res["tasks"])

    def test_reverse_sync_approval_exception_applied(self):
        res = control_room_sync.sync_control_room_to_github(
            self.adapter,
            task_id="T-TEST-APPR-1",
            updated_fields={"Approval": "granted"},
        )
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["applied"]), 1)
        self.assertEqual(res["applied"][0]["field"], "Approval")
        # Cleanup
        appr_file = paths.state_dir() / "approvals" / "T-TEST-APPR-1.json"
        if appr_file.exists():
            appr_file.unlink()

    def test_reverse_sync_killswitch_exception_applied(self):
        res = control_room_sync.sync_control_room_to_github(
            self.adapter,
            task_id="KILL-SWITCH-TASK",
            updated_fields={"Kill Switch": "Clear"},
        )
        self.assertTrue(res["ok"])
        self.assertEqual(len(res["applied"]), 1)
        self.assertEqual(res["applied"][0]["field"], "Kill Switch")

    def test_reverse_sync_unauthorized_fields_rejected(self):
        res = control_room_sync.sync_control_room_to_github(
            self.adapter,
            task_id="T-HACK-1",
            updated_fields={"title": "Hacked Title", "status": "Done"},
        )
        self.assertFalse(res["ok"])
        self.assertEqual(len(res["applied"]), 0)
        self.assertEqual(len(res["rejected"]), 2)
        for r in res["rejected"]:
            self.assertIn("not in reverse sync whitelist", r["reason"])


if __name__ == "__main__":
    unittest.main()
