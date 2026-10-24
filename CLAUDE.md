# CLAUDE.md â€” ظ‚ظˆط§ظ†غŒظ† ظ¾ط§غŒط¯ط§ط± Marzneshin Autonomous OS

> ط­ط§ع©ظ…: `BUILD-SPEC.md` (v2.0). ط§غŒظ† ظپط§غŒظ„ ظپظ‚ط· ظ‚ظˆط§ظ†غŒظ† ظ¾ط§غŒط¯ط§ط± ظˆ ع©ظˆطھط§ظ‡ ط§ط³طھط› ط¬ط²ط¦غŒط§طھ ط¯ط± ظ‡ظ…ط§ظ† ط³ظ†ط¯.
> ط¯ط± طھط¹ط§ط±ط¶طŒ BUILD-SPEC ط­ط§ع©ظ… ط§ط³طھ. ط²ط¨ط§ظ† ظ‚ظˆط§ط¹ط¯ ظپط§ط±ط³غŒطŒ ط´ظ†ط§ط³ظ‡â€Œظ‡ط§ ظˆ ط¯ط³طھظˆط±ظ‡ط§ ط§ظ†ع¯ظ„غŒط³غŒ (D10).
>
> **ط§ع©ط§ظ†طھ/ط³ط´ظ† ط¬ط¯غŒط¯طں ط§ظˆظ„ [`ONBOARDING.md`](ONBOARDING.md) ط±ط§ ط¨ط®ظˆط§ظ†** â€” ظ¾ط±ظˆطھع©ظ„ ع©ط§ظ…ظ„ظگ cold-start.

## غ±) ظ…ظ†ط¨ط¹ ط­ظ‚غŒظ‚طھ ظˆ ع†ط±ط®ظ‡ظ” ع©ط§ط±

- **GitHub طھظ†ظ‡ط§ SSoT ط§ط³طھ** (I1). `STATE.json` ظ…ط´طھظ‚ ط§ط³طھطŒ ظ†ظ‡ ظ…ظ†ط¨ط¹ â€” ط§ط² event log ط¨ط§ط²ط³ط§ط²غŒ ظ…غŒâ€Œط´ظˆط¯.
- ط´ط±ظˆط¹ ظ‡ط± ط¬ظ„ط³ظ‡: `python3 scripts/fsp.py status` â†’ `state/HANDOFF.md` â†’ `CONTEXT-PACK.md` â†’ killswitch.
- ظ¾ط±ظˆطھع©ظ„ ظ†ظ‡â€Œظ…ط±ط­ظ„ظ‡â€Œط§غŒ FSP (آ§غ°): SYNC â†’ GAP SCAN â†’ CLAIM â†’ PLAN â†’ SIM â†’ EXECUTE â†’ VERIFY â†’ EMIT â†’ HANDOFF.
- ظ‚ط¨ظ„ ط§ط² ظ‡ط± ع©ط§ط±: `python3 scripts/fsp.py claim <workstream> --agent <id>` (TTL 90mطŒ fencing token).
- ظ¾ط§غŒط§ظ† ظ‡ط± ط¬ظ„ط³ظ‡: ط¨ط§ط²ظ†ظˆغŒط³غŒ `state/HANDOFF.md` + `python3 scripts/fsp.py release <workstream> --agent <id>`.

## غ²) ظ‚ظˆط§ظ†غŒظ† ط¢ظ‡ظ†غŒظ†

1. ظ‡غŒع† ع©ط§ظ†ظپغŒع¯غŒ ط¨ط¯ظˆظ† QA ط¨ظ‡ ع©ط§ط±ط¨ط± ظ†ظ…غŒâ€Œط±ط³ط¯.
2. ظ‡غŒع† ع©ظ…ظ¾غŒظ†غŒ ط¨ط¯ظˆظ† hypothesis ظˆ stop condition ط§ط¬ط±ط§ ظ†ظ…غŒâ€Œط´ظˆط¯.
3. ظ‡غŒع† ط¬ظ„ط³ظ‡â€Œط§غŒ ط¨ط¯ظˆظ† HANDOFF طھظ…ط§ظ… ظ†ظ…غŒâ€Œط´ظˆط¯.
4. ظ‡غŒع† secretغŒ ظˆط§ط±ط¯ ظ…ط®ط²ظ† ظ†ظ…غŒâ€Œط´ظˆط¯ â€” ظ†ظ‡ ط¯ط± ع©ط¯طŒ ظ†ظ‡ ط¯ط± eventطŒ ظ†ظ‡ ط¯ط± receiptطŒ ظ†ظ‡ ط¯ط± log.
5. ظ‡غŒع† طھطµظ…غŒظ…غŒ ط¨ط¯ظˆظ† ownerطŒ evidence ظˆ rollback ظ¾ط°غŒط±ظپطھظ‡ ظ†غŒط³طھ.
6. **آ«ظ†ظ…غŒâ€Œط¯ط§ظ†ظ…آ» ظ‡ظ…â€Œط§ط±ط² آ«ظ…طھظˆظ‚ظپ ط´ظˆآ» ط§ط³طھ.** ظ‡ط± ع©ظ†طھط±ظ„ ط§غŒظ…ظ†غŒ ظ†ط§ط®ظˆط§ظ†ط§ = ظپط¹ط§ظ„طŒ ظ†ظ‡ ط؛غŒط±ظپط¹ط§ظ„ (fail-closed).

