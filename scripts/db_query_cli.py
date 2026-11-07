#!/usr/bin/env python3
"""Natural Language & SQLite Database Inspector (Khairallah Stack Tool #43 Vanna AI / NL-SQL).

Provides safe, read-only inspection of LangGraph state checkpoints and SQLite databases
in Marzneshin Agent OS with schema discovery and structured tabular rendering.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib import clock
from lib.paths import repo_root

DEFAULT_DBS = [
    repo_root() / "state" / "langgraph_checkpoints.sqlite",
    repo_root() / "data" / "state_store.db"
]


def resolve_db_path(arg_path: Optional[str]) -> Path:
    if arg_path:
        p = Path(arg_path)
        if not p.is_absolute():
            p = repo_root() / p
        return p
    for candidate in DEFAULT_DBS:
        if candidate.exists():
            return candidate
    return DEFAULT_DBS[0]


def get_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_tables(args: argparse.Namespace) -> int:
    db = resolve_db_path(args.db)
    print(f"Inspecting SQLite Database: {db.name} ({db})")
    print("=" * 70)
    try:
        conn = get_connection(db)
    except Exception as e:
        print(f"Error opening database: {e}", file=sys.stderr)
        return 1

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r["name"] for r in cur.fetchall()]

    if not tables:
        print("No user tables found in database.")
        return 0

    print(f"{'Table Name':<35} | {'Row Count':<12} | {'Columns'}")
    print("-" * 70)
    for tbl in tables:
        try:
            cnt_row = cur.execute(f"SELECT COUNT(*) as c FROM \"{tbl}\"").fetchone()
            cnt = cnt_row["c"] if cnt_row else 0
            cols_info = cur.execute(f"PRAGMA table_info(\"{tbl}\")").fetchall()
            cols = len(cols_info)
            print(f"{tbl:<35} | {cnt:<12} | {cols} cols")
        except Exception as e:
            print(f"{tbl:<35} | ERROR: {e}")
    print("=" * 70)
    return 0


def cmd_schema(args: argparse.Namespace) -> int:
    db = resolve_db_path(args.db)
    table_name = args.table
    conn = get_connection(db)
    cur = conn.cursor()
    cols = cur.execute(f"PRAGMA table_info(\"{table_name}\")").fetchall()
    if not cols:
        print(f"Table '{table_name}' not found or empty schema in {db.name}.")
        return 1

    print(f"Schema for '{table_name}' in {db.name}")
    print("=" * 65)
    print(f"{'CID':<5} | {'Column Name':<25} | {'Type':<15} | {'NotNull':<8} | {'PK'}")
    print("-" * 65)
    for c in cols:
        pk = "YES" if c["pk"] else "-"
        nn = "YES" if c["notnull"] else "NO"
        print(f"{c['cid']:<5} | {c['name']:<25} | {c['type'] or 'TEXT':<15} | {nn:<8} | {pk}")
    print("=" * 65)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    query = args.sql.strip()
    # Safety gate: block mutating operations
    forbidden = r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|VACUUM|ATTACH|DETACH|REPLACE)\b"
    if re.search(forbidden, query, re.IGNORECASE):
        print("ERROR: Mutating statements are rejected. db_query_cli is strictly READ-ONLY.", file=sys.stderr)
        return 1

    db = resolve_db_path(args.db)
    conn = get_connection(db)
    cur = conn.cursor()
    try:
        cur.execute(query)
        rows = cur.fetchall()
    except Exception as e:
        print(f"SQL Error: {e}", file=sys.stderr)
        return 1

    if not rows:
        print("Query returned 0 rows.")
        return 0

    col_names = [d[0] for d in cur.description]
    if args.json:
        dict_rows = [dict(r) for r in rows]
        print(json.dumps(dict_rows, indent=2))
        return 0

    # Tabular print
    header = " | ".join(f"{c:<18}" for c in col_names)
    print(header)
    print("-" * len(header))
    for r in rows[: args.limit]:
        line = " | ".join(f"{str(r[c])[:17]:<18}" for c in col_names)
        print(line)
    if len(rows) > args.limit:
        print(f"... and {len(rows) - args.limit} more rows (use --limit to expand).")
    return 0


def cmd_checkpoints(args: argparse.Namespace) -> int:
    db = resolve_db_path(args.db)
    conn = get_connection(db)
    cur = conn.cursor()
    try:
        cur.execute("SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT ?", (args.limit,))
        rows = cur.fetchall()
        print(f"Recent LangGraph Checkpoints in {db.name} (Limit: {args.limit})")
        print("=" * 80)
        print(f"{'Thread ID':<24} | {'Namespace':<15} | {'Checkpoint ID'}")
        print("-" * 80)
        for r in rows:
            print(f"{str(r['thread_id'])[:23]:<24} | {str(r['checkpoint_ns'])[:14]:<15} | {str(r['checkpoint_id'])}")
        print("=" * 80)
    except Exception as e:
        print(f"Checkpoints query error: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Natural Language & SQLite Database Inspector")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_tables = subparsers.add_parser("tables", help="List all tables and row counts")
    p_tables.add_argument("--db", help="Path to SQLite database")
    p_tables.set_defaults(func=cmd_tables)

    p_schema = subparsers.add_parser("schema", help="Show table column schema")
    p_schema.add_argument("table", help="Table name")
    p_schema.add_argument("--db", help="Path to SQLite database")
    p_schema.set_defaults(func=cmd_schema)

    p_query = subparsers.add_parser("query", help="Execute read-only SQL query")
    p_query.add_argument("sql", help="SQL SELECT query")
    p_query.add_argument("--db", help="Path to SQLite database")
    p_query.add_argument("--limit", type=int, default=20, help="Max rows to display")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")
    p_query.set_defaults(func=cmd_query)

    p_cp = subparsers.add_parser("checkpoints", help="List recent LangGraph checkpoints")
    p_cp.add_argument("--db", help="Path to SQLite database")
    p_cp.add_argument("--limit", type=int, default=10, help="Max checkpoints to show")
    p_cp.set_defaults(func=cmd_checkpoints)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())