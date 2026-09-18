# ADR-013: Claude Code Router (CCR) Full Integration

**Date**: 2026-09-05
**Status**: Accepted
**Context**: The Marzneshin Agent OS previously had a stub entry for Claude Code Router (CCR) in `configs/services.json` pointing to a Windows `.exe` file. This failed in WSL due to GUI/Chromium lock-file conflicts. The system's LLM routing (ADR-012) relied solely on the custom Python-based `scripts/router.py` and `scripts/router_server.py` OmniRoute adapter. CCR from [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) provides a production-grade, OpenAI-compatible local gateway with multi-provider routing, usage tracking, and a management UI — capabilities that complement rather than replace the existing router.

## Decision

1. **Headless CLI Deployment**: Replace the Windows `.exe` command in `configs/services.json` with the headless CLI invocation `ccr start --no-open --gateway` via the npm package `@musistudio/claude-code-router` (already installed globally at `~/.nvm/versions/node/v24.19.0/bin/ccr`). This runs the gateway on port 3456 and the management web UI on port 3458 without requiring a display server.

2. **Config Sync from Windows**: The Windows CCR desktop app (`C:\Users\Asus\AppData\Local\Programs\Claude Code Router\`) already has 4 providers configured (TabiToken, FreeLLMAPI, Google Gemini AI Studio, HuggingFace) with 22 models total. The `config.sqlite` from Windows AppData was copied to `~/.claude-code-router/config.sqlite` in WSL to share the same provider configuration.

3. **Router Integration**: The CCR gateway was added as a first-class gateway entry `ccr` in `configs/router.json` with `base_url: http://127.0.0.1:3456/v1`. CCR models were integrated into all routing combos (`fable-planner`, `fable-reasoning`, `fable-luna`, `fable-flash`, `cheap`, `smart`) as priority entries with the `ccr:` prefix, with automatic fallback to existing gateways (freemodels, openrouter, tabitoken, etc.).

4. **Graceful Fallback**: If CCR is not running (port 3456 unreachable), the routing system skips CCR entries and falls back to direct provider gateways. No single point of failure is introduced.

5. **lint-clock Fix (D6)**: The `time.sleep(1)` call in `scripts/dev.py` was replaced with `clock.sleep(1)` from `lib.clock`, and a top-level `sleep()` convenience function was added to `scripts/lib/clock.py`. This restores the `lint-clock` verify gate to GREEN.

## Consequences
- **Positive**: 22 models from 4 providers (TabiToken, FreeLLMAPI, Google Gemini, HuggingFace) are now accessible through a unified local gateway with usage tracking, request logging, and a web management UI at `http://127.0.0.1:3458`.
- **Positive**: All verify checks (6/6) and unit tests (177/177) pass GREEN after the lint-clock fix.
- **Negative**: CCR must be running for its models to be reachable; mitigated by fallback routing.
- **Negative**: The `config.sqlite` sync between Windows and WSL is manual; a future improvement could automate this.

## References
- `configs/services.json` — service definition
- `configs/router.json` — gateway and combo configuration
- `scripts/lib/clock.py` — added `sleep()` convenience function
- `scripts/dev.py` — replaced `time.sleep` with `clock.sleep`
- [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) — upstream repository