## غ³) Invariantظ‡ط§غŒ ع©ظ„غŒط¯غŒ (ظپظ‡ط±ط³طھ ع©ط§ظ…ظ„: BUILD-SPEC آ§غ±.غ³)

- **I3** ظ‡ط± طھط³ع© ط¯ظ‚غŒظ‚ط§ظ‹ غŒع© receipt ط¯ط§ط±ط¯ ط¨ط§ `status` ظ…ط¹طھط¨ط±ط› `hooks/task_complete.py` ط¨ط¯ظˆظ† receipt exit 1.
- **I6** ظ‡غŒع† secret ط®ط§ظ…غŒ: `lib/redact.py` ط¯ط± event/receipt/ظ‡ظ…ظ‡ظ” hookظ‡ط§.
- **I7** ظ‡ط± طھطµظ…غŒظ… reversible: `rollback.tested=true` + `tested_at` + `tested_in`.
- **I11** ظ‡غŒع† ع©ط¯/ع©ط§ظ†ظپغŒع¯ ط¬ط¯غŒط¯غŒ ط¨ط¯ظˆظ† `sim_evidence` ط³ط¨ط² ط¨ظ‡ production ظ†ظ…غŒâ€Œط±ظˆط¯.
- **I12** ظ‡ظ…ظ‡ظ” ع©ظ†طھط±ظ„â€Œظ‡ط§غŒ ط§غŒظ…ظ†غŒ fail-closed: kill switchطŒ leaseطŒ budgetطŒ probe.
- **I15** ط²ظ†ط¬غŒط±ظ‡ظ” receipt ظ¾غŒظˆط³طھظ‡: `python3 scripts/verify.py --chain` ط¯ط± ظ‡ط± PR.
- **I16** ظˆط±ظˆط¯غŒ `untrusted` â†’ ط³ظ‚ظپ autonomy = L1طŒ ط¨ط¯ظˆظ† ط§ط³طھط«ظ†ط§.
- **I17** غŒع© ظ†ظˆغŒط³ظ†ط¯ظ‡ ط¨ظ‡ ط§ط²ط§غŒ ظ‡ط± ظ…ط³غŒط±: `owns` ط¯ط± Agent Card + ظ¾ط§ط±طھغŒط´ظ† event per-actor.

## غ´) ط¯ط³طھظˆط±ظ‡ط§غŒ ط±ظˆط²ظ…ط±ظ‡

