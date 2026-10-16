"""Unit tests for Antigravity Doctor core library (scripts/lib/antigravity_doctor.py)."""

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import sim
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.antigravity_doctor import AntigravityDoctor


class TestAntigravityDoctor(unittest.TestCase):
    def setUp(self):
        self.doctor = AntigravityDoctor(world="sim")

    def test_extract_email_from_token(self):
        token_obj = {"email": "user@gmail.com", "access_token": "ya29.xyz"}
        self.assertEqual(self.doctor.extract_email_from_token(json.dumps(token_obj)), "user@gmail.com")

        raw_str = "Bearer ya29.foo user.test@example.com token_val"
        self.assertEqual(self.doctor.extract_email_from_token(raw_str), "user.test@example.com")

        self.assertIsNone(self.doctor.extract_email_from_token(""))

    def test_is_workspace_domain(self):
        self.assertFalse(self.doctor.is_workspace_domain("dev@gmail.com"))
        self.assertFalse(self.doctor.is_workspace_domain("test@googlemail.com"))
        self.assertTrue(self.doctor.is_workspace_domain("engineer@acme-corp.com"))
        self.assertTrue(self.doctor.is_workspace_domain("student@university.edu"))
        self.assertFalse(self.doctor.is_workspace_domain(""))

    def test_check_token_missing(self):
        chk = self.doctor.check_token(None)
        self.assertFalse(chk["present"])
        self.assertFalse(chk["valid_json"])

    def test_check_token_corrupted_json(self):
        chk = self.doctor.check_token("{not-valid-json")
        self.assertTrue(chk["present"])
        self.assertFalse(chk["valid_json"])
        self.assertIn("Malformed JSON", chk["error"])

    def test_check_token_valid(self):
        tok = json.dumps({"access_token": "abc", "refresh_token": "def", "expiry_date": 9999999999})
        chk = self.doctor.check_token(tok)
        self.assertTrue(chk["present"])
        self.assertTrue(chk["valid_json"])
        self.assertTrue(chk["has_access_token"])
        self.assertTrue(chk["has_refresh_token"])
        self.assertFalse(chk["expired"])

    def test_diagnose_healthy_sim(self):
        tok = json.dumps({"email": "dev@gmail.com", "access_token": "abc", "expiry_date": 9999999999})
        diag = self.doctor.diagnose(token_str=tok)
        self.assertEqual(diag.status, "HEALTHY")
        self.assertEqual(diag.active_email, "dev@gmail.com")
        self.assertFalse(diag.is_workspace_account)

    def test_diagnose_workspace_account_blocked(self):
        tok = json.dumps({"email": "employee@enterprise.com", "access_token": "abc", "expiry_date": 9999999999})
        diag = self.doctor.diagnose(token_str=tok)
        self.assertEqual(diag.status, "BLOCKED")
        self.assertTrue(diag.is_workspace_account)
        codes = [i["code"] for i in diag.issues]
        self.assertIn("WORKSPACE_ACCOUNT_INELIGIBLE", codes)

    def test_clean_dry_run(self):
        res = self.doctor.clean(dry_run=True)
        self.assertTrue(res.ok)
        self.assertTrue(any("dry_run" in c for c in res.removed_credentials))

    def test_repair_dry_run(self):
        res = self.doctor.repair(dry_run=True)
        self.assertTrue(res.ok)
        self.assertIn("step1", res.reauth_guidance)


if __name__ == "__main__":
    unittest.main()
