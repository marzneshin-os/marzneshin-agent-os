#!/usr/bin/env python3
"""
ask_fable.py - Fable 5.1 Orchestration Runner
Supports Windows and Linux/WSL environments.
Calls Claude Code Router (CCR) or direct Google Gemini/OpenRouter to generate structured task graphs.
"""

import sys
import os
import json
import urllib.request
import urllib.error

def main():
    if len(sys.argv) > 1:
        packet = " ".join(sys.argv[1:])
    else:
        packet = sys.stdin.read()

    packet = packet.strip()
    if not packet:
        print("Error: Provide a non-empty orchestration packet on stdin or as arguments.", file=sys.stderr)
        sys.exit(64)

    system_prompt = (
        "You are Claude Fable 5.1, the orchestration controller. You plan and adjudicate only; "
        "never assign yourself implementation. Use only the supplied packet. Return a concise executable "
        "task graph, not implementation. For each node specify: id, purpose, dependencies, recommended model "
        "or agent type, exclusive file or responsibility ownership, expected output, verification, and stop "
        "condition. Identify nodes safe to run in parallel. Minimize the number of agents. Preserve the user "
        "scope and approval boundaries. End with an integration and final-verification node. Do not expose "
        "chain-of-thought; provide decisions and brief rationale only.\n\n"
        "Start the answer with one short line per ready assignment in the form: Agent — Model: bounded responsibility."
    )

    models = [
        "Google Gemini (AI Studio)/gemini-3.7-flash",
        "Google Gemini (AI Studio)/gemini-3.8-flash",
        "Google Gemini (AI Studio)/gemini-3.6-flash",
        "OpenRouter/openrouter/free"
    ]

    headers = {
        "Content-Type": "application/json",
        "x-api-key": os.environ.get("CCR_API_KEY", "ccr-profile-J486MkbbgmnFle9heLnGD9sPcvPO9p-k"),
        "anthropic-version": "2023-06-01"
    }

    # 1. Try CCR on localhost:3456
    for model in models:
        payload = {
            "model": model,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [{"role": "user", "content": packet}]
        }
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:3456/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = "".join(b.get("text", "") for b in data.get("content", []))
                if text.strip():
                    print(f"Fable 5.1 speaks ({model}):\n\n{text.strip()}")
                    return
        except Exception:
            continue

    # 2. Offline fallback if gateway is unreachable
    print("Fable 5.1 speaks (offline fallback):\n\n"
          "Agent Implementation — Default Model: Core feature execution.\n"
          "Agent QA — Default Model: Test suite verification.\n\n"
          "### Execution Task Graph\n"
          "- [Node 1: Scaffolding & Interfaces] -> Dependencies: None\n"
          "- [Node 2: Implementation & Logic] -> Dependencies: Node 1\n"
          "- [Node 3: Integration & Tests] -> Dependencies: Node 2\n")

if __name__ == "__main__":
    main()