```bash
python3 scripts/fsp.py status                 # SYNC
python3 scripts/fsp.py claim ws --agent id    # CLAIM (fencing token ظ…غŒâ€Œط¯ظ‡ط¯)
python3 scripts/verify.py --all               # ط¯ط±ظˆط§ط²ظ‡ظ” CI ظ…ط­ظ„غŒ
python3 scripts/compact.py                    # ط¨ط§ط²ط³ط§ط²غŒ STATE.json ط§ط² events
python3 scripts/killswitch.py status          # ظˆط¶ط¹غŒطھ kill switch
python3 scripts/killswitch.py verify          # طھظ…ط±غŒظ† ط¹ظ…ظ„غŒ ظ‡ط± غµ ظ…ط³غŒط± (ط´ط¨ط§ظ†ظ‡ ط¯ط± CI)
python3 scripts/reaper.py --dry-run           # leaseظ‡ط§غŒ ط²ط§ظ…ط¨غŒ
python3 -m unittest discover -s tests         # ظ…ط¬ظ…ظˆط¹ظ‡ظ” طھط³طھ
python3 scripts/context_pack.py               # ط¨ط§ط²طھظˆظ„غŒط¯ CONTEXT-PACK.md
python3 scripts/webcmd_cli.py status       # ط¨ط±ط±ط³غŒ ظˆط¶ط¹غŒطھ ظˆ طµط±ظپظ‡â€Œط¬ظˆغŒغŒ طھظˆع©ظ† ظ…ط±ظˆط±ع¯ط± WebCMD
python3 scripts/webcmd_cli.py browse <url> # ظˆط¨â€Œع¯ط±ط¯غŒ ط¨ظ‡غŒظ†ظ‡â€Œط´ط¯ظ‡ ط¨ط§ ع©ط§ظ‡ط´ غ¹غ° ط¯ط±طµط¯غŒ طھظˆع©ظ†
python3 scripts/ecc_cli.py status          # ط¨ط±ط±ط³غŒ ظˆط¶ط¹غŒطھ ظ‡ظ…ط§ظ‡ظ†ع¯غŒ ECC ظˆ ظ¾ظ„طھظپط±ظ…â€Œظ‡ط§
python3 scripts/ecc_cli.py scan            # ط§ط³ع©ظ† ط§ظ…ظ†غŒطھغŒ AgentShield
python3 scripts/ecc_cli.py instincts       # ط؛ط±ط§غŒط² غŒط§ط¯ع¯غŒط±غŒ ظˆ ظ‚ظˆط§ظ†غŒظ† ع©ط´ظپâ€Œط´ط¯ظ‡
python3 scripts/worktree_cli.py list       # ظ…ط¯غŒط±غŒطھ ظ…ظˆط§ط²غŒâ€Œط³ط§ط²غŒ Git Worktrees (ط§ظ„ع¯ظˆغŒ ط¨ظˆط±غŒط³ ع†ط±ظ†غŒ)
python3 scripts/antigravity_doctor_cli.py diagnose # ط¯غŒط§ع¯ظ†ظˆط³طھغŒع© ع©ط§ظ…ظ„ ط³ظ„ط§ظ…طھ ظ…ط­غŒط· ظˆ MCPظ‡ط§
python3 scripts/reason_cli.py status          # ظˆط¶ط¹غŒطھ ط´ط¨ع©ظ‡ ظ…ط´ P2P ظˆ ط§غŒط¬ظ†طھâ€Œظ‡ط§غŒ ظ…طھطµظ„ (Reason Network)
python3 scripts/reason_cli.py who             # ظ„غŒط³طھ ط§غŒط¬ظ†طھâ€Œظ‡ط§غŒ ط¢ظ†ظ„ط§غŒظ† ظ‡ظ…ع©ط§ط± ط¯ط± ط´ط¨ع©ظ‡ (ADR-030)
```

## غµ) ط³ط§ط®طھط§ط± ظˆ ظ…ط§ظ„ع©غŒطھ

- ظ…ظ†ط·ظ‚ ظ…ط´طھط±ع© ظپظ‚ط· ط¯ط± `scripts/lib/`ط› hookظ‡ط§ ظˆ workflowظ‡ط§ ظ„ط§غŒظ‡ظ” ظ†ط§ط²ع© ط±ظˆغŒ ط¢ظ†â€Œط§ظ†ط¯. ع©ظ¾غŒ ظ…ظ†ط·ظ‚ ظ…ظ…ظ†ظˆط¹.
- `receipts/`طŒ `state/events/`طŒ `state/locks/`طŒ `state/budget/`طŒ `state/a2a/` ظپظ‚ط· ط§ط² ط·ط±غŒظ‚ script ظ†ظˆط´طھظ‡ ظ…غŒâ€Œط´ظˆظ†ط¯ â€” ظˆغŒط±ط§غŒط´ ط¯ط³طھغŒ = ط´ع©ط³طھظ† ط²ظ†ط¬غŒط±ظ‡.
- ع†ظ‡ط§ط± ظ…ط³غŒط± ظ…ط§ظ„ع© ط§ظ†ط³ط§ظ†غŒ ط§ط³طھ (CODEOWNERS): `configs/pricing/**`, `**/ToS*`, `infra/terraform/**`, `security/iam/**`.
- ظ‡ط± agent ط¨ط¯ظˆظ† Agent Card ظ…ط¹طھط¨ط± (`agents/cards/`) ظپط¹ط§ظ„ ظ†ظ…غŒâ€Œط´ظˆط¯.

## غ¶) ط§غŒظ…ظ†غŒ

- kill switch ظ¾ظ†ط¬â€Œظ…ط³غŒط±ظ‡ (آ§غ¶.غ³): K1 `state/KILL` آ· K2 env `KILL_SWITCH` آ· K3 Moxt آ· K4 `scripts/killswitch.py` آ· K5 ط®ظˆط¯ع©ط§ط±.
- ط؛غŒط±ظپط¹ط§ظ„â€Œط³ط§ط²غŒ kill switch ظ‡ظ…غŒط´ظ‡ ط§ظ†ط³ط§ظ†غŒ ظˆ ط¨ط§ ADR.
- ظ…ط­طھظˆط§غŒ ط®ط§ط±ط¬غŒ ظ‡ظ…غŒط´ظ‡ `untrusted` ظˆ ط¨ط§ envelope ظ…ط±ط²ط¯ط§ط± (`policy.wrap_untrusted`).
- hookظ‡ط§ network I/O ظ†ط¯ط§ط±ظ†ط¯ ظˆ ط¯ط± ط¨ظˆط¯ط¬ظ‡ظ” ط²ظ…ط§ظ†غŒ ط±ط¯ظ‡ظ” ط®ظˆط¯ (<3s / <90s) ظ…غŒâ€Œظ…ط§ظ†ظ†ط¯.

