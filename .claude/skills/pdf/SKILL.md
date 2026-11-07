---
name: pdf
description: Official Anthropic PDF document processing, table parsing, and form extraction (Khairallah Stack Tool #23). Use when inspecting PDF files, extracting tabular data, or converting documentation into Markdown.
---

# Official PDF Processing & Document Intelligence

Analyze, extract, and convert PDF documents with high fidelity.

## Capabilities
- **Text & Structure**: Extract text layout-preservatively without character corruption.
- **Table Extraction**: Convert complex multi-column tables into clean Markdown/CSV matrices.
- **Form Inspection**: Read and parse AcroForms and structured PDF fields.

## Usage Commands
- Inspect document info: `python3 scripts/markdownify_cli.py inspect <file.pdf>`
- Convert to Markdown: `python3 scripts/markdownify_cli.py convert <file.pdf> -o output.md`