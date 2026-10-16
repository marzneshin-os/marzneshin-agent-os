# Antigravity Workspace Instructions — Marzneshin Autonomous Agent OS

## Active Model & Steering
- **Primary Optimization:** Pixel Canary (`stealth/pixel-canary`) / Gemini 3.8 Flash.
- **Source of Truth:** [AGENTS.md](AGENTS.md) and [BUILD-SPEC.md](BUILD-SPEC.md).

## Operational Workflow
- Web browsing & token optimization: WebCMD memory layer (90% token reduction via `webcmd_browse` tool or `python3 scripts/webcmd_cli.py browse <url>`).
- Service verification: `python3 scripts/dev.py status`
- Autonomous tooling: Graphify (`graphify query`), Headroom (`headroom savings`), AgentMemory.
- Always verify changes before claiming completion.
- Security & Continuous Learning: Everything Claude Code (ECC) harness & AgentShield (`python3 scripts/ecc_cli.py scan` and `python3 scripts/ecc_cli.py instincts`).

## FreeLLMAPI Universal Free-Tier Token Pool (~7.4B Tokens/Month)
- **Local Gateway**: `http://127.0.0.1:3001/v1` (OpenAI & Anthropic `/v1/messages` compatible)
- **Status & Diagnostics**: `python3 scripts/freellm_cli.py status`
- **Catalog of Free Models**: `python3 scripts/freellm_cli.py catalog --domain coding`
- **Failover**: Auto-switches across 34+ free-tier providers on 429 rate limit with multi-key cooldown.
