# Gravitas-Inspired Antigravity Reliability Guard

## Goal

Implement an opt-in, workspace-local reliability guard for Antigravity tasks, inspired by Gravitas, and gate guarded action completion on fresh evidence from observed Antigravity hook events across the REST API, action updates, and lease release. Preserve existing local work. Do not change global IDE settings, commit, push, deploy, or claim OS-level isolation.

## Approved invariants

- Runtime mode defaults to `off`; enabling `audit` or `enforce` is explicit and workspace-local.
- Actions without a guard contract retain legacy behavior.
- Guarded actions require an explicit action/session/workspace-root binding, declared write scope, observed read-before-write events for existing files, and current validator evidence for every required acceptance criterion before completion. This is evidence from events the IDE exposes, not proof the model consumed file contents or no external edit occurred.
- A successful mutation invalidates prior validator evidence. A failed tool-call fingerprint cannot be retried unchanged; re-arming is a one-use grant bound to the failed fingerprint, requires a diagnosis, and the next canonical argument fingerprint must differ.
- PreToolUse must return Antigravity's actual `allow`, `ask`, or `deny` decision. In enforce mode, inability to reach the guard service fails closed for guarded writes and completion-sensitive operations.
- Hook path checks use local canonical paths and reject traversal/symlink escapes. This reduces accidental scope violations; hooks do not eliminate TOCTOU or shell/OS bypasses.
- Store fingerprints and bounded metadata only, never raw tool arguments, file contents, validator output, or credentials.
- `StateKV` has no documented CAS/transaction primitive. Use per-action process-local serialization and deduplicate/order events by session, step index, phase, tool name, and argument hash. Reject stale/out-of-order events and fail closed on bounded-state overflow in enforce mode. Document the single-local-service limitation; make no cross-replica atomicity claim.
- Orchestration reports success only for work actually dispatched and validated. It must not silently invent a successful subagent result, auto-commit/merge, or delete failed worktree data.

## Guard contract

- `Action.guardContract` is optional. Its shape is `enforcement: "audit" | "enforce"`, `allowedPaths: string[]` (workspace-relative), `acceptanceCriteria: { id, description, validatorId }[]`, and `validators: { id, command }[]`.
- Guard state is keyed by action ID and records one bound Antigravity `conversationId` and one canonical workspace root (reject multi-root binding), action-wide mutation revision, bounded read receipts (`relativePath` + SHA-256), bounded failed-call hashes, recent event IDs, and validator evidence (`validatorId`, passed flag, mutation revision, step index, timestamp, exact command hash).
- The single `mem::gravitas-guard` function accepts a strict discriminated operation: `bind`, `pre_tool`, `post_tool`, `rearm_failure`, or `completion_check`. The corresponding authenticated REST endpoint is `POST /agentmemory/gravitas/event`; it forwards only validated, whitelisted fields.
- `pre_tool` receives native tool name, session, pinned workspace root, workspace-relative path where applicable, current file hash where applicable, a hash of normalized arguments, and a command hash for `run_command`. `post_tool` receives tool outcome and hashes only. `rearm_failure` requires the failed-call hash plus non-empty diagnosis; it grants one attempt only when the next canonical argument hash differs from the failed attempt.
- Validator evidence is fresh only when it passes and its recorded mutation revision equals the action's current revision. A successful file mutation increments that revision and clears all validator evidence.
- Completion is allowed when every declared criterion maps to a passing validator at the current revision and Antigravity reports `fullyIdle: true`. For guarded actions with `enforcement: "audit"`, missing evidence is audited but does not block legacy completion. For `enforce`, both action-update and lease-release reject completion; the lease gate runs before writing lease/action/audit state.
- The workspace-only config `.agents/gravitas.local.json` holds mode (`off|audit|enforce`) and `actionId`; it is ignored by Git. `AGENTMEMORY_URL`/`AGENTMEMORY_SECRET` remain environment-only. The persisted action contract controls completion enforcement; local mode cannot downgrade a persisted `enforce` contract. A local/contract mismatch fails closed and must be corrected. In `audit`, violations are reported and calls proceed. In `enforce`, only exact declared synchronous validators are allowed through the shell rule.
- Read-before-write is based on a successful full-file `view_file` event and a local file hash; Antigravity does not expose view output to `PostToolUse`, so this cannot prove the model received or understood the contents. Partial line-range reads do not count. Existing-file writes must still match that local hash at pre-tool time. New files need no read receipt. `run_command` validator evidence is rejected if `RunPersistent` is true or `WaitMsBeforeAsync` is supplied; Stop must report `fullyIdle: true`. Hooks cannot prove absence of external/MCP edits, defeat TOCTOU, or act as an OS sandbox.

