# WebCMD Self-Learning Browser Memory Rule

When performing web searches, documentation retrieval, or external web browsing:

1. **Token Efficiency First**: Never dump raw HTML or uncompressed DOM structures into the LLM context. Always utilize WebCMD (`webcmd_browse` tool or `python3 scripts/webcmd_cli.py browse <url>`).
2. **Sitemap Memory Consultation**: Before executing multi-step web interactions, inspect existing domain memory via `webcmd_get_sitemap` to reuse known routes and selectors.
3. **Fail-Closed & Security (I6)**: Never transmit or record raw secrets, cookies with session tokens, or API keys in memory sitemaps.
4. **Action Shortcuts**: Use the compact interactive action identifiers (`[@id]`) extracted by the semantic compressor rather than searching through thousands of raw HTML tags.
