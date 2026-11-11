#!/usr/bin/env python3
"""tests/test_argon_harness.py — Verification suite for Harness 2.0 & Argon-grade reasoning (ADR-034)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from lib.ecc_harness import AgentShieldScanner, HarnessAudit  # noqa: E402


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise AssertionError(f"{path} missing YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise AssertionError(f"{path} malformed YAML frontmatter")
    data = yaml.safe_load(parts[1]) or {}
    return data, parts[2]


class TestArgonHarnessDeployment(unittest.TestCase):
    def test_gemini_md_kernel_and_legacy_rules_preserved(self):
        p = REPO / "GEMINI.md"
        self.assertTrue(p.exists(), "GEMINI.md must exist at repo root")
        text = p.read_text(encoding="utf-8")
        self.assertFalse(text.lstrip().startswith("---"), "GEMINI.md must NOT have YAML frontmatter (always_on root file)")
        self.assertLess(p.stat().st_size, 24_000, "GEMINI.md must stay below 24KB Antigravity file cap")

        for required in (
            "COGNITIVE & HARNESS 2.0 KERNEL",
            "Zero Reasoning Excursions",
            "Holistic File Comprehension",
            "Never Swallow Raw Logs",
            "60 / 20 / 20",
            "I1",
            "I11",
            "I12",
            "I15",
            "I16",
            "I17",
            "Boris Cherny",
            "GRAVITAS",
            "dev.py status",
            "antigravity_doctor_cli.py",
            "webcmd_cli.py",
            "ecc_cli.py",
        ):
            self.assertIn(required, text, f"GEMINI.md missing required directive: {required}")

    def test_mcp_config_valid_and_hermetic(self):
        p = REPO / ".agents" / "mcp_config.json"
        self.assertTrue(p.exists(), ".agents/mcp_config.json must exist")
        raw = p.read_text(encoding="utf-8")
        for forbidden in ("C:\\", "/mnt/", "wsl.exe"):
            self.assertNotIn(forbidden, raw, f".agents/mcp_config.json must remain hermetic (found {forbidden})")
        data = json.loads(raw)
        servers = data.get("mcpServers", {})
        self.assertIn("marzneshin-agentmemory", servers)
        am = servers["marzneshin-agentmemory"]
        self.assertEqual(am.get("command"), "npx")
        self.assertEqual(am.get("args"), ["-y", "@agentmemory/agentmemory"])
        self.assertEqual(am.get("env", {}).get("XDG_DATA_HOME"), "./state")
        self.assertEqual(am.get("timeoutSeconds"), 120)

    def test_hooks_json_valid_and_latency_safe(self):
        p = REPO / ".agents" / "hooks.json"
        self.assertTrue(p.exists(), ".agents/hooks.json must exist")
        data = json.loads(p.read_text(encoding="utf-8"))

        self.assertIn("marzneshin-fsp-session-start", data)
        self.assertIn("marzneshin-fast-gate-sensor", data)
        self.assertIn("marzneshin-stop-receipt-guard", data)

        start_hooks = data["marzneshin-fsp-session-start"]["SessionStart"]
        self.assertEqual(start_hooks[0]["command"], "python3 scripts/fsp.py status")
        self.assertLessEqual(start_hooks[0]["timeout"], 30)

        post_entry = data["marzneshin-fast-gate-sensor"]["PostToolUse"][0]
        self.assertIn("write_to_file", post_entry["matcher"])
        self.assertIn("replace_file_content", post_entry["matcher"])
        post_cmd = post_entry["hooks"][0]["command"]
        self.assertIn("scripts/verify.py --lint-imports --lint-clock", post_cmd)
        self.assertNotIn("health.py", post_cmd, "PostToolUse hook must remain sub-second/fast (<3s budget)")
        self.assertLessEqual(post_entry["hooks"][0]["timeout"], 15)

        stop_hooks = data["marzneshin-stop-receipt-guard"]["Stop"]
        self.assertEqual(stop_hooks[0]["command"], "python3 scripts/fsp.py status")

    def test_rules_flat_valid_frontmatter_and_budget(self):
        rules_dir = REPO / ".agents" / "rules"
        reasoning_path = rules_dir / "argon-deep-reasoning.md"
        invariants_path = rules_dir / "marzneshin-code-invariants.md"

        self.assertTrue(reasoning_path.exists())
        self.assertTrue(invariants_path.exists())
        self.assertLess(reasoning_path.stat().st_size, 24_000)
        self.assertLess(invariants_path.stat().st_size, 24_000)

        fm_r, body_r = _parse_frontmatter(reasoning_path)
        self.assertEqual(fm_r.get("trigger"), "model_decision")
        self.assertTrue(fm_r.get("description"))
        for phase in ("Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5", "Best-of-3", "Sim-First"):
            self.assertIn(phase, body_r)

        fm_i, body_i = _parse_frontmatter(invariants_path)
        self.assertEqual(fm_i.get("trigger"), "glob")
        globs = fm_i.get("globs", "")
        for prefix in ("scripts/**", "hooks/**", "sim/**", "adapters/**", "agents/**", "state/**", "receipts/**", "tests/**"):
            self.assertIn(prefix, globs)
        self.assertIn("scripts/lib/redact.py", body_i)
        self.assertIn("scripts/compact.py", body_i)
        self.assertIn("scripts/fsp.py claim", body_i)

        # Verify total always_on rule budget stays well under 20,000 tokens (~80KB conservative ceiling)
        always_on_bytes = (REPO / "AGENTS.md").stat().st_size + (REPO / "GEMINI.md").stat().st_size
        for rule in rules_dir.glob("*.md"):
            head = rule.read_text(encoding="utf-8", errors="ignore")[:300]
            if "trigger: always_on" in head:
                always_on_bytes += rule.stat().st_size
        self.assertLess(always_on_bytes, 40_000, f"always_on budget too large: {always_on_bytes} bytes")

    def test_four_harness_skills_valid_and_reconciled(self):
        skills_root = REPO / ".agents" / "skills"
        self.assertTrue((skills_root / "relevance-ai").exists(), "relevance-ai submodule must remain intact")
        self.assertIn("relevance-ai", (REPO / ".gitmodules").read_text(encoding="utf-8"))

        expected = {
            "fsp-start": ("CLAUDE.md", "BUILD-SPEC.md", "scripts/fsp.py claim", "<WORKSTREAM>", "scripts/health.py"),
            "sim-tdd": ("--seeds 11", "--skip-sim", "scripts/health.py", "scripts/verify.py --all", "argon-critic"),
            "fsp-closeout": ("scripts/lib/receipts.py", "verify.py --chain", "hooks/task_complete.py", "compact.py", "context_pack.py", "fsp.py release"),
            "scar-learn": ("scripts/anomaly.py", "marzneshin-code-invariants.md", "marzneshin-agentmemory", "scripts/verify.py", "scripts/health.py"),
        }
        for name, needles in expected.items():
            skill_path = skills_root / name / "SKILL.md"
            self.assertTrue(skill_path.exists(), f"Missing skill {skill_path}")
            fm, body = _parse_frontmatter(skill_path)
            self.assertEqual(fm.get("name"), name)
            self.assertTrue(fm.get("description"))
            for needle in needles:
                self.assertIn(needle, body, f"Skill {name} missing '{needle}'")

        # fsp-closeout must not tell agents to invoke a nonexistent scripts/receipt.py CLI
        closeout_body = (skills_root / "fsp-closeout" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("scripts/receipt.py", closeout_body)

    def test_argon_critic_subagent_readonly(self):
        p = REPO / ".agents" / "agents" / "argon-critic.md"
        self.assertTrue(p.exists(), ".agents/agents/argon-critic.md must exist")
        fm, body = _parse_frontmatter(p)
        self.assertEqual(fm.get("name"), "argon-critic")
        self.assertTrue(fm.get("subagent"))
        self.assertFalse(fm.get("mainAgent"))
        self.assertEqual(fm.get("model"), "pro")
        tools = set(fm.get("tools") or [])
        self.assertTrue({"view_file", "run_command"}.issubset(tools))
        self.assertTrue(tools.isdisjoint({"write_to_file", "replace_file_content", "multi_replace_file_content"}))
        self.assertIn("skills/scar-learn", fm.get("skills") or [])
        self.assertIn("read-only", body.lower())

    def test_harness_audit_and_agentshield_clean(self):
        audit_report = HarnessAudit(repo_root=REPO).audit()
        self.assertTrue(audit_report.ok, f"HarnessAudit failed: {audit_report.missing_rules}")

        scanner = AgentShieldScanner(repo_root=REPO)
        deployed_files = [
            REPO / "GEMINI.md",
            REPO / ".agents" / "mcp_config.json",
            REPO / ".agents" / "hooks.json",
            REPO / ".agents" / "rules" / "argon-deep-reasoning.md",
            REPO / ".agents" / "rules" / "marzneshin-code-invariants.md",
            REPO / ".agents" / "skills" / "fsp-start" / "SKILL.md",
            REPO / ".agents" / "skills" / "sim-tdd" / "SKILL.md",
            REPO / ".agents" / "skills" / "fsp-closeout" / "SKILL.md",
            REPO / ".agents" / "skills" / "scar-learn" / "SKILL.md",
            REPO / ".agents" / "agents" / "argon-critic.md",
        ]
        for target in deployed_files:
            self.assertTrue(target.exists(), f"Deployed artifact missing: {target}")
            findings = scanner.scan_file(target)
            severe = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]
            self.assertEqual(severe, [], f"AgentShield severe findings in {target}: {severe}")


if __name__ == "__main__":
    unittest.main()
