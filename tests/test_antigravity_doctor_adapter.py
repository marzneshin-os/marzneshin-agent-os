"""Contract and unit tests for AntigravityDoctorAdapter (adapters/antigravity_doctor.py)."""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from adapters.contract import run_contract
from adapters.antigravity_doctor import AntigravityDoctorAdapter
from sim.fakes.antigravity_doctor import AntigravityDoctorFake


class TestAntigravityDoctorAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = AntigravityDoctorAdapter(world="sim")
        self.fake = AntigravityDoctorFake(world="sim")
        self.deadline = datetime.now(timezone.utc) + timedelta(seconds=30)

    def test_healthz(self):
        h = self.adapter.healthz()
        self.assertTrue(h.ok)
        self.assertIn("doctor", h.detail.lower())

    def test_capabilities(self):
        caps = self.adapter.capabilities()
        self.assertIn("diagnose_account", caps)
        self.assertIn("clean_credentials", caps)
        self.assertIn("repair_environment", caps)
        self.assertIn("check_eligibility", caps)
        self.assertIn("get_auth_status", caps)

    def test_fake_contract(self):
        results = run_contract(lambda: AntigravityDoctorFake(world="sim"), self.fake.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Fake contract checks failed: {failures}")

    def test_adapter_contract(self):
        results = run_contract(lambda: AntigravityDoctorAdapter(world="sim"), self.adapter.capabilities())
        failures = [c for c in results if not c.ok]
        self.assertEqual(len(failures), 0, f"Adapter contract checks failed: {failures}")

    def test_execute_diagnose_sim(self):
        res = self.adapter.execute(
            "diagnose_account",
            {"token": '{"email": "user@gmail.com", "access_token": "tok"}'},
            idem_key="test-diag-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertEqual(res.data.get("status"), "HEALTHY")

    def test_execute_check_eligibility(self):
        res = self.adapter.execute(
            "check_eligibility",
            {"email": "corp@workplace.com"},
            idem_key="test-elig-1",
            idem_class="none",
            dry_run=False,
            deadline=self.deadline,
            provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
        )
        self.assertTrue(res.ok)
        self.assertTrue(res.data.get("is_workspace"))
        self.assertFalse(res.data.get("eligible"))


if __name__ == "__main__":
    unittest.main()
