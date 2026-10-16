#!/usr/bin/env python3
"""Grounded Notebook CLI — Citation-Anchored Knowledge Exploration & Verification.

Synthesizes NotebookLM grounded knowledge exploration with Antigravity autonomous action.
Governed by ADR-026 and BUILD-SPEC.md v2.0 §4.
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.insert(1, str(REPO / "scripts"))

from scripts.lib.grounded_notebook import GroundedNotebook, NotebookStore


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grounded Notebook Knowledge Engine CLI (ADR-026)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_p = subparsers.add_parser("create", help="Create a new knowledge notebook")
    create_p.add_argument("--id", required=True, help="Notebook unique identifier")
    create_p.add_argument("--title", required=True, help="Notebook title")
    create_p.add_argument("--description", default="", help="Notebook description")
    create_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # ingest
    ingest_p = subparsers.add_parser("ingest", help="Ingest a file or raw text into a notebook")
    ingest_p.add_argument("--id", required=True, help="Notebook identifier")
    ingest_p.add_argument("--file", help="Path to file to ingest")
    ingest_p.add_argument("--text", help="Raw text to ingest directly")
    ingest_p.add_argument("--name", default="doc.md", help="Document name for citations")
    ingest_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # query
    query_p = subparsers.add_parser("query", help="Run a citation-grounded query against a notebook")
    query_p.add_argument("--id", required=True, help="Notebook identifier")
    query_p.add_argument("--query", required=True, help="Query text")
    query_p.add_argument("--top-k", type=int, default=5, help="Max citation chunks")
    query_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # synthesize
    synth_p = subparsers.add_parser("synthesize", help="Synthesize multiple sources on a topic")
    synth_p.add_argument("--id", required=True, help="Notebook identifier")
    synth_p.add_argument("--topic", required=True, help="Topic to synthesize")
    synth_p.add_argument("--top-k", type=int, default=5, help="Top evidence count")
    synth_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # verify
    verify_p = subparsers.add_parser("verify", help="Adversarially verify statement grounding against sources")
    verify_p.add_argument("--id", required=True, help="Notebook identifier")
    verify_p.add_argument("--statement", required=True, help="Statement to check")
    verify_p.add_argument("--threshold", type=float, default=0.2, help="Support confidence threshold")
    verify_p.add_argument("--json", action="store_true", help="Output raw JSON")

    # list
    list_p = subparsers.add_parser("list", help="List all available knowledge notebooks")
    list_p.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()
    store = NotebookStore()

    if args.command == "create":
        nb = GroundedNotebook(notebook_id=args.id, title=args.title, description=args.description)
        store.save(nb)
        if args.json:
            print(json.dumps(nb.to_dict(), indent=2))
        else:
            print(f"Created notebook '{args.id}': {args.title}")
        return 0

    elif args.command == "ingest":
        nb = store.load(args.id)
        if nb is None:
            print(f"Error: Notebook '{args.id}' not found.", file=sys.stderr)
            return 1
        if args.file:
            fpath = Path(args.file)
            if not fpath.is_file():
                print(f"Error: File '{args.file}' not found.", file=sys.stderr)
                return 1
            content = fpath.read_text(encoding="utf-8")
            sname = args.name if args.name != "doc.md" else fpath.name
            doc = nb.ingest_text(content, source_name=sname, source_path=str(fpath))
        elif args.text:
            doc = nb.ingest_text(args.text, source_name=args.name)
        else:
            print("Error: Specify either --file or --text.", file=sys.stderr)
            return 1

        store.save(nb)
        if args.json:
            print(json.dumps(doc.to_dict(), indent=2))
        else:
            print(f"Ingested '{doc.source_name}' ({doc.total_lines} lines, {doc.total_chunks} chunks).")
        return 0

    elif args.command == "query":
        nb = store.load(args.id)
        if nb is None:
            print(f"Error: Notebook '{args.id}' not found.", file=sys.stderr)
            return 1
        res = nb.query(query_text=args.query, top_k=args.top_k)
        if args.json:
            print(json.dumps(res.to_dict(), indent=2))
        else:
            print(f"=== Query: '{args.query}' ===")
            print(f"Matched Chunks: {res.total_chunks_matched}")
            for c in res.citations:
                print(f"• Citation: {c['citation']} (Hash: {c['content_hash'][:8]})")
            print("\n--- Synthesized Context ---")
            print(res.synthesized_context)
        return 0

    elif args.command == "synthesize":
        nb = store.load(args.id)
        if nb is None:
            print(f"Error: Notebook '{args.id}' not found.", file=sys.stderr)
            return 1
        synth = nb.synthesize(topic=args.topic, top_k=args.top_k)
        if args.json:
            print(json.dumps(synth.to_dict(), indent=2))
        else:
            print(synth.summary)
        return 0

    elif args.command == "verify":
        nb = store.load(args.id)
        if nb is None:
            print(f"Error: Notebook '{args.id}' not found.", file=sys.stderr)
            return 1
        verif = nb.verify_grounding(statement=args.statement, threshold=args.threshold)
        if args.json:
            print(json.dumps(verif.to_dict(), indent=2))
        else:
            status = "SUPPORTED" if verif.supported else "UNSUPPORTED / HALLUCINATED"
            print(f"Grounding Status: {status} (Confidence: {verif.confidence:.1%})")
            if verif.supporting_citations:
                print("Citations:")
                for c in verif.supporting_citations:
                    print(f"  • {c['citation']}")
            if verif.unsupported_aspects:
                print("Unsupported Aspects:")
                for u in verif.unsupported_aspects:
                    print(f"  ✗ {u}")
        return 0

    elif args.command == "list":
        nbs = store.list_all()
        if args.json:
            print(json.dumps({"notebooks": nbs, "total": len(nbs)}, indent=2))
        else:
            print(f"Found {len(nbs)} knowledge notebook(s):")
            for item in nbs:
                print(f"• [{item['notebook_id']}] {item['title']} ({item['sources_count']} docs, {item['chunks_count']} chunks)")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
