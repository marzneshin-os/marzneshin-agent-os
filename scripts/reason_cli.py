#!/usr/bin/env python3
"""Reason Network CLIWith Marzneshin Safety Invariants (1R-030)."""

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.reason_bridge import ReasonBridge


def main() -> int:
    parser = argparse.ArgumentParser(description="Reason Network P2P Mesh Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Get daemon and connection status")

    # who
    subparsers.add_parser("who", help="Show online agents and team members")

    # doctor
    subparsers.add_parser("doctor", help="Run diagnostic health check")

    # invite
    subparsers.add_parser("invite", help="Show invite link for new teammates/agents")

    # send
    send_p = subparsers.add_parser("send", help="Send a secret-redacted message to a peer agent")
    send_p.add_argument("to", type=str, help="Recipient session, e.g. alice/api-claude or *")
    send_p.add_argument("message", type=str, help="Message text")
    send_p.add_argument("--file", action="append", default=[], help="File attachment")
    send_p.add_argument("--notify", action="store_true", help="Pop up notification on recipient's screen")

    args = parser.parse_args()
    bridge = ReasonBridge()

    if args.command == "status":
        st = bridge.status()
        print(f"Available: {st.available}")
        print(f"Daemon Running: {st.daemon_running}")
        print(f"Team: {st.team_name or 'N/A'}")
        if st.raw_status:
            print(f"\nRaw Status:\n{st.raw_status}")
        return 0 if st.daemon_running else 1

    elif args.command == "who":
        res = subprocess.run([bridge.bin, "who"], check=False)
        return res.returncode

    elif args.command == "doctor":
        doc = bridge.doctor()
        print(f"Status: {doc.get('status')}")
        if doc.get("output"):
            print(doc["output"])
        if doc.get("error"):
            print(doc["error"], file=sys.stderr)
        return 0 if doc.get("status") == "healthy" else 1

    elif args.command == "invite":
        res = subprocess.run([bridge.bin, "invite"], check=False)
        return res.returncode


    elif args.command == "send":
        res = bridge.send_safe(to=args.to, message=args.message, files=args.file, notify=args.notify)
        if res["success"]:
            print(f" Message delivered to {args.to}")
            if res.get("stdout"):
                print(res["stdout"])
            return 0
        else:
            print(f"· Delivery failed: {res.get('error') or res.get('stderr')}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

