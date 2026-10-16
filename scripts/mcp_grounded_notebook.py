#!/usr/bin/env python3
"""Grounded Notebook Native MCP Server — JSON-RPC 2.0 stdio interface.

Exposes citation-grounded knowledge notebook capabilities (NotebookLM paradigm)
to agentic execution workflows (Antigravity paradigm) in Marzneshin Agent OS.
Governed by ADR-026.
"""

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.grounded_notebook import GroundedNotebook, NotebookStore

STORE = NotebookStore()

TOOLS = [
    {
        "name": "notebook_create",
        "description": "Create a new isolated, citation-grounded knowledge notebook for a task or topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique identifier for the notebook"},
                "title": {"type": "string", "description": "Human-readable title"},
                "description": {"type": "string", "description": "Optional notebook description", "default": ""},
            },
            "required": ["id", "title"],
        },
    },
    {
        "name": "notebook_ingest",
        "description": "Ingest workspace documents, specifications, or text into a grounded knowledge notebook with deterministic line-span chunking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Notebook identifier"},
                "file_path": {"type": "string", "description": "Optional path to a workspace file to ingest"},
                "content": {"type": "string", "description": "Optional raw text content to ingest"},
                "source_name": {"type": "string", "description": "Name of the source document for citation anchors", "default": "document.md"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "notebook_query",
        "description": "Query a knowledge notebook with citation-grounded BM25 retrieval, returning exact line-span anchors and source hashes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Notebook identifier"},
                "query": {"type": "string", "description": "Search query or question"},
                "top_k": {"type": "integer", "description": "Maximum number of citation chunks to return", "default": 5},
            },
            "required": ["id", "query"],
        },
    },
    {
        "name": "notebook_synthesize",
        "description": "Cross-reference multiple ingested sources on a topic, synthesizing findings with source attribution.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Notebook identifier"},
                "topic": {"type": "string", "description": "Topic or concept to synthesize"},
                "top_k": {"type": "integer", "description": "Top evidence count", "default": 5},
            },
            "required": ["id", "topic"],
        },
    },
    {
        "name": "notebook_verify_grounding",
        "description": "Adversarially verify whether a code change proposal or technical claim is grounded in indexed source specifications.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Notebook identifier"},
                "statement": {"type": "string", "description": "Candidate statement, claim, or invariant to verify"},
                "threshold": {"type": "number", "description": "Minimum grounding confidence threshold (0.0 to 1.0)", "default": 0.2},
            },
            "required": ["id", "statement"],
        },
    },
    {
        "name": "notebook_list",
        "description": "List all active knowledge notebooks and their source counts.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "notebook_create":
        nb = GroundedNotebook(
            notebook_id=args["id"],
            title=args["title"],
            description=args.get("description", ""),
        )
        STORE.save(nb)
        return {"content": [{"type": "text", "text": json.dumps(nb.to_dict(), indent=2)}]}

    elif name == "notebook_ingest":
        nb = STORE.load(args["id"])
        if nb is None:
            raise ValueError(f"Notebook '{args['id']}' not found.")
        file_path = args.get("file_path")
        content = args.get("content")
        sname = args.get("source_name", "document.md")
        if file_path:
            p = Path(file_path)
            if not p.is_file():
                # Try relative to repo
                p = REPO / file_path
            if not p.is_file():
                raise FileNotFoundError(f"File '{file_path}' not found.")
            content = p.read_text(encoding="utf-8")
            sname = p.name
            doc = nb.ingest_text(content, source_name=sname, source_path=str(p))
        elif content:
            doc = nb.ingest_text(content, source_name=sname)
        else:
            raise ValueError("Specify either 'file_path' or 'content'.")
        STORE.save(nb)
        return {"content": [{"type": "text", "text": json.dumps(doc.to_dict(), indent=2)}]}

    elif name == "notebook_query":
        nb = STORE.load(args["id"])
        if nb is None:
            raise ValueError(f"Notebook '{args['id']}' not found.")
        res = nb.query(query_text=args["query"], top_k=int(args.get("top_k", 5)))
        return {"content": [{"type": "text", "text": json.dumps(res.to_dict(), indent=2)}]}

    elif name == "notebook_synthesize":
        nb = STORE.load(args["id"])
        if nb is None:
            raise ValueError(f"Notebook '{args['id']}' not found.")
        synth = nb.synthesize(topic=args["topic"], top_k=int(args.get("top_k", 5)))
        return {"content": [{"type": "text", "text": json.dumps(synth.to_dict(), indent=2)}]}

    elif name == "notebook_verify_grounding":
        nb = STORE.load(args["id"])
        if nb is None:
            raise ValueError(f"Notebook '{args['id']}' not found.")
        verif = nb.verify_grounding(
            statement=args["statement"],
            threshold=float(args.get("threshold", 0.2)),
        )
        return {"content": [{"type": "text", "text": json.dumps(verif.to_dict(), indent=2)}]}

    elif name == "notebook_list":
        nbs = STORE.list_all()
        return {"content": [{"type": "text", "text": json.dumps({"notebooks": nbs, "total": len(nbs)}, indent=2)}]}

    raise ValueError(f"Unknown tool: {name}")


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                out = handle_call_tool(tool_name, tool_args)
                resp = {"jsonrpc": "2.0", "id": msg_id, "result": out}
            except Exception as e:
                resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": str(e)}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