## Implementation stages

1. **Contract and guard core** — Add typed task contract, per-action guard state, bounded event/fingerprint/evidence records, shared guard functions, audit operations, and completion-validation helper. Register the new functions. Add focused unit tests for mode compatibility, scope decisions, failed retry re-arming, validator freshness, and completion denial.
2. **Completion-path integration** — Extend action creation input and the existing MCP/REST action-create whitelists to accept a validated optional guard contract. Route both `mem::action-update(status=done)` and `mem::lease-release(result)` through the same completion gate before mutating action state. Preserve legacy behavior for unguarded actions. Test both success and rejection paths.
3. **Workspace-local Antigravity hooks** — Merge a uniquely named hook bundle into `.agents/hooks.json` without removing existing entries. Update the bridge, plugin hook manifest, and generated plugin script. Use documented `SessionStart` for binding; do not treat `PreInvocation` as a prompt event. Support `off|audit|enforce`, explicit action/root binding, local realpath/symlink checks, read/write/failure/validator events, Stop output with required `decision` (`continue` on missing proof; `allow` otherwise), `fullyIdle` handling, zero-based invocation semantics, bounded HTTP requests, and fail-closed enforcement. Add tests for path escapes, ambiguous/unknown binding, service failures, Stop response, duplicate/stale events, and invocation zero.
4. **Orchestrator safety** — Remove fake success for unsupported specialist dispatch, ensure the prompt is actually used by a real dispatcher or return an explicit unsupported/skipped result, propagate merge failures, and remove automatic commit/merge/destructive cleanup behavior. Refuse empty fallback sandboxes. Add tests that failed isolation preserves worktree data and no branch/commit is created by orchestration.
5. **Docs and generated consistency** — Document workspace-only setup, required secret/action binding, safe mode default, limitations, risk-scaled `direct|compact|deep|replan` policy, and opt-in enforcement. Update REST endpoint counts if routes are added. Rebuild only generated plugin assets through the project build path and inspect the resulting diff.
6. **Verification and adversarial review** — Run focused tests first, then `npm test`, `npm run build`, skill/consistency checks, and relevant Python/orchestrator checks. Review the final diff against the user's pre-existing changes, inspect failure paths and data retention, and report exact evidence and residual limits. Do not stage or commit.

## Work ownership

- Core/data/completion gates: `src/types.ts`, `src/state/schema.ts`, new guard function module, `src/functions/actions.ts`, `src/functions/leases.ts`, focused tests.
- Hook/local enforcement: `src/hooks/antigravity-bridge.ts`, `.agents/hooks.json`, `plugin/hooks/hooks.antigravity.json`, generated `plugin/scripts/antigravity-bridge.mjs`, hook tests, targeted docs.
- Orchestrator isolation/status behavior: `scripts/orchestrator/*` and isolated tests.
- Integration owner: REST/MCP registration and all count/manifests; final test/build/diff review.

## Acceptance criteria

- Default-off and unguarded legacy behavior are covered by tests.
- A guarded task cannot be completed from either action-update or lease-release without all required fresh evidence from observed hook events; lease state remains intact when the gate rejects completion.
- Mutations invalidate evidence; unchanged retries after failure are rejected until an explicit diagnosis/context change.
- Enforce-mode local hooks reject out-of-scope paths, traversal, symlink escapes, ambiguous roots, stale/duplicate events, and asynchronous validators; API/service failure does not silently allow guarded writes.
- Existing `.agents/hooks.json` bundles remain intact and workspace-local integration is visible in Antigravity's hook manager.
- Orchestrator success reflects actual completed work; no implicit commit/merge or destructive fallback cleanup occurs.
- Tests, build, and consistency checks report their real exit status; no successful handoff/receipt is fabricated.