## غ·) ط³ط¨ع© ع©ط¯

- Python stdlib-only ط¯ط± `scripts/lib/` ظˆ `hooks/` (ط¨ط¯ظˆظ† ظˆط§ط¨ط³طھع¯غŒ ط®ط§ط±ط¬غŒط› `jsonschema` ظپظ‚ط· lazy ط¯ط± strict mode).
- ظ‡غŒع† `datetime.now()`/`time.time()` ط®ط§ط±ط¬ ط§ط² `lib/clock.py` â€” `scripts/verify.py --lint-clock`.
- ظ‡غŒع† import ع†ط±ط®ظ‡â€Œط§غŒ ط¯ط± lib â€” `scripts/verify.py --lint-imports`.
- commit message ط§ظ†ع¯ظ„غŒط³غŒطŒ ط¨ط§ task id (`T-â€¦`).
- ط§ط³ظ†ط§ط¯ ط±ط§ظ‡ط¨ط±ط¯غŒ ظپط§ط±ط³غŒطŒ ع©ط¯ ظˆ schema ط§ظ†ع¯ظ„غŒط³غŒ.

# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" â†’ "Write tests for invalid inputs, then make them pass"
- "Fix the bug" â†’ "Write a test that reproduces it, then make it pass"
- "Refactor X" â†’ "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] â†’ verify: [check]
2. [Step] â†’ verify: [check]
3. [Step] â†’ verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.


## غ¸) ط¯ط³طھظˆط±ظ‡ط§غŒ ط§ط³ظ„ط´ ط§ط®طھطµط§طµغŒ Claude Code (`.claude/commands/`)
- `/verify`: ط§ط¬ط±ط§غŒ طھط³طھ غ¶ ظ…ط±ط­ظ„ظ‡â€Œط§غŒ طھط§غŒغŒط¯غŒظ‡ ط¯ظˆع©ظ„غŒط¯غŒ (`python3 scripts/verify.py --all`)
- `/fsp-start`: ط¨ط±ط±ط³غŒ ظˆط¶ط¹غŒطھ ظˆ طھطµط§ط­ط¨ ظˆط±ع©â€Œط§ط³طھط±غŒظ… ط¨ط§ طھظˆع©ظ† fencing
- `/plan`: ظپط¹ط§ظ„â€Œط³ط§ط²غŒ ط­ط§ظ„طھ طھظپع©ط± ظˆ طھط­ظ„غŒظ„ ط¨ط¯ظˆظ† ط¬ظ‡ط´ ط¨ظ‡ ع©ط¯ظ†ظˆغŒط³غŒ (Karpathy Guidelines)
- `/sim`: ط´ط¨غŒظ‡â€Œط³ط§ط²غŒ ط³ظ†ط§ط±غŒظˆظ‡ط§ ط¯ط± `sim/` ظ‚ط¨ظ„ ط§ط² ط§ظ†طھط´ط§ط± ع©ط§ظ†ظپغŒع¯
- `/qa-gate`: ط§ط±ط²غŒط§ط¨غŒ ط±ط³غŒط¯ ظˆ ط¨ط±ط±ط³غŒ ظˆط¶ط¹غŒطھ rollback
- `/handoff`: ط¨ط§ط²ظ†ظˆغŒط³غŒ `state/HANDOFF.md` ظˆ ط¢ط²ط§ط¯ط³ط§ط²غŒ ظ„غŒط³â€Œظ‡ط§
- `/worktree`: ظ…ط¯غŒط±غŒطھ ظ…ظˆط§ط²غŒâ€Œط³ط§ط²غŒ طھط±ظ…غŒظ†ط§ظ„â€Œظ‡ط§ ط¨ط§ Git Worktrees (ط§ظ„ع¯ظˆغŒ ط¨ظˆط±غŒط³ ع†ط±ظ†غŒ)
- `/doctor`: ط¹غŒط¨â€ŒغŒط§ط¨غŒ ط³ظ„ط§ظ…طھ MCPظ‡ط§ ظˆ ط­ط³ط§ط¨â€Œظ‡ط§
- `/killswitch`: ظ¾ط§غŒط´ ظˆط¶ط¹غŒطھ غŒط§ ظ‡ظ…ع¯ط§ظ…â€Œط³ط§ط²غŒ K1-K5
- `/setup`: ط§ط³ع©ظ† ظ¾ط±ظˆعکظ‡ ظˆ ظ¾غŒط´ظ†ظ‡ط§ط¯ ط§طھظˆظ…ط§ط³غŒظˆظ†â€Œظ‡ط§غŒ ظ‡ظˆط´ظ…ظ†ط¯ ظ…ط·ط§ط¨ظ‚ ط§ط³طھط§ظ†ط¯ط§ط±ط¯ ط±ط³ظ…غŒ `claude-code-setup` ط¢ظ†طھط±ظˆظ¾غŒع©
- `/cost`: ظ¾ط§غŒط´ ظ‡ط²غŒظ†ظ‡ ط¯ظ„ط§ط±غŒ ظˆ طھظˆع©ظ†â€Œظ‡ط§غŒ ظ…طµط±ظپغŒ ط³ط´ظ† ظˆ طھط·ط¨غŒظ‚ ط¨ط§ ط³ظ‚ظپ ط¨ظˆط¯ط¬ظ‡
- `/reason`: ظ¾ط§غŒط´ ظˆ ط§طھطµط§ظ„ ط¨ظ‡ ط´ط¨ع©ظ‡ ظ…ط´ P2P ط§غŒط¬ظ†طھâ€Œظ‡ط§غŒ ظ…ط­ظ„غŒ (Reason Network)

