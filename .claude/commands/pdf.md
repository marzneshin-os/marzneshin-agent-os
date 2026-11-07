---
description: Official Anthropic PDF Document Processing & Table Extraction (Khairallah Stack #23)
---

**ANTHROPIC OFFICIAL PDF PROCESSING**

Inspect, extract, and convert PDF documents:
1. **Inspect Metadata**: `python3 scripts/markdownify_cli.py inspect <file.pdf>`
2. **Convert to Markdown**: `python3 scripts/markdownify_cli.py convert <file.pdf> -o output.md`
3. **Table Extraction**: Extract structured CSV and GFM tables from multi-column PDFs without OCR loss.