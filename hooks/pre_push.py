#!/usr/bin/env python3
"""PrePush hook (BUILD-SPEC §7.2, class B <90s).

The heavy gate that cannot fit in 3 seconds (G9): full unit suite, schema
validation, receipt chain, event-gap scan, import and clock lints. Everything
here is local; network stays out of hooks.

Fails (exit != 0) when any of it is red. A red class-B gate blocks the push —
that is the point of having two classes.
"""

from __future__ import annotations

import subprocess
import sys
import time

import _common as H

BUDGET_SECONDS = 90


def _run(label: str, argv: list[str], timeout: int) -> tuple[bool, str]:
    try:
        out = subprocess.run(argv, cwd=H.REPO_ROOT, capture_output=True, text=True,
                             timeout=timeout)
        tail = (out.stdout + out.stderr).strip().splitlines()
        return out.returncode == 0, "\n".join(tail[-6:])
    except subprocess.TimeoutExpired:
        return False, f"{label} exceeded {timeout}s"
    except OSError as exc:
        return False, f"{label} could not start: {exc}"


def main() -> None:
    H.read_stdin()
    started = time.monotonic()
    py = sys.executable
    failures: list[str] = []

    checks = [
        ("unit suite", [py, "-m", "unittest", "discover", "-s", "tests"], 45),
        ("verify --all", [py, "scripts/verify.py", "--all"], 30),
    ]
    for label, argv, timeout in checks:
        ok, tail = _run(label, argv, timeout)
        if not ok:
            failures.append(f"{label} FAILED:\n{tail}")

    elapsed = time.monotonic() - started
    if failures:
        H.block("class-B gate red (pre-push):\n" + "\n\n".join(failures),
                event_type="verify.failed", subject_kind="push", subject_id="pre_push",
                payload={"elapsed_s": round(elapsed, 1)})

    H.emit("verify.passed", "push", "pre_push",
           {"elapsed_s": round(elapsed, 1), "budget_s": BUDGET_SECONDS})
    H.allow()


if __name__ == "__main__":
    main()
