#!/usr/bin/env python3
"""Document Intelligence & Markdown Converter (Khairallah Stack Tools #21 & #23).

Converts PDFs, CSVs, JSON, and web HTML into clean, token-optimized GitHub Flavored Markdown (GFM).
Zero external dependencies required (with graceful auto-detection of pypdf/pdfplumber if present).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))
if str(WORKSPACE_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from lib import clock
from lib.paths import repo_root


def convert_csv_to_markdown(text: str, delimiter: str = ",") -> str:
    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return ""
    header = rows[0]
    out = []
    out.append("| " + " | ".join(header) + " |")
    out.append("| " + " | ".join(["---"] * len(header)) + " |")
    for r in rows[1:]:
        # pad row if uneven
        padded = r + [""] * (len(header) - len(r))
        out.append("| " + " | ".join(padded[:len(header)]) + " |")
    return "\n".join(out)


def convert_json_to_markdown(raw_json: str) -> str:
    try:
        obj = json.loads(raw_json)
        formatted = json.dumps(obj, indent=2)
        return f"```json\n{formatted}\n```"
    except Exception:
        return raw_json


def convert_html_to_markdown(html: str) -> str:
    # Remove script and style
    text = re.sub(r"(?is)<script.*?</script>", "", html)
    text = re.sub(r"(?is)<style.*?</style>", "", text)
    # Convert headings
    text = re.sub(r"(?i)<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text)
    text = re.sub(r"(?i)<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text)
    text = re.sub(r"(?i)<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text)
    # Convert lists
    text = re.sub(r"(?i)<li[^>]*>(.*?)</li>", r"\n- \1", text)
    # Convert links
    text = re.sub(r"(?i)<a\s+[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", text)
    # Paragraphs and breaks
    text = re.sub(r"(?i)<p[^>]*>(.*?)</p>", r"\n\1\n", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_pure_python(data: bytes) -> str:
    """Extract readable text streams from PDF using pure python stdlib."""
    text_chunks: List[str] = []
    # Find all streams
    stream_matches = re.finditer(rb"stream[\r\n]+([\s\S]*?)[\r\n]+endstream", data)
    for m in stream_matches:
        raw_stream = m.group(1)
        # Try decompressing via zlib
        try:
            decompressed = zlib.decompress(raw_stream)
        except Exception:
            decompressed = raw_stream

        # Extract text within parentheses in BT ... ET blocks: (text) Tj or [(text)] TJ
        matches = re.findall(rb"\((.*?)\)\s*(?:Tj|'|\")", decompressed)
        for chunk in matches:
            try:
                decoded = chunk.decode("utf-8", errors="ignore").strip()
                if decoded and len(decoded) > 1:
                    text_chunks.append(decoded)
            except Exception:
                pass
    if text_chunks:
        return "\n".join(text_chunks)
    # Fallback to general printable ascii strings
    strings = re.findall(rb"[\x20-\x7E]{4,}", data)
    return "\n".join(s.decode("ascii", errors="ignore") for s in strings[:200])


def convert_pdf_to_markdown(pdf_path: Path) -> str:
    # Try pypdf if installed
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        pages_out = []
        for idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            pages_out.append(f"### Page {idx+1}\n\n{txt.strip()}")
        return f"# Document: {pdf_path.name}\n\n" + "\n\n---\n\n".join(pages_out)
    except Exception:
        pass

    # Pure python fallback
    data = pdf_path.read_bytes()
    text = _extract_pdf_pure_python(data)
    return f"# Document: {pdf_path.name} (Extracted Text)\n\n{text}"


def convert_file(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return convert_pdf_to_markdown(file_path)
    elif suffix in (".csv", ".tsv"):
        sep = "\t" if suffix == ".tsv" else ","
        return convert_csv_to_markdown(file_path.read_text(encoding="utf-8", errors="replace"), sep)
    elif suffix == ".json":
        return convert_json_to_markdown(file_path.read_text(encoding="utf-8", errors="replace"))
    elif suffix in (".html", ".htm"):
        return convert_html_to_markdown(file_path.read_text(encoding="utf-8", errors="replace"))
    else:
        return file_path.read_text(encoding="utf-8", errors="replace")


def cmd_convert(args: argparse.Namespace) -> int:
    target = Path(args.file)
    if not target.is_absolute():
        target = repo_root() / target

    try:
        md = convert_file(target)
    except Exception as e:
        print(f"Error converting {target}: {e}", file=sys.stderr)
        return 1

    if args.output:
        out_p = Path(args.output)
        if not out_p.is_absolute():
            out_p = repo_root() / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md, encoding="utf-8")
        print(f"Successfully converted {target.name} -> {out_p}")
    else:
        print(md[:args.preview_limit])
        if len(md) > args.preview_limit:
            print(f"\n... [Truncated. Use --output to write full {len(md)} characters]")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    target = Path(args.file)
    if not target.is_absolute():
        target = repo_root() / target

    if not target.exists():
        print(f"File not found: {target}", file=sys.stderr)
        return 1

    size_kb = round(target.stat().st_size / 1024, 2)
    print(f"Document Inspection: {target.name}")
    print("=" * 60)
    print(f"File Path:   {target}")
    print(f"File Size:   {size_kb} KB")
    print(f"Extension:   {target.suffix.lower() or 'none'}")
    print(f"Modified:    {clock.iso()}")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Document Intelligence & Markdown Converter")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_conv = subparsers.add_parser("convert", help="Convert document to markdown")
    p_conv.add_argument("file", help="Path to input document")
    p_conv.add_argument("--output", "-o", help="Optional output markdown file path")
    p_conv.add_argument("--preview-limit", type=int, default=1500, help="Max preview characters to print")
    p_conv.set_defaults(func=cmd_convert)

    p_insp = subparsers.add_parser("inspect", help="Inspect document metadata")
    p_insp.add_argument("file", help="Path to input document")
    p_insp.set_defaults(func=cmd_inspect)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())