import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

class TestClaudeSetupHooks(unittest.TestCase):
    def test_pre_tool_blocks_protected_files(self):
        hook_path = REPO_ROOT / "hooks" / "pre_tool.py"
        protected_targets = [
            ".env",
            ".env.local",
            "package-lock.json",
            "secrets.yaml",
            "credentials.json",
            ".git/config",
        ]
        for target in protected_targets:
            payload = {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(REPO_ROOT / target)},
            }
            res = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
            )
            self.assertEqual(
                res.returncode,
                2,
                f"Expected pre_tool.py to block edit to {target}, got {res.returncode}: {res.stderr or res.stdout}",
            )

    def test_notification_hook(self):
        hook_path = REPO_ROOT / "hooks" / "notification.py"
        payload = {
            "type": "notification",
            "matcher": "permission_prompt",
            "message": "Claude needs permission to run bash",
        }
        res = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )
        self.assertEqual(res.returncode, 0, f"Expected notification.py exit 0, got {res.returncode}")
        # Verify log entry in logs/notifications.log
        log_file = REPO_ROOT / "logs" / "notifications.log"
        self.assertTrue(log_file.exists(), "notifications.log should be created")
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        self.assertTrue(any("permission_prompt" in line for line in lines))

if __name__ == "__main__":
    unittest.main()