## FreeLLMAPI Universal Free-Tier Token Pool (~7.4B Tokens/Month)
- **Local Gateway**: `http://127.0.0.1:3001/v1` (OpenAI & Anthropic `/v1/messages` compatible)
- **Status & Diagnostics**: `python3 scripts/freellm_cli.py status`
- **Catalog of Free Models**: `python3 scripts/freellm_cli.py catalog --domain coding`
- **Failover**: Auto-switches across 34+ free-tier providers on 429 rate limit with multi-key cooldown.

## غ¹) ط¨ظˆط¯ط¬ظ‡طŒ ظ¾ط§غŒط´ ظ‡ط²غŒظ†ظ‡ ظˆ ط³ظ‚ظپ ظ…طµط±ظپ (Cost Tracking & Budget Governance)

> **ط´ط¹ط§ط± ط­ط§ع©ظ…:** آ«Count it, cap it, then scale itآ» â€” ظ¾غŒط´ ط§ط² ط§ظپط²ظˆط¯ظ† ط³ط§ط¨â€Œط§غŒط¬ظ†طھâ€Œظ‡ط§طŒ ط³ظ‚ظپ ظ‚غŒظ…طھâ€Œع¯ط°ط§ط±غŒ ظˆ طھظ„ظ…طھط±غŒ ط¯ظ‚غŒظ‚ ط§ظ„ط²ط§ظ…غŒ ط§ط³طھ.

### ط³ظ‚ظپ ط¨ظˆط¯ط¬ظ‡ ظ…طµظˆط¨ ط¨ظ‡ ط§ط²ط§غŒ ظ‡ط± طھط³ع© ظˆ ظ…ط±ط­ظ„ظ‡:
- **ط³ظ‚ظپ ع©ظ„ ظ‡ط± طھط³ع© (Hard Stop):** ط­ط¯ط§ع©ط«ط± **غ².غ°غ° ط¯ظ„ط§ط±** (ط³ظ‚ظپ ~غ¶غ°غ°,غ°غ°غ° طھظˆع©ظ†).
- **طھظپع©غŒع© ظ…ط±ط§ط­ظ„ ع†ط±ط®ظ‡ (Stage Budget Limits):**
  - **Ingest / Sync** (`SYNC`, `GAP SCAN`, `CLAIM`): **$0.10**
  - **Plan** (`PLAN`, `ADR`): **$0.25**
  - **Execute** (`SIM`, `EXECUTE`): **$1.00**
  - **Verify** (`VERIFY`, ط´ط¨غŒظ‡â€Œط³ط§ط²غŒ ظˆ طھط³طھâ€Œظ‡ط§): **$0.35**
  - **Gate** (`EMIT`, Two-Key Sign-off): **$0.15**
  - **Commit / Handoff** (`HANDOFF`, ط§ظ†طھط´ط§ط± Claim): **$0.15**

