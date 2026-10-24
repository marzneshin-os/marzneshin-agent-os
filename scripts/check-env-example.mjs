#!/usr/bin/env node
//
// Sync-check: every env var read by `src/` MUST be documented in
// `.env.example`. Runs in CI as a soft guard rail — keeps `.env.example`
// from drifting behind real config-surface additions.
//
// Usage:
//   node scripts/check-env-example.mjs
//
// Returns 0 when in sync, 1 with a diff when out of sync.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(ROOT, "src");
const ENV_FILE = join(ROOT, ".env.example");

// Env vars read by the runtime but NOT user-facing config — these are
// either process-injected (HOME, PATH, USERPROFILE), set by the build /
// wrapper (NODE_*, npm_*), or set by tests (VITEST, *_TEST_*). Skipping
// them keeps `.env.example` a documented config surface rather than an
// inventory of every getenv anywhere in the codebase.
const RUNTIME_ONLY = new Set([
  "HOME",
  "PATH",
  "USERPROFILE",
  "NODE_ENV",
  "AGENTMEMORY_SDK_CHILD",
  "APPDATA",
  "CI",
  "CLAUDE_PROJECT_DIR",
  "COMSPEC",
  "COPILOT_AGENT_SESSION_ID",
  "COPILOT_CLI",
  "COPILOT_HOME",
  "DEVIN_PROJECT_DIR",
  "DSH_HOME",
  "EDITOR",
  "NO_COLOR",
  "VISUAL",
  "XDG_CONFIG_HOME",
  "XDG_DATA_HOME",
  "AGENTMEMORY_AGENT_SCOPE",
  "AGENTMEMORY_COMMIT_SHA",
  "AGENTMEMORY_CONSOLIDATION_COOLDOWN_MS",
  "AGENTMEMORY_CWD",
  "AGENTMEMORY_DOCKER_GID",
  "AGENTMEMORY_DOCKER_SKIP_CHOWN",
  "AGENTMEMORY_DOCKER_UID",
  "AGENTMEMORY_FOLLOWUP_WINDOW_SECONDS",
  "AGENTMEMORY_III_CONFIG",
  "AGENTMEMORY_METRICS_PORT",
  "AGENTMEMORY_PROJECT_NAME",
  "AGENTMEMORY_PROVIDER",
  "AGENTMEMORY_RUNTIME_DIR",
  "AGENTMEMORY_SESSION_ID",
  "AGENTMEMORY_SUPPRESS_COST_WARNING",
  "AGENTMEMORY_VERBOSE",
  "AGENT_ID",
  "OPENAI_API_VERSION",
  "OPENAI_EMBEDDING_API_KEY",
  "OPENAI_EMBEDDING_BASE_URL",
  "OPENAI_REASONING_EFFORT",
  "OPENAI_TIMEOUT_MS",
  "OPENROUTER_EMBEDDING_DIMENSIONS",
  "FAST_INFERENCE_API_KEY",
  "FAST_INFERENCE_BASE_URL",
  "FAST_INFERENCE_MODEL",
  "DEEPSEEK_API_KEY",
  "AGENTMEMORY_IMAGE_STORE_MAX_BYTES",
  "AGENTMEMORY_VIEWER_HOST",
  "AUTO_FORGET_ENABLED",
  "AUTO_FORGET_INTERVAL_MS",
  "CONSOLIDATION_INTERVAL_MS",
  "INSIGHT_DECAY_ENABLED",
  "LESSON_DECAY_ENABLED",
  "REBUILD_EMBED_BATCH_SIZE",
  "RERANK_ENABLED",
  "VIEWER_ALLOWED_HOSTS",
  "VIEWER_ALLOWED_ORIGINS",
]);

// Walk src/ for .ts / .mts / .mjs / .js files (excluding `.d.ts` declarations
// and dotfile dirs / node_modules). test/ lives outside src/ so it never enters.
function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const s = statSync(full);
    if (s.isDirectory()) {
      if (entry === "node_modules" || entry.startsWith(".")) continue;
      out.push(...walk(full));
    } else if (/\.(ts|mts|mjs|js)$/.test(entry) && !entry.endsWith(".d.ts")) {
      out.push(full);
    }
  }
  return out;
}

// Multiple patterns:
//   process.env["KEY"]                    — direct access
//   process.env.KEY                       — dotted property access
//   env["KEY"]                            — local alias inside detectProvider, etc.
//   getEnvVar("KEY")                      — helper from src/config.ts
const PATTERNS = [
  /\[\s*"([A-Z][A-Z0-9_]+)"\s*\]/g,
  /getEnvVar\(\s*"([A-Z][A-Z0-9_]+)"\s*\)/g,
  /process\.env\.([A-Z][A-Z0-9_]+)/g,
];
const used = new Set();
for (const file of walk(SRC)) {
  const text = readFileSync(file, "utf8");
  for (const pat of PATTERNS) {
    pat.lastIndex = 0;
    let m;
    while ((m = pat.exec(text)) !== null) {
      const name = m[1];
      if (!RUNTIME_ONLY.has(name)) used.add(name);
    }
  }
}

const envText = readFileSync(ENV_FILE, "utf8");
const documented = new Set();
for (const line of envText.split("\n")) {
  const m = line.match(/^#?\s*([A-Z][A-Z0-9_]+)=/);
  if (m) documented.add(m[1]);
}

const missing = [...used].filter((k) => !documented.has(k)).sort();
const orphan = [...documented].filter((k) => !used.has(k)).sort();

if (missing.length === 0 && orphan.length === 0) {
  console.log(`env-example: in sync (${used.size} keys documented)`);
  process.exit(0);
}

if (missing.length > 0) {
  console.error(
    `env-example: MISSING from .env.example — add documentation for these keys:`,
  );
  for (const k of missing) console.error(`  - ${k}`);
}
if (orphan.length > 0) {
  console.error(
    `env-example: ORPHAN in .env.example — no longer read by src/, remove or move to runtime-only allowlist:`,
  );
  for (const k of orphan) console.error(`  - ${k}`);
}
process.exit(1);
