"""test_t3_transport.py — Contract & fallback tests for T3 HTTP Gateway transport (§5.3, §5.5, I14)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.lib import a2a, clock, events, ids, killswitch, paths

REPO = Path(__file__).resolve().parent.parent


class MockT3Client(a2a.T3Client):
    def __init__(self, healthy: bool = True, deliver_fails: bool = False):
        self._healthy = healthy
        self._deliver_fails = deliver_fails
        self.delivered_envelopes = []

    def healthz(self) -> bool:
        return self._healthy

    def deliver(self, envelope: dict) -> dict:
        if self._deliver_fails:
            raise RuntimeError("Simulated T3 Gateway network drop")
        self.delivered_envelopes.append(envelope)
        return {"ref": f"http://127.0.0.1:8000/v1/tasks/{envelope['task_id']}", "status": "admitted"}


class TestT3Transport(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="marz-t3-"))
        (self.tmp / "state").mkdir(parents=True, exist_ok=True)
        (self.tmp / "BUILD-SPEC.md").write_text("test\n", encoding="utf-8")
        shutil.copytree(REPO / "analytics" / "schemas", self.tmp / "analytics" / "schemas")
        (self.tmp / "agents").mkdir(exist_ok=True)
        shutil.copy(REPO / "agents" / "registry.json", self.tmp / "agents" / "registry.json")
        
        self._env = dict(os.environ)
        os.environ["MARZNESHIN_OPS_ROOT"] = str(self.tmp)
        os.environ["MARZ_WORLD"] = "sim"
        os.environ.pop("KILL_SWITCH", None)
        
        from scripts.lib import validate
        validate.clear_cache()
        a2a.clear_registry_cache()
        self.clock = clock.VirtualClock(seed=7)
        clock.set_clock(self.clock)
        killswitch.touch_heartbeat(verified_by="test", sources=["test"])

    def tearDown(self) -> None:
        clock.set_clock(None)
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)
        a2a.clear_registry_cache()

    def _build_env(self, preferred_transport: str = "T3", test_nonce: str = "default") -> dict:
        reg = a2a.registry()
        reg["agents"]["qa-gate"]["transports"] = {
            "preferred": preferred_transport,
            "allowed": ["T1", "T2", "T3"]
        }
        return a2a.build_envelope(
            sender="orchestrator",
            to="qa-gate",
            capability="probe.echo",
            input={"nonce": test_nonce, "val": 42},
            input_provenance=[{"field": "$.input", "source": "test", "trust": "internal"}],
            transport=preferred_transport,
            env_epoch=f"epoch-{test_nonce}"
        )

    def test_choose_route_prefers_t3_when_healthy(self) -> None:
        """choose_route selects T3 when preferred and healthy."""
        env = self._build_env("T3", test_nonce="route-1")
        client3 = MockT3Client(healthy=True)
        route = a2a.choose_route("qa-gate", t3_client=client3)
        self.assertEqual(route, "T3")

    def test_choose_route_falls_back_when_t3_unhealthy(self) -> None:
        """choose_route gracefully falls back to T2 or T1 when T3 is unhealthy."""
        env = self._build_env("T3", test_nonce="route-2")
        client3 = MockT3Client(healthy=False)
        client2 = a2a.FileT2Client()
        route = a2a.choose_route("qa-gate", t2_client=client2, t3_client=client3)
        self.assertEqual(route, "T1")

    def test_send_delivers_via_t3_and_idempotency_replay(self) -> None:
        """send routes via T3 when healthy and replays stored result on duplicate key."""
        env = self._build_env("T3", test_nonce="send-1")
        client3 = MockT3Client(healthy=True)
        
        # 1. First send
        res1 = a2a.send(env, t3_client=client3)
        self.assertTrue(res1.ok)
        self.assertEqual(res1.transport, "T3")
        self.assertFalse(res1.replayed)
        self.assertEqual(len(client3.delivered_envelopes), 1)

        # 2. Second send with identical envelope / idempotency key
        res2 = a2a.send(env, t3_client=client3)
        self.assertTrue(res2.ok)
        self.assertTrue(res2.replayed)
        self.assertEqual(len(client3.delivered_envelopes), 1)

    def test_send_falls_back_to_t1_on_t3_delivery_failure(self) -> None:
        """send falls back to T1 baseline with zero content change if T3 deliver raises."""
        env = self._build_env("T3", test_nonce="send-fail-fallback")
        client3 = MockT3Client(healthy=True, deliver_fails=True)
        res = a2a.send(env, t3_client=client3)
        self.assertTrue(res.ok)
        self.assertEqual(res.transport, "T1")
        # Envelope delivered to T1 inbox
        inbox_file = paths.a2a_inbox("qa-gate") / f"{env['task_id']}.json"
        self.assertTrue(inbox_file.exists())


if __name__ == "__main__":
    unittest.main()
