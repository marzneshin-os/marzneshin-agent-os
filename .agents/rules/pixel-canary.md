# Pixel Canary Model Steering Rule

This rule guides autonomous agents when utilizing the **Pixel Canary** (`stealth/pixel-canary`) model.

## Model Characteristics
- High capability on coding agent benchmarks (96.8% with project context).
- Stealth model hosted on Vercel AI Gateway / Cline Free tier.
- Highly sensitive to architectural context files like `AGENTS.md`.

## Execution Directives
1. Always maintain alignment with `AGENTS.md` consistency rules.
2. Do not log or leak sensitive credentials to stealth/preview models.
3. Test every change before concluding tasks.
