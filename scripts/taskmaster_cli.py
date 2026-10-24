#!/usr/bin/env python3
"""Task Master AI Orchestration Engine for Claude Code (Khairallah 2026 Stack Tool #18).

Bridges high-level PRDs / Specifications into structured, dependency-aware tasks.json
pipelines with rigorous acceptance criteria and Two-Key verification integration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib import clock
from lib.atomic import write_text_atomic
from lib.paths import state_dir

TASKS_FILE = state_dir() / "tasks.json"

def _load_tasks_data() -> Dict[str, Any]:
    if not TASKS_FILE.exists():
        return {"version": "1.0", "updated_at": clock.iso(), "tasks": []}
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "tasks" not in data:
                return {"version": "1.0", "updated_at": clock.iso(), "tasks": []}
            return data
    except Exception:
        return {"version": "1.0", "updated_at": clock.iso(), "tasks": []}

def _save_tasks_data(data: Dict[str, Any]) -> None:
    data["updated_at"] = clock.iso()
    raw = json.dumps(data, indent=2) + "\n"
    write_text_atomic(TASKS_FILE, raw)

def parse_prd_into_tasks(content: str, source_name: str = "prd") -> List[Dict[str, Any]]:
    """Parse a markdown PRD / Spec into sequential structured tasks with dependencies."""
    tasks: List[Dict[str, Any]] = []
    lines = content.splitlines()
    current_title = ""
    current_desc: List[str] = []
    current_criteria: List[str] = []
    task_idx = 1

    for line in lines:
        stripped = line.strip()
        # Headings indicating tasks or components
        if re.match(r"^#{2,4}\s+(Task\s+\d+|Step\s+\d+|Phase\s+\d+|\[MODIFY\]|\[NEW\]|[\d\.\-\)]+\s+.+)", stripped, re.IGNORECASE):
            if current_title:
                dep = [f"TASK-{task_idx-1:02d}"] if task_idx > 1 else []
                tasks.append({
                    "id": f"TASK-{task_idx:02d}",
                    "title": current_title,
                    "description": " ".join(current_desc).strip(),
                    "depends_on": dep,
                    "acceptance_criteria": current_criteria.copy() or ["Code and tests pass verification."],
                    "status": "pending",
                    "created_at": clock.iso(),
                    "completed_at": None,
                    "receipt_id": None
                })
                task_idx += 1
                current_desc = []
                current_criteria = []
            current_title = re.sub(r"^#{2,4}\s+", "", stripped)
        elif stripped.startswith("- [ ]") or stripped.startswith("* [ ]"):
            crit = stripped[5:].strip()
            if crit:
                current_criteria.append(crit)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullet = stripped[2:].strip()
            if current_title:
                current_desc.append(bullet)
        elif current_title and stripped and not stripped.startswith("#"):
            current_desc.append(stripped)

    # Append trailing task
    if current_title:
        dep = [f"TASK-{task_idx-1:02d}"] if task_idx > 1 else []
        tasks.append({
            "id": f"TASK-{task_idx:02d}",
            "title": current_title,
            "description": " ".join(current_desc).strip(),
            "depends_on": dep,
            "acceptance_criteria": current_criteria.copy() or ["Code and tests pass verification."],
            "status": "pending",
            "created_at": clock.iso(),
            "completed_at": None,
            "receipt_id": None
        })

    # If document had no explicit sections, create a baseline task
    if not tasks:
        tasks.append({
            "id": "TASK-01",
            "title": f"Implementation of {source_name}",
            "description": content[:500].strip(),
            "depends_on": [],
            "acceptance_criteria": ["All verification checks pass."],
            "status": "pending",
            "created_at": clock.iso(),
            "completed_at": None,
            "receipt_id": None
        })

    return tasks

def cmd_init(args: argparse.Namespace) -> int:
    source = args.source
    content = ""
    source_name = "PRD"
    if source:
        p = Path(source)
        if not p.is_absolute():
            p = WORKSPACE_ROOT / p
        if not p.exists():
            print(f"Error: Specification file not found at {p}", file=sys.stderr)
            return 1
        content = p.read_text(encoding="utf-8")
        source_name = p.name
    else:
        # Check standard default specs
        for candidate in [WORKSPACE_ROOT / "implementation_plan.md", WORKSPACE_ROOT / "BUILD-SPEC.md"]:
            if candidate.exists():
                content = candidate.read_text(encoding="utf-8")
                source_name = candidate.name
                break

    if not content:
        print("Error: No PRD or spec content found to parse.", file=sys.stderr)
        return 1

    tasks = parse_prd_into_tasks(content, source_name)
    data = {"version": "1.0", "source": source_name, "updated_at": clock.iso(), "tasks": tasks}
    _save_tasks_data(data)
    print(f"Successfully initialized Task Master with {len(tasks)} tasks from {source_name}.")
    for t in tasks:
        dep_str = f" (depends on {', '.join(t['depends_on'])})" if t['depends_on'] else ""
        print(f"  [{t['id']}] {t['title']}{dep_str}")
    return 0

def cmd_list(args: argparse.Namespace) -> int:
    data = _load_tasks_data()
    tasks = data.get("tasks", [])
    if not tasks:
        print("No tasks configured. Run `python3 scripts/taskmaster_cli.py init <spec>` to initialize.")
        return 0

    print("Task Master AI â€” Structured Task Pipeline")
    print("=" * 70)
    for t in tasks:
        status = t.get("status", "pending").upper()
        icon = "[ ]"
        if status == "COMPLETED":
            icon = "[x]"
        elif status == "IN_PROGRESS":
            icon = "[*]"
        elif status == "BLOCKED":
            icon = "[!]"
        deps = f" (deps: {', '.join(t.get('depends_on', []))})" if t.get('depends_on') else ""
        print(f"{icon} {t['id']} [{status:<11}] {t['title']}{deps}")
    return 0

def cmd_next(args: argparse.Namespace) -> int:
    data = _load_tasks_data()
    tasks = data.get("tasks", [])
    completed_ids = {t["id"] for t in tasks if t.get("status") == "completed"}

    ready_task: Optional[Dict[str, Any]] = None
    for t in tasks:
        if t.get("status") in ("pending", "in_progress"):
            deps = t.get("depends_on", [])
            if all(dep in completed_ids for dep in deps):
                ready_task = t
                break

    if not ready_task:
        if tasks and len(completed_ids) == len(tasks):
            print("ALL_TASKS_COMPLETED: Every task in the pipeline has been verified and completed.")
        else:
            print("NO_READY_TASKS: Remaining tasks are blocked by pending dependencies.")
        return 0

    print(f"NEXT_TASK: {ready_task['id']}")
    print(f"Title: {ready_task['title']}")
    print(f"Status: {ready_task['status']}")
    if ready_task.get("description"):
        print(f"Description: {ready_task['description']}")
    if ready_task.get("acceptance_criteria"):
        print("Acceptance Criteria:")
        for c in ready_task["acceptance_criteria"]:
            print(f"  - {c}")
    return 0

def cmd_start(args: argparse.Namespace) -> int:
    data = _load_tasks_data()
    task_id = args.id.upper()
    found = False
    for t in data.get("tasks", []):
        if t["id"].upper() == task_id:
            t["status"] = "in_progress"
            found = True
            break
    if not found:
        print(f"Error: Task {task_id} not found.", file=sys.stderr)
        return 1
    _save_tasks_data(data)
    print(f"Task {task_id} is now IN_PROGRESS.")
    return 0

def cmd_complete(args: argparse.Namespace) -> int:
    data = _load_tasks_data()
    task_id = args.id.upper()
    found = False
    for t in data.get("tasks", []):
        if t["id"].upper() == task_id:
            t["status"] = "completed"
            t["completed_at"] = clock.iso()
            if args.receipt:
                t["receipt_id"] = args.receipt
            found = True
            break
    if not found:
        print(f"Error: Task {task_id} not found.", file=sys.stderr)
        return 1
    _save_tasks_data(data)
    print(f"Task {task_id} marked as COMPLETED.")
    return 0

def cmd_status(args: argparse.Namespace) -> int:
    data = _load_tasks_data()
    tasks = data.get("tasks", [])
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    in_prog = sum(1 for t in tasks if t.get("status") == "in_progress")
    pending = sum(1 for t in tasks if t.get("status") == "pending")

    if args.json:
        print(json.dumps({
            "total": total,
            "completed": completed,
            "in_progress": in_prog,
            "pending": pending,
            "progress_pct": round((completed / total * 100) if total else 0, 1)
        }, indent=2))
    else:
        pct = round((completed / total * 100) if total else 0, 1)
        print(f"Task Master Status: {completed}/{total} tasks completed ({pct}%). In-progress: {in_prog}, Pending: {pending}")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Task Master AI Structured Pipeline CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_init = subparsers.add_parser("init", help="Initialize tasks from PRD/spec")
    p_init.add_argument("source", nargs="?", default="", help="Path to markdown PRD / Spec")
    p_init.set_defaults(func=cmd_init)

    p_list = subparsers.add_parser("list", help="List all tasks and statuses")
    p_list.set_defaults(func=cmd_list)

    p_next = subparsers.add_parser("next", help="Get next ready task with acceptance criteria")
    p_next.set_defaults(func=cmd_next)

    p_start = subparsers.add_parser("start", help="Mark task as in-progress")
    p_start.add_argument("id", help="Task ID (e.g. TASK-01)")
    p_start.set_defaults(func=cmd_start)

    p_complete = subparsers.add_parser("complete", help="Mark task as completed")
    p_complete.add_argument("id", help="Task ID (e.g. TASK-01)")
    p_complete.add_argument("--receipt", help="Optional verification receipt ID")
    p_complete.set_defaults(func=cmd_complete)

    p_status = subparsers.add_parser("status", help="Get summary status")
    p_status.add_argument("--json", action="store_true", help="Output JSON")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())