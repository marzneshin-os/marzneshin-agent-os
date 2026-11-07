#!/usr/bin/env python3
"""PostToolUse hook (BUILD-SPEC §7.2, class A <3s).

Fails (exit != 0) when:
  - the tool result contains a secret (I6 — it is already in the transcript,
    so the hook flags it loudly AND records the redaction gap)
  - an untrusted-data envelope is opened but never closed (§15.2: stripped
    boundaries turn data back into instructions)

Deny-only event emission, same rationale as pre_tool (ADR-003 D19).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import _common as H
from lib import redact


def run_auto_formatter(data: dict) -> None:
    """Boris Cherny PostToolUse auto-formatting pattern.
    Runs ruff format on edited python files with a strict sub-second budget.
    """
    tool = data.get("tool_name", "")
    if tool not in ("replace_file_content", "multi_replace_file_content", "write_to_file", "Edit", "Write"):
        return

    tool_input = data.get("tool_input") or {}
    filepath_str = tool_input.get("TargetFile") or tool_input.get("file_path") or tool_input.get("path")
    if not filepath_str:
        return

    p = Path(filepath_str)
    if p.suffix == ".py" and p.exists():
        ruff_bin = Path(H.REPO_ROOT) / ".venv" / "bin" / "ruff"
        cmd = [str(ruff_bin) if ruff_bin.exists() else "ruff", "format", str(p)]
        try:
            subprocess.run(cmd, capture_output=True, timeout=1.5)
        except Exception:
            pass


def main() -> None:
    data = H.read_stdin()
    tool = data.get("tool_name", "")
    response = data.get("tool_response", "")
    text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    if len(text) > 200_000:  # huge outputs: scan the ends, where secrets surface
        text = text[:100_000] + text[-100_000:]

    scan = redact.scan_text(text)
    if not scan.clean:
        kinds = ", ".join(sorted({f.kind for f in scan.findings}))
        H.block(f"secret detected in {tool} output ({kinds}). The value is already in "
                f"the transcript: treat it as exposed — rotate it, and do not persist "
                f"it anywhere (I6).",
                event_type="policy.denied", subject_kind="tool", subject_id=tool,
                payload={"findings": [f.kind for f in scan.findings], "stage": "post"})

    opens = text.count("<<UNTRUSTED_DATA")
    closes = text.count("<<END_UNTRUSTED_DATA>>")
    if opens > closes:
        H.block(f"{tool} output contains an unterminated UNTRUSTED_DATA envelope "
                f"({opens} open vs {closes} closed). A stripped boundary turns data "
                f"back into instructions (§15.2).",
                subject_kind="tool", subject_id=tool)

    # Auto-format edited files
    run_auto_formatter(data)

    try:
        from lib import agentmemory
        redacted_data = redact.redact_obj({"tool": tool, "response": response})
        agentmemory.call_mcp_tool("memory_save", {"content": f"Tool call {tool} result: {json.dumps(redacted_data, ensure_ascii=False)}"})
    except Exception:
        pass

    H.allow()


if __name__ == "__main__":
    main()
