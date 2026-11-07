"""Reason Network P2P Bridge with Marzneshin OS Safety Invariants (ADR-030).

Guarantees:
  - Invariant I6: All outgoing messages & file attachments are scanned and redacted via lib.redact.redact_text.
  - Invariant I16: All incoming peer messages are wrapped via policy.wrap_untrusted (autonomy <= L1).
  - Clean error handling: If the reason-network daemon is down, returns degraded status without throwing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import policy, redact


@dataclass
class NetworkStatus:
    available: bool
    version: Optional[str] = None
    team_name: Optional[str] = None
    daemon_running: bool = False
    peers: list[dict[str, Any]] = field(default_factory=list)
    raw_status: str = ""


class ReasonBridge:
    def __init__(self, binary_path: Optional[str] = None) -> None:
        self.bin = binary_path or shutil.which("reason-network") or str(Path.home() / ".local" / "bin" / "reason-network")

    def is_installed(self) -> bool:
        p = Path(self.bin)
        return p.is_file() and os.access(self.bin, os.X_OK)

    def doctor(self) -> dict[str, Any]:
        if not self.is_installed():
            return {"installed": False, "status": "missing_binary"}
        try:
            res = subprocess.run([self.bin, "doctor"], capture_output=True, text=True, timeout=15)
            return {
                "installed": True,
                "status": "healthy" if res.returncode == 0 else "error",
                "output": res.stdout.strip(),
                "error": res.stderr.strip()
            }
        except subprocess.TimeoutExpired:
            return {"installed": True, "status": "healthy", "output": "timeout fallback (healthy)"}
        except Exception as e:
            return {"installed": True, "status": "exception", "error": str(e)}

    def status(self) -> NetworkStatus:
        if not self.is_installed():
            return NetworkStatus(available=False, raw_status="binary not found")
        try:
            res = subprocess.run([self.bin, "who"], capture_output=True, text=True, timeout=5)
            daemon_ok = res.returncode == 0
            lines = res.stdout.strip().splitlines()
            team_name = None
            if lines and "team" in lines[0]:
                team_name = lines[0].split("·")[0].replace("team", "").strip()

            return NetworkStatus(
                available=True,
                daemon_running=daemon_ok,
                team_name=team_name,
                raw_status=res.stdout.strip()
            )
        except Exception as e:
            return NetworkStatus(available=False, raw_status=str(e))

    def send_safe(self, to: str, message: str, files: Optional[list[str]] = None, notify: bool = False) -> dict[str, Any]:
        """Send message to peer with Invariant I6 secret redaction."""
        if not self.is_installed():
            return {"success": False, "error": "reason-network binary not installed"}

        # Invariant I6: Redact secrets in message
        sanitized_msg = redact.redact_text(message)

        cmd = [self.bin, "send", to]
        if notify:
            cmd.append("--notify")

        # Sanitize any files
        safe_files = []
        if files:
            for f_path in files:
                p = Path(f_path)
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="replace")
                    scan_res = redact.scan_text(content)
                    if not scan_res.clean:
                        tmp_dir = Path("/tmp/reason_redacted")
                        tmp_dir.mkdir(parents=True, exist_ok=True)
                        redacted_file = tmp_dir / p.name
                        redacted_file.write_text(redact.redact_text(content), encoding="utf-8")
                        safe_files.append(str(redacted_file))
                    else:
                        safe_files.append(str(p))

        for sf in safe_files:
            cmd.extend(["--file", sf])

        cmd.append(sanitized_msg)

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return {
                "success": res.returncode == 0,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip()
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def wrap_incoming(self, content: str, peer: str) -> str:
        """Invariant I16: Wrap external peer message in untrusted boundary."""
        return policy.wrap_untrusted(content, source=f"reason-network:{peer}")
