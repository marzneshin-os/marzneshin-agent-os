# Antigravity Workspace Instructions — Marzneshin Autonomous Agent OS

## 1. Active Model, Steering & Architecture
- **Primary Optimization:** Gemini 3.8 Flash (High) / Pixel Canary (`stealth/pixel-canary`) / Extended Thinking Models.
- **Source of Truth:** [BUILD-SPEC.md](BUILD-SPEC.md) (v2.0) & [AGENTS.md](AGENTS.md).
- **Core Philosophy:** Claude Code Ecosystem Architecture (Boris Cherny, Anthropic Lead) + GRAVITAS Invariants.

## 2. Boris Cherny's 10 Golden Rules for Antigravity IDE
1. **Plan Mode First (`/plan`)**: Never jump straight into code on complex tasks. Explore codebase first, verify assumptions, generate implementation plan, and obtain approval before mutations.
2. **Subagent Recon Isolation**: Offload heavy codebase search to isolated subagents (`invoke_subagent(TypeName="research")`) to keep the main conversation context clean.
3. **Multi-Agent Parallelism (`/worktree`)**: Run independent features in isolated Git worktrees (`python3 scripts/worktree_cli.py create <branch>`) to avoid branch collision and context bleed.
4. **Living Memory Compounding**: Every time an agent makes a mistake, immediately update repository instructions. Keep instruction files concise (<1,000 tokens).
5. **Deterministic Pre-Allowed Commands**: Tests, formatters, and builds are pre-allowed in `.claude/settings.json` for frictionless inner-loop execution.
6. **Self-Correction & Test Verification**: Never declare completion without fresh passing test evidence. Provide verification criteria in every implementation turn.
7. **Deterministic Hooks**:
   - `PostToolUse`: Automatically runs `ruff format` on edited Python files (<200ms budget).
   - `SessionStart`: Checks stale states, reconciles killswitch, and injects clean context.
   - `Stop`: Blocks session termination if unverified changes, open leases, or broken handoffs exist.
8. **Context Window Hygiene (`/compact` & `/context`)**: Re-compact state before context collapse occurs (`python3 scripts/compact.py`).
9. **YAGNI Decision Ladder (`/ponytail`)**: Evaluate requirements through the 7-step ladder before creating any new abstractions or files.
10. **Anti-Slop Design Taste (`/impeccable`)**: Eliminate AI-slop UI; enforce curated typography, harmonious HSL palettes, and restrained micro-interactions.

## 3. Operational Workflow & Tooling
- **Service Verification**: `python3 scripts/dev.py status`
- **Health Diagnostics**: `python3 scripts/antigravity_doctor_cli.py diagnose`
- **Token Optimization**: WebCMD memory layer (90% reduction via `python3 scripts/webcmd_cli.py browse <url>`) + Headroom CCR.
- **Security & ECC Harness**: AgentShield scan (`python3 scripts/ecc_cli.py scan`) and instincts (`python3 scripts/ecc_cli.py instincts`).
- **FreeLLMAPI Gateway**: Universal Free-Tier Token Pool on `http://127.0.0.1:3001/v1`.

## 4. GRAVITAS Reliability Runtime & Six Invariants
1. **Ground before mutating**: Read target + tests + callers before editing. File state is observed, never assumed.
2. **Stay in declared scope**: Writes outside declared task scope are denied. Amend the contract openly; do not route around it.
3. **Completion needs evidence**: A criterion is done only when a fresh validator PASS is recorded after the last mutation.
4. **Never exact-retry a failure**: Change diagnosis, context, or strategy before retrying.
5. **Satisfy the contract**: Acceptance criteria and required validators gate completion.
6. **Say what you cannot verify**: Label unverified claims explicitly; downgrade confidence rather than fabricating certainty.
