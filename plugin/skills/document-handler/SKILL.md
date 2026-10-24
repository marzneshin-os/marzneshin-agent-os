---
name: document-handler
description: Create, parse, inspect, and transform office documents including Excel (.xlsx), Word (.docx), PDF (.pdf), and PowerPoint (.pptx). Use when user asks to process, generate, edit, or convert document files.
argument-hint: "<action> <file-path>"
user-invocable: true
---

# Document Handler — Office Document Processing

Generate, inspect, extract, and convert structured documents (Excel, Word, PowerPoint, PDF).

## Quick Start

- **Excel (.xlsx / .csv):** Read sheets, update tabular data, apply formulas, format cell ranges.
- **Word (.docx):** Generate reports, format headings/paragraphs, insert tables and lists.
- **PDF (.pdf):** Extract text, parse tables, merge pages, inspect metadata.
- **PowerPoint (.pptx):** Generate slide decks, customize templates, add shape and text elements.

## Common Workflows

### 1. Tabular Data & Spreadsheets
Use headless libraries (e.g. `xlsx`, `exceljs`, or Python `openpyxl`/`pandas`) to read/write workbook data without requiring Microsoft Office.

### 2. Word Documents & Reports
Generate styled `.docx` reports using templates or programmatically using `docx` (Node) or `python-docx` (Python).

### 3. PDF Extraction & Generation
Extract structured content using `pdf-parse` / `pypdf`, or generate printable documents using PDF renderers.

## Safety & Best Practices

- Validate file paths before writing to prevent accidental overwrite.
- Retain original file backups when mutating existing documents.
- Keep formula calculations accurate and verify data types.

## See Also

- `REFERENCE.md`: Detailed library recommendations, formats, and code snippets.

## Troubleshooting

See ../_shared/TROUBLESHOOTING.md for common environment issues.
