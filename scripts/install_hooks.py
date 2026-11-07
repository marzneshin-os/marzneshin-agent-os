#!/usr/bin/env python3
"""
Marzneshin Autonomous OS — Git Hooks Installer
Installs Two-Key pre-commit and pre-push hooks to enforce zero regressions automatically.
"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"

PRE_COMMIT_SCRIPT = """#!/usr/bin/env sh
# Marzneshin Agent OS — Two-Key Pre-Commit Gate
echo "============================================================"
echo "  MARZNESHIN OS — AUTONOMOUS TWO-KEY PRE-COMMIT GATE"
echo "============================================================"
python scripts/verify.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ Pre-commit validation failed (6/6 checks not met)! Commit aborted."
  exit 1
fi
echo "✅ All 6/6 checks passed. Proceeding with commit."
exit 0
"""

PRE_PUSH_SCRIPT = """#!/usr/bin/env sh
# Marzneshin Agent OS — Two-Key Pre-Push Gate
echo "============================================================"
echo "  MARZNESHIN OS — AUTONOMOUS TWO-KEY PRE-PUSH GATE"
echo "============================================================"
python scripts/verify.py
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
  echo "❌ Pre-push validation failed (6/6 checks not met)! Push aborted."
  exit 1
fi
echo "✅ Pre-push validation verified. Proceeding with push."
exit 0
"""


def install_hooks():
    if not HOOKS_DIR.exists():
        print(f"❌ .git/hooks directory not found at {HOOKS_DIR}")
        sys.exit(1)

    pre_commit_path = HOOKS_DIR / "pre-commit"
    pre_push_path = HOOKS_DIR / "pre-push"

    pre_commit_path.write_text(PRE_COMMIT_SCRIPT, encoding="utf-8")
    pre_push_path.write_text(PRE_PUSH_SCRIPT, encoding="utf-8")

    try:
        pre_commit_path.chmod(0o755)
        pre_push_path.chmod(0o755)
    except Exception:
        pass

    print("============================================================")
    print("  MARZNESHIN OS — GIT HOOKS INSTALLED SUCCESSFULLY")
    print("============================================================")
    print(f"  [OK] Installed pre-commit: {pre_commit_path}")
    print(f"  [OK] Installed pre-push:   {pre_push_path}")
    print("  All local commits and pushes are now automatically guarded.")
    print("============================================================")


if __name__ == "__main__":
    install_hooks()
