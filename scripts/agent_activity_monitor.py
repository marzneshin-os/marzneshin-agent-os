#!/usr/bin/env python3
"""
agent_activity_monitor.py — Real-time Multi-Agent Activity Monitor for Antigravity IDE & 2.0.

Provides live visibility into agent & subagent actions, thinking streams,
and tool calls (similar to Claude Code's concurrent agent view).

Usage:
    python scripts/agent_activity_monitor.py [--cid CONVERSATION_ID] [--no-follow]
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import clock

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ANSI Color Codes for terminal styling
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

def get_brain_dir() -> Path:
    win_path = Path(os.environ.get("USERPROFILE", "C:/Users/Asus")) / ".gemini" / "antigravity-ide" / "brain"
    if win_path.exists():
        return win_path
    linux_path = Path.home() / ".gemini" / "antigravity-ide" / "brain"
    if linux_path.exists():
        return linux_path
    return win_path

def find_latest_conversation(brain_dir: Path) -> Path | None:
    if not brain_dir.exists():
        return None
    conv_dirs = [d for d in brain_dir.iterdir() if d.is_dir() and (d / ".system_generated" / "logs" / "transcript.jsonl").exists()]
    if not conv_dirs:
        return None
    conv_dirs.sort(key=lambda d: (d / ".system_generated" / "logs" / "transcript.jsonl").stat().st_mtime, reverse=True)
    return conv_dirs[0]

def format_tool_call(tool_call: dict) -> str:
    name = tool_call.get("name", "unknown")
    args = tool_call.get("args", {})
    summary = ""
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            pass
    if isinstance(args, dict):
        tool_summary = args.get("toolSummary") or args.get("toolAction")
        if tool_summary:
            summary = f" -> {tool_summary}"
        elif "CommandLine" in args:
            cmd = args.get("CommandLine", "")
            summary = f" -> `{cmd[:60]}...`" if len(cmd) > 60 else f" -> `{cmd}`"
        elif "TargetFile" in args or "AbsolutePath" in args:
            fpath = args.get("TargetFile") or args.get("AbsolutePath")
            summary = f" -> {Path(fpath).name}"
    return f"{Colors.CYAN}{Colors.BOLD}[Tool]{Colors.RESET} {Colors.YELLOW}{name}{Colors.RESET}{summary}"

def monitor_transcript(transcript_path: Path, follow: bool = True):
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}   Antigravity IDE - Multi-Agent Live Activity Monitor (Claude-Style) {Colors.RESET}")
    print(f"{Colors.HEADER}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.DIM}Target Transcript: {transcript_path}{Colors.RESET}\n")

    seen_steps = set()
    
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        while True:
            line = f.readline()
            if not line:
                if not follow:
                    break
                clock.sleep(0.5)
                continue
            
            line = line.strip()
            if not line:
                continue
                
            try:
                entry = json.loads(line)
            except Exception:
                continue
                
            step_idx = entry.get("step_index")
            if step_idx is not None and step_idx in seen_steps:
                continue
            if step_idx is not None:
                seen_steps.add(step_idx)

            source = entry.get("source", "")
            step_type = entry.get("type", "")
            status = entry.get("status", "")
            thinking = entry.get("thinking", "")
            tool_calls = entry.get("tool_calls", [])
            content = entry.get("content", "")
            
            timestamp = clock.now().strftime("%H:%M:%S")

            step_label = f"STEP {step_idx}" if step_idx is not None else "EVENT"
            status_color = Colors.GREEN if status == "DONE" else Colors.YELLOW
            print(f"{Colors.BOLD}[{timestamp}] [{Colors.BLUE}{step_label}{Colors.RESET}{Colors.BOLD}] [{status_color}{status}{Colors.RESET}{Colors.BOLD}]{Colors.RESET}")

            if thinking:
                clean_thinking = thinking.strip().replace("\n", " ")
                if len(clean_thinking) > 160:
                    clean_thinking = clean_thinking[:160] + "..."
                print(f"  {Colors.DIM}[Thinking]{Colors.RESET} {clean_thinking}")

            for tc in tool_calls:
                t_name = tc.get("name", "")
                if "subagent" in t_name or "invoke" in t_name:
                    print(f"  {Colors.GREEN}{Colors.BOLD}>>> [SUBAGENT DISPATCH]{Colors.RESET} {format_tool_call(tc)}")
                else:
                    print(f"  {format_tool_call(tc)}")

            if step_type == "BROWSER_SUBAGENT":
                print(f"  {Colors.GREEN}{Colors.BOLD}[Browser Subagent Finished Work]{Colors.RESET}")
            elif step_type == "USER_INPUT":
                first_line = content.strip().split("\n")[0]
                print(f"  {Colors.YELLOW}[User Input]:{Colors.RESET} {first_line[:90]}...")

            print()

def main():
    parser = argparse.ArgumentParser(description="Live monitor for Antigravity subagents and agents.")
    parser.add_argument("--cid", type=str, help="Specific conversation ID to monitor")
    parser.add_argument("--no-follow", action="store_true", help="Do not follow live updates (exit at EOF)")
    args = parser.parse_args()

    brain_dir = get_brain_dir()
    if args.cid:
        target_dir = brain_dir / args.cid
    else:
        target_dir = find_latest_conversation(brain_dir)

    if not target_dir or not target_dir.exists():
        print(f"{Colors.RED}No active conversation found in {brain_dir}{Colors.RESET}")
        sys.exit(1)

    transcript_file = target_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if not transcript_file.exists():
        print(f"{Colors.RED}Transcript file not found at {transcript_file}{Colors.RESET}")
        sys.exit(1)

    monitor_transcript(transcript_file, follow=not args.no_follow)

if __name__ == "__main__":
    main()