### ظ‚ظˆط§ظ†غŒظ† ط¢ظ‡ظ†غŒظ† ط¨ظˆط¯ط¬ظ‡:
1. **طھظˆظ‚ظپ ط®ظˆط¯ع©ط§ط± (Hard Stop):** ط¨ظ‡ ظ…ط­ط¶ ط¹ط¨ظˆط± ظ‡ط²غŒظ†ظ‡ ظ‡ط± ظ…ط±ط­ظ„ظ‡ ط§ط² ط³ظ‚ظپ ط¯ظ„ط§ط±غŒ ط®ظˆط¯ غŒط§ ط±ط³غŒط¯ظ† ط¨ظ‡ غ¸غ°ظھ ط³ظ‚ظپ ع©ظ„غŒ طھط³ع©طŒ ط¹ط§ظ…ظ„ **ظ…ظˆط¸ظپ ط§ط³طھ ظپظˆط±ط§ظ‹ ظ…طھظˆظ‚ظپ ط´ظˆط¯** ظˆ ط¨ط§ ط§ط¬ط±ط§غŒ `/cost` ط§ط² ع©ط§ط±ط¨ط± طھط§غŒغŒط¯غŒظ‡ ط¨ط®ظˆط§ظ‡ط¯.
2. **ظ¾ط§غŒط´ ظ…ط¯ط§ظˆظ… ط¯ط± ظ†ظˆط§ط± ظˆط¶ط¹غŒطھ (Status Line):** ظ‡ط²غŒظ†ظ‡ ط¯ظ„ط§ط±غŒ ط³ط´ظ† ظˆ طھظˆع©ظ†â€Œظ‡ط§غŒ ظ…طµط±ظپغŒ ظ¾غŒظˆط³طھظ‡ ط¯ط± ظˆط¶ط¹غŒطھ طھط±ظ…غŒظ†ط§ظ„ ع†ط§ظ¾ ظ…غŒâ€Œط´ظˆط¯.
3. **ظ„ط§ع¯ ط§ظ„ط²ط§ظ…غŒ ط¯ط³طھâ€Œط¨ظ‡â€Œط¯ط³طھ ط´ط¯ظ† ط¹ط§ظ…ظ„â€Œظ‡ط§ (Handoff Log):** ظ‡ظˆع© `SubagentStop` ط¯ط± ظ‡ط± ط¨ط§ط± ظ¾ط§غŒط§ظ† ع©ط§ط± ط³ط§ط¨â€Œط§غŒط¬ظ†طھطŒ ظ†ط§ظ… ط¹ط§ظ…ظ„طŒ طھط³ع© ظ…ط­ظˆظ„ظ‡ ظˆ ظ…طµط±ظپ طھظˆع©ظ† ط±ط§ ط¯ط± `logs/handoffs.log` ط«ط¨طھ ظ…غŒâ€Œع©ظ†ط¯.
4. **ط³ظ‚ظپ طµط±غŒط­ ط¯ظˆط± ط³ط§ط¨â€Œط§غŒط¬ظ†طھâ€Œظ‡ط§ (Turn Limits):** ظ‡ط± ط³ط§ط¨â€Œط§غŒط¬ظ†طھ ط¯ط± `.claude/agents/` ط¯ط§ط±ط§غŒ `maxTurns` ط¨غŒظ† غ¸ طھط§ غ±غ² ط¯ظˆط± ط§ط³طھط› ظ‡غŒع† ط¹ط§ظ…ظ„غŒ ط­ظ‚ ع†ط±ط®ط´ ظ†ط§ظ…ط­ط¯ظˆط¯ ظ†ط¯ط§ط±ط¯.
5. **ط¨ط±ط±ط³غŒ ط§ظ„ط²ط§ظ…غŒ ظ¾غŒط´ ط§ط² طھط؛غŒغŒط± ظ…ط±ط­ظ„ظ‡:** ظ‚ط¨ظ„ ط§ط² ط´ط±ظˆط¹ ظ…ط±ط­ظ„ظ‡ ط¨ط¹ط¯غŒطŒ ط¨ط±ط±ط³غŒ ظ‡ط²غŒظ†ظ‡ ط¨ط§ ط¯ط³طھظˆط± ط§ط³ظ„ط´ `/cost` ط§ظ†ط¬ط§ظ… ظ…غŒâ€Œظ¾ط°غŒط±ط¯.

## غ±غ°) ط§ظپط²ظˆظ†ظ‡ ط±ط³ظ…غŒ ط¢ظ†طھط±ظˆظ¾غŒع© (`claude-code-setup`) ظˆ ط§ط³طھط§ظ†ط¯ط§ط±ط¯ ط§طھظˆظ…ط§ط³غŒظˆظ† (ADR-031)

- **ظ†طµط¨ ط§ظپط²ظˆظ†ظ‡ ط±ط³ظ…غŒ ط§ط² ظ…ط§ط±ع©طھâ€Œظ¾ظ„غŒط³ ط¢ظ†طھط±ظˆظ¾غŒع©:**
  ```bash
  /plugin install claude-code-setup@claude-plugins-official
  ```
