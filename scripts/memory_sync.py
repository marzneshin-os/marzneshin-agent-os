#!/usr/bin/env python3
"""Sync immutable event log to AgentMemory SQLite database.

Allows rebuilding AgentMemory local db from the source of truth if deleted.
Supports single-run and continuous autonomous watch mode (--watch).
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from datetime import date
from pathlib import Path

# Add lib path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import events, agentmemory, clock

running = True

def signal_handler(signum, frame):
    global running
    running = False

def sync_events(seen_ids: set[str], start_date: date = None) -> int:
    """Sync new events to AgentMemory and update seen_ids."""
    if start_date is None:
        start_date = date(2024, 1, 1)
    end_date = clock.now().date()
    
    new_synced = 0
    errors = 0
    for ev in events.iter_range(start_date, end_date, world="prod"):
        ev_id = ev.get("event_id")
        if not ev_id or ev_id in seen_ids:
            continue
            
        t = ev.get("type", "")
        if t in ("task.completed", "decision.recorded", "receipt.written", "code.modified", "milestone.reached"):
            try:
                res = agentmemory.call_mcp_tool("memory_save", {"content": json.dumps(ev, ensure_ascii=False)})
                if res.startswith("AgentMemory error"):
                    errors += 1
                else:
                    seen_ids.add(ev_id)
                    new_synced += 1
            except Exception as e:
                errors += 1
                print(f"[memory_sync] Error syncing event {ev_id}: {e}")
        else:
            seen_ids.add(ev_id)
            
    return new_synced

def main():
    parser = argparse.ArgumentParser(description="Autonomous Event Sync to AgentMemory")
    parser.add_argument("--watch", action="store_true", help="Run continuously in background watching for new events")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds for watch mode")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    seen_ids: set[str] = set()
    print("[memory_sync] Initial historical sync to AgentMemory...")
    initial_count = sync_events(seen_ids, start_date=date(2024, 1, 1))
    print(f"[memory_sync] Initial sync complete. {initial_count} events indexed.")

    if not args.watch:
        return

    print(f"[memory_sync] Autonomous watch mode enabled. Monitoring events every {args.interval}s...")
    while running:
        try:
            clock.sleep(args.interval)
            # In watch mode, only scan today's date
            today = clock.now().date()
            new_count = sync_events(seen_ids, start_date=today)
            if new_count > 0:
                print(f"[memory_sync] Automatically captured and synced {new_count} new event(s).")
        except Exception as e:
            print(f"[memory_sync] Loop warning: {e}")
            clock.sleep(2)

    print("[memory_sync] Watcher stopped.")

if __name__ == "__main__":
    main()
