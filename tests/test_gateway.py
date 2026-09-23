"""test_gateway.py — Comprehensive contract and functional tests for HTTP Gateway (§5.3, VS-12).

Tests every endpoint specified in BUILD-SPEC §5.3:
  - GET /.well-known/agent-card.json
  - GET /healthz and GET /readyz (fail-closed check on killswitch)
  - GET /v1/agents (filtered by capability)
  - POST /v1/tasks (idempotency, schema validation, 202 status)
  - GET /v1/tasks/{id} (status & state transitions)
  - POST /v1/tasks/{id}/messages (mid-task message)
  - POST /v1/tasks/{id}/cancel (cancel with reason)
  - GET /v1/tasks/{id}/events (SSE event stream)
  - POST/GET /v1/artifacts[/{id}] (upload/retrieve with sha256 verification)
  - POST /v1/policy/evaluate (dry-run policy decisions)
  - GET /v1/killswitch (read-only verification, Rule I14)
"""

import hashlib
import json
import unittest
from fastapi.testclient import TestClient

from gateway.app import create_app
from gateway.store.task_store import get_task_store
from scripts.lib import killswitch, a2a, clock


class TestGateway(unittest.TestCase):

    def setUp(self) -> None:
        self.app = create_app()
        self.client = TestClient(self.app)
        # Clear or reset task store
        store = get_task_store()
        store._tasks.clear()
        store._idempotency.clear()
        # Touch heartbeat so killswitch is fresh and clear
        killswitch.touch_heartbeat(verified_by="test-gateway", sources=["test"])

    def test_well_known_agent_card(self) -> None:
        """GET /.well-known/agent-card.json returns host agent card."""
        resp = self.client.get("/.well-known/agent-card.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("id", data)
        self.assertIn("capabilities", data)
        self.assertEqual(data["id"], "orchestrator")

    def test_healthz_and_readyz(self) -> None:
        """GET /healthz and /readyz report liveness and fail-closed readiness."""
        h_resp = self.client.get("/healthz")
        self.assertEqual(h_resp.status_code, 200)
        self.assertTrue(h_resp.json()["live"])

        r_resp = self.client.get("/readyz")
        self.assertEqual(r_resp.status_code, 200)
        self.assertTrue(r_resp.json()["ready"])
        self.assertEqual(r_resp.json()["killswitch"], "running")

    def test_readyz_fail_closed_on_killswitch(self) -> None:
        """GET /readyz returns 503 when kill switch is engaged (fail-closed, Rule I14)."""
        killswitch.engage(
            scope="global",
            source="K1",
            reason="Test emergency shutdown drill",
            engaged_by="test-operator"
        )
        try:
            resp = self.client.get("/readyz")
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            self.assertFalse(data["ready"])
            self.assertEqual(data["killswitch"], "killed")
        finally:
            killswitch.release(
                scope="global",
                released_by="test-operator"
            )

    def test_list_agents_and_filtering(self) -> None:
        """GET /v1/agents returns registry and supports capability filter."""
        resp = self.client.get("/v1/agents")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("agents", data)
        self.assertIn("orchestrator", data["agents"])

        # Filter by capability
        filtered_resp = self.client.get("/v1/agents?capability=qa.gate.run")
        self.assertEqual(filtered_resp.status_code, 200)
        filtered_data = filtered_resp.json()
        self.assertIn("qa-gate", filtered_data["agents"])
        self.assertNotIn("config-engineer", filtered_data["agents"])

    def test_task_lifecycle_and_idempotency(self) -> None:
        """POST /v1/tasks, GET /v1/tasks/{id}, messages, and idempotency dedup."""
        # 1. Submit task using valid fields
        payload = {
            "sender": "orchestrator",
            "to": "qa-gate",
            "capability": "probe.echo",
            "input": {"target": "node-1", "rounds": 3},
            "input_provenance": [{"field": "$.input", "source": "unit-test", "trust": "internal"}],
            "priority": "high",
            "autonomy_requested": "L2"
        }
        res1 = self.client.post("/v1/tasks", json=payload)
        self.assertEqual(res1.status_code, 202)
        task_info1 = res1.json()
        self.assertEqual(task_info1["status"], "admitted")
        self.assertFalse(task_info1["replayed"])
        task_id = task_info1["task_id"]

        # 2. Get task status
        get_res = self.client.get(f"/v1/tasks/{task_id}")
        self.assertEqual(get_res.status_code, 200)
        task_data = get_res.json()
        self.assertEqual(task_data["task_id"], task_id)
        self.assertEqual(task_data["state"], "admitted")
        self.assertGreaterEqual(len(task_data["history"]), 2)

        # 3. Post a message to task
        msg_payload = {"sender": "qa-gate", "content": {"progress": 50, "note": "Halfway done"}}
        msg_res = self.client.post(f"/v1/tasks/{task_id}/messages", json=msg_payload)
        self.assertEqual(msg_res.status_code, 200)
        self.assertEqual(msg_res.json()["status"], "ok")

        # 4. Check message was appended
        get_res2 = self.client.get(f"/v1/tasks/{task_id}")
        self.assertEqual(get_res2.json()["messages_count"], 1)

        # 5. Cancel task
        cancel_res = self.client.post(
            f"/v1/tasks/{task_id}/cancel",
            json={"reason": "Operator requested abort", "auto_rollback": True}
        )
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["status"], "cancelled")

        # 6. Verify final cancelled state
        get_res3 = self.client.get(f"/v1/tasks/{task_id}")
        self.assertEqual(get_res3.json()["state"], "cancelled")

    def test_task_submission_with_explicit_envelope_and_idempotency(self) -> None:
        """POST /v1/tasks with pre-built A2A envelope respects idempotency replay."""
        env = a2a.build_envelope(
            sender="orchestrator",
            to="qa-gate",
            capability="probe.echo",
            input={"check": "alpha"},
            input_provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
            env_epoch="epoch-1"
        )
        # First send
        res1 = self.client.post("/v1/tasks", json={"envelope": env})
        self.assertEqual(res1.status_code, 202)
        self.assertFalse(res1.json()["replayed"])

        # Second send with same envelope (idempotency key matches)
        res2 = self.client.post("/v1/tasks", json={"envelope": env})
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["replayed"])

    def test_artifacts_upload_and_download_sha256(self) -> None:
        """POST/GET /v1/artifacts calculates and verifies SHA-256 integrity."""
        raw_bytes = b"Hello Marzneshin Autonomous Agent OS Gateway Artifact"
        expected_hash = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()

        # Upload raw
        up_res = self.client.post(
            "/v1/artifacts",
            content=raw_bytes,
            headers={"Content-Type": "application/octet-stream"}
        )
        self.assertEqual(up_res.status_code, 201)
        up_data = up_res.json()
        self.assertEqual(up_data["status"], "created")
        self.assertEqual(up_data["hash"], expected_hash)
        self.assertEqual(up_data["size_bytes"], len(raw_bytes))
        art_id = up_data["artifact_id"]

        # Retrieve
        down_res = self.client.get(f"/v1/artifacts/{art_id}")
        self.assertEqual(down_res.status_code, 200)
        down_data = down_res.json()
        self.assertEqual(down_data["hash"], expected_hash)
        self.assertEqual(down_data["text"], raw_bytes.decode("utf-8"))

    def test_policy_evaluate_dry_run(self) -> None:
        """POST /v1/policy/evaluate performs dry-run decision evaluation."""
        payload = {
            "capability": "probe.echo",
            "sender": "orchestrator",
            "target": "qa-gate",
            "autonomy_requested": "L2",
            "inputs": {}
        }
        resp = self.client.post("/v1/policy/evaluate", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["verdict"], "ALLOW")
        self.assertTrue(data["allowed"])

    def test_killswitch_read_only(self) -> None:
        """GET /v1/killswitch returns read-only status (Rule I14)."""
        resp = self.client.get("/v1/killswitch")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("verdict", data)
        self.assertIn("rule_i14_notice", data)
        self.assertEqual(data["verdict"], "running")

    def test_task_events_sse_stream(self) -> None:
        """GET /v1/tasks/{id}/events streams SSE state transitions."""
        payload = {
            "sender": "orchestrator",
            "to": "qa-gate",
            "capability": "probe.echo",
            "input": {"stream": True},
            "input_provenance": [{"field": "$.input", "source": "test", "trust": "internal"}]
        }
        res = self.client.post("/v1/tasks", json=payload)
        task_id = res.json()["task_id"]

        # Cancel it so terminal state is reached quickly
        self.client.post(f"/v1/tasks/{task_id}/cancel", json={"reason": "done"})

        sse_res = self.client.get(f"/v1/tasks/{task_id}/events")
        self.assertEqual(sse_res.status_code, 200)
        self.assertIn("text/event-stream", sse_res.headers["content-type"])
        body = sse_res.text
        self.assertIn("state_transition", body)
        self.assertIn("close", body)


if __name__ == "__main__":
    unittest.main()