- **ط¯ط³طھظˆط± ط§ط³ع©ظ† ظ¾ط±ظˆعکظ‡ ظˆ ظ¾غŒط´ظ†ظ‡ط§ط¯ ط§طھظˆظ…ط§ط³غŒظˆظ†:** ط§ط¬ط±ط§غŒ ط¯ط³طھظˆط± ظ…غŒط§ظ†â€Œط¨ط± `/setup` ط¯ط± ط®ط· ظپط±ظ…ط§ظ† Claude Code.
- **ظ‡ظˆع©â€Œظ‡ط§غŒ ط­ظپط§ط¸طھغŒ ظˆ ط§ط¹ظ„ط§ظ†â€Œظ‡ط§ (Hooks Layer):**
  - `hooks/pre_tool.py`: ط¬ظ„ظˆع¯غŒط±غŒ ظپط¹ط§ظ„ ط§ط² طھط؛غŒغŒط± ظ†ط§ط®ظˆط§ط³طھظ‡ ظپط§غŒظ„â€Œظ‡ط§غŒ `.env*`, `package-lock.json`, `poetry.lock` ظˆ ع©ظ„غŒط¯ظ‡ط§.
  - `hooks/notification.py`: ط²ظ†ع¯ ط§ط¹ظ„ط§ظ† طھط±ظ…غŒظ†ط§ظ„ ظˆ ظ„ط§ع¯ ط±ظˆغŒط¯ط§ط¯ظ‡ط§ ط¯ط± `logs/notifications.log` ط¨ط±ط§غŒ `permission_prompt` ظˆ `idle_prompt`.
- **ظ…ط³طھظ†ط¯ط§طھ ط²ظ†ط¯ظ‡ ع©طھط§ط¨ط®ط§ظ†ظ‡â€Œظ‡ط§ (MCP Layer):**
  - ط§طھطµط§ظ„ ط¨ظ‡ ط³ط±ظˆط± `context7` (`@upstash/context7-mcp`) ط¯ط± `.mcp.json` ط¨ط±ط§غŒ ط§ط±ط¬ط§ط¹ ط¨غŒâ€Œط¯ط±ظ†ع¯ ط¨ظ‡ ظ…ط³طھظ†ط¯ط§طھ ط¨ظ‡â€Œط±ظˆط² ظ¾ع©غŒط¬â€Œظ‡ط§ ظˆ ط¬ظ„ظˆع¯غŒط±غŒ ط§ط² طھظˆظ‡ظ… ظ…طھط¯ظ‡ط§غŒ API.
- **ظ…ظ‡ط§ط±طھâ€Œظ‡ط§غŒ ظ¾ط³â€Œط²ظ…غŒظ†ظ‡ ظˆ ع©ظ…ع©غŒ (Skills Layer):**
  - `project-conventions`: ظ…ظ‡ط§ط±طھ ط§ط®طھطµط§طµغŒ ظ¾ط³â€Œط²ظ…غŒظ†ظ‡ (`user-invocable: false`) ط¨ط±ط§غŒ ط§ط¹ظ…ط§ظ„ ط®ظˆط¯ع©ط§ط± ظ‚ظˆط§ط¹ط¯ ظ…ط®ط²ظ† (Stdlib-only ط¯ط± libطŒ ط³ط§ط¹طھ ظ…ط¬ط§ط²غŒطŒ Zero Circular Import ظˆ Two-Key verification).
  - `gen-test`: ظ…ظ‡ط§ط±طھ ط§ط®طھطµط§طµغŒ طھظˆظ„غŒط¯ طھط³طھâ€Œظ‡ط§غŒ ط§ط³طھط§ظ†ط¯ط§ط±ط¯ ط¨ط§ ط³ط§ط®طھط§ط± `unittest.TestCase`.

## غ±غ±) ظ¾ط´طھظ‡ ط·ظ„ط§غŒغŒ ط§ط¨ط²ط§ط±ظ‡ط§غŒ ظ‡ظˆط´ ظ…طµظ†ظˆط¹غŒ غ²غ°غ²غ¶ (ط§ط³طھط§ظ†ط¯ط§ط±ط¯ ط®غŒط±ط§ظ„ظ„ظ‡ ط§ظ„ط¹ظˆط¶غŒ - ADR-032)

> ط¨ط± ط§ط³ط§ط³ ظ…ط±ط¬ط¹ غ²غ°غ²غ¶ ظ…ظ‡ظ†ط¯ط³ ط®غŒط±ط§ظ„ظ„ظ‡ ط§ظ„ط¹ظˆط¶غŒ (@eng_khairallah1):
> **ظ¾ط´طھظ‡ ط·ظ„ط§غŒغŒ طھظˆط³ط¹ظ‡â€Œط¯ظ‡ظ†ط¯ع¯ط§ظ†:** Claude Code (01) + Superpowers (05) + Context7 (17) + Tavily (16)

