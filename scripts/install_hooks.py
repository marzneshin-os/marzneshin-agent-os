#!/usr/bin/env python3
"""Install owned Git hooks that run the Two-Key verification gate."""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PROJECT_ROOT / ".git" / "hooks"
MANAGED_MARKERS = {
    "pre-commit": {
        "# Marzneshin Agent OS — Two-Key Pre-Commit Gate",
        "# marzneshin-agent-os managed two-key hook:pre-commit:v1",
    },
    "pre-push": {
        "# Marzneshin Agent OS — Two-Key Pre-Push Gate",
        "# marzneshin-agent-os managed two-key hook:pre-push:v1",
    },
}

PRE_COMMIT_SCRIPT = """#!/usr/bin/env sh
# marzneshin-agent-os managed two-key hook:pre-commit:v1
echo "MARZNESHIN OS — TWO-KEY PRE-COMMIT GATE"
python scripts/two_key_gate.py run
EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
  echo "Pre-commit Two-Key verification failed; commit aborted."
  exit 1
fi
exit 0
"""

PRE_PUSH_SCRIPT = """#!/usr/bin/env sh
# marzneshin-agent-os managed two-key hook:pre-push:v1
echo "MARZNESHIN OS — TWO-KEY PRE-PUSH GATE"
python scripts/two_key_gate.py run
EXIT_CODE=$?
if [ "$EXIT_CODE" -ne 0 ]; then
  echo "Pre-push Two-Key verification failed; push aborted."
  exit 1
fi
exit 0
"""


def install_hooks(hooks_dir=HOOKS_DIR):
    hooks_dir = Path(hooks_dir)
    if not hooks_dir.is_dir():
        print(f"[ERROR] Git hooks directory not found: {hooks_dir}", file=sys.stderr)
        return 1

    scripts = {
        hooks_dir / "pre-commit": PRE_COMMIT_SCRIPT,
        hooks_dir / "pre-push": PRE_PUSH_SCRIPT,
    }
    for path in scripts:
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            print(f"[ERROR] Cannot safely inspect existing hook {path}: {error}", file=sys.stderr)
            return 1
        if not any(marker in content for marker in MANAGED_MARKERS[path.name]):
            print(f"[ERROR] Existing custom hook preserved: {path}", file=sys.stderr)
            return 1

    try:
        for path, content in scripts.items():
            path.write_text(content, encoding="utf-8")
            try:
                path.chmod(0o755)
            except OSError:
                pass
    except OSError as error:
        print(f"[ERROR] Failed to install Git hooks: {error}", file=sys.stderr)
        return 1

    print("[OK] Installed pre-commit and pre-push Two-Key gates.")
    return 0


if __name__ == "__main__":
    sys.exit(install_hooks())
