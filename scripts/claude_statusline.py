#!/usr/bin/env python3
"""Claude Code Statusline Generator (Sub-second status output).
Outputs a clean, rich status string for Claude Code's terminal statusLine.
Now includes real-time session cost and tokens tracking.
"""
import json
import select
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

def get_git_branch() -> str:
    try:
        res = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=REPO_ROOT, capture_output=True, text=True, timeout=0.3)
        return res.stdout.strip() or 'unknown'
    except Exception:
        return 'detached'

def get_killswitch_status() -> str:
    kill_file = REPO_ROOT / 'state' / 'KILL'
    if not kill_file.exists():
        return '🟢 RUNNING'
    try:
        data = json.loads(kill_file.read_text(encoding='utf-8'))
        if data.get('entries'):
            return '🛑 KILLED'
        return '🟢 RUNNING'
    except Exception:
        return '⚠️ UNKNOWN'

def get_reason_network_status() -> str:
    sock = Path.home() / '.reason' / 'network' / 'network.sock'
    if sock.exists():
        return '🌐 Reason: Online'
    return '🌐 Reason: Off'

def get_claude_telemetry() -> dict:
    telemetry = {}
    if not sys.stdin.isatty():
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if r:
                raw = sys.stdin.read()
                if raw.strip():
                    telemetry = json.loads(raw)
                    try:
                        cache_path = REPO_ROOT / 'state' / 'claude_session_telemetry.json'
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_text(json.dumps(telemetry, indent=2), encoding='utf-8')
                    except Exception:
                        pass
        except Exception:
            pass

    if not telemetry:
        try:
            cache_path = REPO_ROOT / 'state' / 'claude_session_telemetry.json'
            if cache_path.exists():
                telemetry = json.loads(cache_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    return telemetry

def main() -> None:
    branch = get_git_branch()
    ks = get_killswitch_status()
    rn = get_reason_network_status()
    telemetry = get_claude_telemetry()

    cost_usd = telemetry.get('cost', {}).get('total_cost_usd', 0.0)
    in_tok = telemetry.get('context_window', {}).get('total_input_tokens', 0)
    out_tok = telemetry.get('context_window', {}).get('total_output_tokens', 0)
    used_pct = telemetry.get('context_window', {}).get('used_percentage')

    cost_str = f"💰 ${cost_usd:.2f}"
    total_tokens = in_tok + out_tok
    if total_tokens >= 1000:
        tok_str = f"🪙 {total_tokens // 1000}k tok"
    else:
        tok_str = f"🪙 {total_tokens} tok"

    if used_pct is not None:
        tok_str += f" ({int(used_pct)}% ctx)"

    print(f"⚡ Marzneshin OS | 🌿 {branch} | {cost_str} | {tok_str} | {ks} | {rn} | 🛡️ Two-Key: Active")

if __name__ == '__main__':
    main()
