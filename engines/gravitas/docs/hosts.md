# Hosts

## Antigravity (first-class)

- **Core**: portable skill at `.agents/skills/gravitas/` (progressive procedures).
- **Native**: `gravitas-native` plugin — `rules/` invariants (always-on),
  hook enforcement (`PreToolUse/PostToolUse/PostInvocation/Stop`),
  specialists in `agents/`. Install: `agy plugin install dist/gravitas-antigravity`.
- Full lifecycle: action lock, scope guard, read-before-write, duplicate
  prevention, evidence ledger, completion gate.
- Hook payload versions are fixture-pinned (`tests/fixtures/antigravity/`).

## OpenCode (first-class)

- Invariants via project `AGENTS.md`, procedures via shared skills,
  specialists via `.opencode/agents/`, enforcement via `permission`
  profiles + the `tool.execute.before` plugin shim (`gravitas guard`).
- Install: `gravitas init --host opencode --profile fast|balanced|strict`.
- Compatibility (verified 2026-10-15): OpenCode v2.0.28 installed; shim
  hook signature `(input, output)` with args in `output.args` matches the
  official plugin docs verbatim (incl. the `tool.execute.before` arg-mutation
  example); project `.opencode/plugins/` auto-load confirmed in docs, so
  `gravitas init` output lands on the documented load path. No live
  model-backed tool run performed (would spend paid quota); V1
  `permission`-schema profiles ship in `adapters/opencode/permissions/`
  (V1 runtime not installed here -- unvalidated). v2 uses a
  `permissions`-array schema (see `adapters/opencode/README.md`).
- Failure policy is fail-closed: unreachable/slow/broken guard denies
  mutating calls; see shim header.

## Capability differences (honest)

| Capability | Antigravity Native | OpenCode |
|---|---|---|
| Write/scope gating | hook deny | shim deny + permissions |
| Destructive confirm | `force_ask` | hard deny (no ask channel) |
| Completion gate | automatic Stop hook | manual (`summarize` + evidence) |
| Evidence ledger | automatic | manual via CLI |
| Session isolation | per-conversation | per-workspace contract |
| Guard dependency | none (in-process) | python3 + `gravitas` on PATH |

## Generic Agent Skills

Without native enforcement, the skill still works: invariants,
policy records, verification hierarchy, and output format are
host-independent. Enforcement degrades to instruction-following;
say so in the project docs.