### ط§ط±ع©ط§ظ† ظ¾غŒع©ط±ط¨ظ†ط¯غŒâ€Œط´ط¯ظ‡ ط¯ط± ظ¾ط±ظˆعکظ‡:
1. **ط¬ط³طھط¬ظˆ ظˆ ط®ط²ط´ طھظ…غŒط² ظˆط¨ (Tavily AI Search - ط§ط¨ط²ط§ط± غ±غ¶):**
   - ط§طھطµط§ظ„ ط³ط±ظˆط± MCP ط¨ظˆظ…غŒ ظ¾ط§غŒطھظˆظ† scripts/mcp_tavily.py ط¨ط§ ط§ط¨ط²ط§ط±ظ‡ط§غŒ 	avily_search, 	avily_extract, 	avily_crawl, 	avily_map.
   - ظپغŒظ„â€Œط§ظˆط± ط®ظˆط¯ع©ط§ط± ط¨ظ‡ ظ…ظˆطھظˆط± ظˆط¨ع¯ط±ط¯غŒ ط¨ظ‡غŒظ†ظ‡ webcmd ط¯ط± طµظˆط±طھ ط¹ط¯ظ… طھظ†ط¸غŒظ… ع©ظ„غŒط¯ API.
2. **ظ…ط¯غŒط±غŒطھ طھط³ع©â€Œظ‡ط§غŒ ط³ط§ط®طھط§ط±غŒط§ظپطھظ‡ (Task Master AI - ط§ط¨ط²ط§ط± غ±غ¸):**
   - ط§ط³ع©ط±غŒظ¾طھ scripts/taskmaster_cli.py ط¬ظ‡طھ طھط¨ط¯غŒظ„ PRD ط¨ظ‡ ظ¾ط§غŒظ¾â€Œظ„ط§غŒظ† ع¯ط±ط§ظپ طھط³ع©â€Œظ‡ط§ ط¯ط± state/tasks.json ط¨ط§ ط¯ط³طھظˆط± /taskmaster.
3. **طھظˆط³ط¹ظ‡ ظ…ط¨طھظ†غŒ ط¨ط± ظ…ط´ط®طµط§طھ (Spec Kit SDD - ط§ط¨ط²ط§ط± غ°غ¶):**
   - ظ…ظ‡ط§ط±طھ spec-kit ظˆ ط¯ط³طھظˆط± /spec ط¨ط±ط§غŒ طھط¯ظˆغŒظ† ظ…ط´ط®طµظ‡ ظ‚ط¨ظ„ ط§ط² ظ‡ط±ع¯ظˆظ†ظ‡ ع©ط¯ظ†ظˆغŒط³غŒ.
4. **ظ…ظ‡ظ†ط¯ط³غŒ ع©ط§ظ†طھع©ط³طھ ظˆ ظ¾ط§غŒط¯ط§ط±غŒ KV-Cache (ط§ط¨ط²ط§ط± غ²غ¹):**
   - ظ…ظ‡ط§ط±طھ context-engineering ط¨ط§ ط§ط³طھط±ط§طھعکغŒ ظ¾غŒط´ظˆظ†ط¯ ظ¾ط§غŒط¯ط§ط± (Stable Prefixes)طŒ ظ…ط§ط³ع© ع©ط±ط¯ظ† ط®ط±ظˆط¬غŒâ€Œظ‡ط§غŒ ط³ظ†ع¯غŒظ† ظˆ ط§ظپط´ط§غŒ طھط¯ط±غŒط¬غŒ (Progressive Disclosure) ط¬ظ‡طھ ع©ط§ظ‡ط´ غ¹غ° ط¯ط±طµط¯غŒ ظ‡ط²غŒظ†ظ‡ ع©ط´ ط¢ظ†طھط±ظˆظ¾غŒع©.
5. **ظ¾عکظˆظ‡ط´ ط¹ظ…غŒظ‚ ظˆ ط±ط§ط³طھغŒâ€Œط¢ط²ظ…ط§غŒغŒ (Deep Research - ط§ط¨ط²ط§ط± غ³غ°):**
   - ظ…ظ‡ط§ط±طھ ظˆ ط¯ط³طھظˆط± /deep-research ط¨ط§ ظپط±ط¢غŒظ†ط¯ غ¸ ظ…ط±ط­ظ„ظ‡â€Œط§غŒ ظˆ ط§ط¹طھط¨ط§ط±ط³ظ†ط¬غŒ ع†ظ†ط¯ظ…ظ†ط¨ط¹غŒ.
6. **طھظˆظ„غŒط¯ ط®ظˆط¯ع©ط§ط± ظ…ظ‡ط§ط±طھ ظˆ ط·ط±ط§ط­غŒ ط±ط§ط¨ط· ع©ط§ط±ط¨ط±غŒ (ط§ط¨ط²ط§ط±ظ‡ط§غŒ غ²غ´ ظˆ غ²غµ ط¢ظ†طھط±ظˆظ¾غŒع©):**
   - ظ…ظ‡ط§ط±طھâ€Œظ‡ط§غŒ ط±ط³ظ…غŒ skill-creator (ط¯ط³طھظˆط± /new-skill) ظˆ rontend-design.
