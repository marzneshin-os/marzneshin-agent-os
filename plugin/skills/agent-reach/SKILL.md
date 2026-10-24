---
name: agent-reach
description: Read and extract content from the web and social platforms without API keys. Use when the user requests reading articles, tweets, Reddit threads, GitHub repos, YouTube transcripts, or when invoking /agent-reach.
argument-hint: "<url> [options]"
user-invocable: true
---

# Agent Reach — Keyless Web & Social Content Extractor

Fetch, parse, and clean content across 13+ web and social platforms without requiring third-party API credentials.

## Quick Start

Run `/agent-reach <url>` to fetch content from supported platforms:
- **Articles & Webpages:** Extracts clean Markdown, stripping nav, ads, and cookie banners.
- **X / Twitter:** Fetches post threads, author info, and engagement metrics.
- **Reddit:** Extracts post body, top comment trees, and author info via public JSON endpoints.
- **YouTube:** Extracts video metadata, descriptions, and captions/transcripts.
- **GitHub:** Fetches READMEs, file trees, issues, and PR diffs via public endpoints.
- **RSS/Atom:** Parses feeds into structured updates.

## Commands

- `/agent-reach <url>`: Extract and format content from URL as clean Markdown.
- `/agent-reach doctor`: Verify network access and extractor availability across platforms.
- `/agent-reach raw <url>`: Retrieve unformatted text or HTML representation.

## Extraction Workflow

1. Detect target platform from URL domain and structure.
2. Route to specialized parser (see `REFERENCE.md`).
3. Clean and sanitize content (strip scripts, tracking params, boilerplate).
4. Return structured Markdown with title, author, date, source URL, and clean body.

## See Also

- `REFERENCE.md`: Platform-specific extraction methods, rate limits, and fallback strategies.

## Troubleshooting

See ../_shared/TROUBLESHOOTING.md for network or parsing issues.
