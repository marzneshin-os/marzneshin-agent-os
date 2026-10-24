# Workspace-local Antigravity reliability guard

The Antigravity guard is registered only in this workspace's `.agents/hooks.json`. It does not edit Antigravity's global settings. The workspace entries use guard-only mode: they do not invoke the legacy memory-capture scripts. If `.agents/gravitas.local.json` is absent or selects `off`, the guard sends no API events; active `audit` and `enforce` modes send only the guard's hashed event metadata.

## Enable a guarded action

1. Build the workspace bundle with `npm run build` so `plugin/scripts/antigravity-bridge.mjs` contains the current guard implementation.
2. Create an action with a validated `guardContract`. The contract's `enforcement` must be the same as the local mode. For `enforce`, declare at least one workspace-relative allowed path, one validator command, and an acceptance criterion linked to that validator.
3. Copy `.agents/gravitas.local.example.json` to `.agents/gravitas.local.json` and set the action ID and matching mode. The local file is Git-ignored.
4. Make `AGENTMEMORY_URL` and `AGENTMEMORY_SECRET` available to the Antigravity IDE process through its launching environment. Restart the IDE after changing its environment. Keep the secret out of this file and out of repository settings.
5. In Antigravity, open the agent side panel's **Customizations → Hooks** and confirm the workspace `agentmemory-gravitas` bundle is enabled. The workspace hook file uses `SessionStart` to bind one conversation and one canonical workspace root.

Example local config:

```json
{
  "mode": "enforce",
  "actionId": "act_123"
}
```

The local mode must match the persisted action contract. `off` makes the guard pass tool decisions through without sending guard API events. `audit` records policy violations and allows calls. `enforce` denies guarded writes when scope/read evidence is missing, prevents retries until a diagnosed one-use re-arm is supplied, and keeps the Antigravity loop open until fresh validators pass and the Stop event reports `fullyIdle: true`.

## Evidence and limits

- Existing files require a successful full-file `view_file` event before a write; partial line reads do not count. Hooks hash the local file before the write. This records an IDE event and current file hash, not proof that the model consumed or understood the displayed contents.
- Only exact declared synchronous `run_command` validators are permitted in `enforce`. Persistent/async commands are denied. Antigravity's PostToolUse hook does not expose tool output or an exit code; validator evidence therefore means Antigravity emitted a completed event without an `error`, not that the bridge independently inspected the command output.
- Tool argument and command fingerprints, bounded event metadata, and file hashes are stored. Raw hook arguments, file contents, credentials, and validator output are not written by the guard state.
- Hooks are not an OS sandbox. They cannot stop edits made outside observed Antigravity tools, close time-of-check/time-of-use races, or provide cross-replica atomicity. The guard uses the local service's per-action process lock and is intended for one local service instance.
- Removing or disabling the local hook config disables write-time enforcement. The persisted action completion gate still rejects guarded completion when fresh evidence is missing.

Antigravity's standalone IDE reads workspace hooks from `.agents/hooks.json` and offers management in **Customizations → Hooks**. Workspace Skills are loaded from `.agents/skills/`. Native custom-subagent orchestration is currently documented for the Antigravity App and CLI, not the standalone IDE; this project's orchestrator therefore reports unsupported specialist dispatch instead of inventing a result.
