import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lib.service_probes import (
    measure_http_probe,
    measure_process_probe,
    measure_port_probe,
    probe_single_service,
    probe_all_services,
)


class TestServiceHealthUpgrade(unittest.TestCase):

    def test_measure_http_probe_down(self):
        """Verify unavailable port fails gracefully and reports latency and error."""
        res = measure_http_probe(port=59123, path="/health", timeout_s=0.5)
        self.assertFalse(res["ok"])
        self.assertIsNone(res["status_code"])
        self.assertGreaterEqual(res["latency_ms"], 0.0)
        self.assertIsNotNone(res["error"])

    @patch("urllib.request.urlopen")
    def test_measure_http_probe_mock_expected(self, mock_urlopen):
        """Verify expected status code matching with mock."""
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = measure_http_probe(port=8005, path="/", expected_status=[200], timeout_s=2.0)
        self.assertTrue(res["ok"])
        self.assertEqual(res["status_code"], 200)
        self.assertGreaterEqual(res["latency_ms"], 0.0)

    def test_measure_process_probe_missing(self):
        """Verify missing process returns ok=False and empty PIDs."""
        res = measure_process_probe("non_existent_ghost_daemon_xyz")
        self.assertFalse(res["ok"])
        self.assertEqual(res["pids"], [])
        self.assertEqual(res["rss_mb"], 0.0)

    def test_measure_process_probe_live(self):
        """Verify live process detection and memory parsing."""
        # We know python3 is currently executing this test
        res = measure_process_probe("python3")
        self.assertTrue(res["ok"])
        self.assertGreater(len(res["pids"]), 0)

    def test_measure_port_probe_down(self):
        """Verify TCP port probe on closed port."""
        res = measure_port_probe(59124, timeout_s=0.2)
        self.assertFalse(res["ok"])
        self.assertIsNotNone(res["error"])

    def test_probe_single_service_contract(self):
        """Verify probe_single_service returns standard contract dictionary."""
        cfg = {
            "port": 8005,
            "health": {"type": "http", "path": "/", "expected_status": [200], "timeout_s": 2.0}
        }
        report = probe_single_service("test-service", cfg)
        self.assertEqual(report["service"], "test-service")
        self.assertIn(report["status"], ("UP", "DOWN"))
        self.assertIn("latency_ms", report)
        self.assertIn("rss_mb", report)

    def test_probe_all_services_fleet(self):
        """Verify fleet probe covers all 12 services in configs/services.json."""
        reports = probe_all_services()
        self.assertGreaterEqual(len(reports), 12, "Fleet must probe all ecosystem services")
        services_found = [r["service"] for r in reports]
        self.assertIn("gateway", services_found)
        self.assertIn("agentmemory", services_found)
        self.assertIn("langgraph", services_found)
        self.assertIn("graphify", services_found)
        self.assertIn("ccr", services_found)


if __name__ == "__main__":
    unittest.main()
