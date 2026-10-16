# FreeLLMAPI Universal Free-Tier Token Pool Rule

All autonomous agents operating in Marzneshin Agent OS should leverage the FreeLLMAPI unified free token pool for non-critical, high-volume evaluations, code generation, and test synthesis:

1. **Free Token Pool Preference**:
   - For fast inference, subagent loops, and bulk code analysis, prefer free-tier pooled endpoints (`http://127.0.0.1:3001/v1` or combo `freellm-coding` / `freellm-fast`).
   - Monitor pool health via `python3 scripts/freellm_cli.py status`.

2. **Rate Limit Resilience**:
   - If an agent receives HTTP 429 or 402, report rate limit via `FreeLLMPoolManager` or adapter, triggering automatic cooldown and immediate fallback to the next candidate model.
   - Never abort an autonomous session due to single-key quota exhaustion.

3. **Zero Hardcoded Secrets**:
   - All provider keys must be managed in `configs/keys_pool.json` or environment variables without hardcoded production fallbacks.
