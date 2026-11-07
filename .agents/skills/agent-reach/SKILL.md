---
name: agent-reach
description: Read and extract content from the web and social platforms without API keys. Use when the user requests reading articles, tweets, Reddit threads, GitHub repos, YouTube transcripts, or when invoking /agent-reach.
---

# Agent Reach: Zero-Key Web & Social Intelligence

Extract high-fidelity markdown content from public web URLs and social platforms without requiring paid API keys.

## Supported Sources
- **Twitter / X**: Extracts tweets, threads, profiles, and media links via public mirrors/proxies.
- **Reddit**: Parses Reddit JSON endpoints (`.json` append) for threads and top comments.
- **GitHub**: Directly reads public files, commits, READMEs, and releases via raw GitHub content.
- **Web Articles & Docs**: Strips boilerplate, ads, navbars, and cookie banners to return clean GitHub-flavored markdown.
- **YouTube**: Retrieves video titles, descriptions, and available captions/transcripts.

## Operational Modes
- `read_url_content(Url)`: Fast HTTP fetch and HTML-to-markdown extraction.
- `webcmd_browse`: Integrated with the repository's WebCMD memory layer for 90% token reduction:
  ```bash
  python3 scripts/webcmd_cli.py browse <url>
  ```
- Diagnostic:
  ```bash
  python3 scripts/webcmd_cli.py status
  ```

## Invariants
- Never persist credentials or tokens found in fetched content (enforce `lib.redact`).
- Truncate excessively long web documents beyond 50,000 characters to prevent context blowout.
