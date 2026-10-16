---
name: webcmd-browser
description: "Self-learning browser memory and 90% token reduction layer for web browsing, documentation lookup, and DOM interaction. Caches sitemaps, action element shortcuts, and page state recipes across Antigravity, Claude Code, and OpenCode."
trigger: /webcmd
---

# WebCMD — Self-Learning Browser Memory & Token Optimization

WebCMD acts as a persistent memory and token-reduction layer between AI agents and the web. Standard browser automation re-parses heavy DOM structures on every visit, consuming tens of thousands of tokens. WebCMD compresses web pages into high-density semantic action maps, remembers domain sitemaps, and allows direct shortcut navigation, reducing web token spend by up to **90%**.

## Architecture

```
 AI Agent (Antigravity IDE / Claude Code / OpenCode / LangGraph)
        │
        ▼
 ┌─────────────────────────────────────────────────────────────┐
 │  WebCMD Adapter & Memory Engine (scripts/lib/webcmd_memory) │
 │  ────────────────────────────────────────────────────────── │
 │  • 90% Semantic DOM Compressor & Interactive Action Mapper  │
 │  • Domain Navigation Graph Store (state/web_memory/)        │
 │  • Isolated Agent Spaces & Profiles (cookie jars)           │
 │  • Structural Fingerprinting & Auto-Invalidation Drift Gate │
 └─────────────────────────────────────────────────────────────┘
        │
        ▼
 Target Website (Docs, GitHub, Internal Portals, APIs)
```

## Available MCP Tools

When the `webcmd-browser` MCP server is active in `.mcp.json`, agents can invoke:

1. `webcmd_browse`:
   - Fetches target URL and returns a compressed semantic text representation with interactive targets (`[@1]`, `[@2]`, ...).
   - Parameters: `url` (string, required), `profile` (string, optional).
2. `webcmd_get_sitemap`:
   - Retrieves learned domain sitemap, navigation routes, and selector shortcuts.
   - Parameters: `domain` (string, required).
3. `webcmd_learn_route`:
   - Manually or programmatically stores an action route or selector shortcut into domain memory.
   - Parameters: `url` (string, required), `title` (string, optional), `shortcuts` (object, optional).
4. `webcmd_status`:
   - Returns operational status, number of cached domains, and lifetime tokens saved.
5. `webcmd_purge_cache`:
   - Clears memory cache for a specific domain or all memory.

## CLI Usage

Agents and human operators can execute CLI commands directly:

```bash
# Check status and lifetime tokens saved
python3 scripts/webcmd_cli.py status

# Browse and compress a webpage with 90% token savings
python3 scripts/webcmd_cli.py browse https://docs.github.com/en/rest

# Inspect learned sitemap for a domain
python3 scripts/webcmd_cli.py sitemap docs.github.com

# Purge cache for a domain if structure changed
python3 scripts/webcmd_cli.py purge --domain docs.github.com
```

## Operating Invariants

- **Fail-Closed & Sanitized**: All network calls fail closed safely; credentials and authorization headers are never logged or stored in sitemaps (I6).
- **Auto-Freshness**: WebCMD checks structural hashes on live visits. If the DOM structure drifted, it invalidates stale selectors and relearns the path autonomously.
