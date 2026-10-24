import { describe, it, expect } from "vitest";
import { execFileSync } from "node:child_process";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { isAbsolute, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import {
  buildMergedAntigravityHooks,
  containsSpaces,
  type AntigravityHookManifest,
} from "../src/cli/connect/antigravity-hooks.js";
import { findPluginRoot } from "../src/cli/connect/codex-hooks.js";
import {
  hashValue,
  isWithinWorkspace,
  normalizeGuardConfig,
  normalizePayload,
  resolveWorkspaceTarget,
  responseFor,
  stableJson,
  targetsFor,
} from "../src/hooks/antigravity-bridge.js";

const PLUGIN_ROOT = resolve(__dirname, "..", "plugin");

function build(existing: AntigravityHookManifest | null = null) {
  return buildMergedAntigravityHooks(existing, findPluginRoot());
}

type Handler = { type: string; command: string; timeout?: number };

function eventEntries(bundle: unknown, event: string) {
  return (bundle as Record<string, unknown>)[event] as {
    matcher?: string;
    hooks: Handler[];
  }[];
}

function handlers(bundle: unknown, event: string) {
  return (bundle as Record<string, unknown>)[event] as Handler[];
}

/** Every handler in a bundle, across both of agy's event shapes. */
function allCommands(bundle: unknown): string[] {
  const out: string[] = [];
  for (const value of Object.values(bundle as Record<string, unknown>)) {
    if (!Array.isArray(value)) continue;
    for (const entry of value) {
      const nested = (entry as { hooks?: Handler[] }).hooks;
      for (const h of nested ?? [entry as Handler]) out.push(h.command);
    }
  }
  return out;
}

describe("buildMergedAntigravityHooks", () => {
  it("rewrites ${CLAUDE_PLUGIN_ROOT} to absolute pluginRoot in every command", () => {
    for (const bundle of Object.values(build())) {
      for (const command of allCommands(bundle)) {
        expect(command).not.toContain("${CLAUDE_PLUGIN_ROOT}");
        expect(command).toContain(`${PLUGIN_ROOT}/scripts/`);
      }
    }
  });

  it("leaves the resolved script path unquoted, as agy's parser requires", () => {
    // agy does not run `command` through a shell and does not strip quotes
    // before splitting, so `node "<root>/x.mjs"` makes node look for a module
    // whose name literally begins with a double quote. Verified on 1.0.15.
    for (const bundle of Object.values(build())) {
      for (const command of allCommands(bundle)) {
        expect(command).not.toContain('"');
      }
    }
  });

  it("shapes tool events and lifecycle events the way agy parses them", () => {
    // Only tool events take the { matcher, hooks } wrapper. Wrapping a
    // lifecycle event makes agy reject the entire file, which silently
    // disables every other bundle in it too. Verified on agy 1.0.15.
    const bundle = build()["agentmemory"]!;
    for (const event of ["PreToolUse", "PostToolUse"]) {
      for (const entry of eventEntries(bundle, event)) {
        expect(Array.isArray(entry.hooks), event).toBe(true);
        expect(entry, event).not.toHaveProperty("command");
      }
    }
    for (const event of ["SessionStart", "Stop"]) {
      for (const handler of handlers(bundle, event)) {
        expect(handler.type, event).toBe("command");
        expect(handler.command, event).toContain("antigravity-bridge.mjs");
        expect(handler, event).not.toHaveProperty("hooks");
        expect(handler, event).not.toHaveProperty("matcher");
      }
    }
  });

  it("flags a plugin path that agy could never execute", () => {
    // Quoted or not, a space truncates the argument — there is no escaping
    // form that works, so the installer has to refuse instead of writing a
    // bundle that loads but never fires.
    expect(containsSpaces("C:/Program Files/agentmemory/plugin")).toBe(true);
    expect(containsSpaces("/opt/agentmemory/plugin")).toBe(false);
  });

  it("registers under a single named bundle, as Antigravity's schema requires", () => {
    expect(Object.keys(build())).toEqual(["agentmemory"]);
    expect(build()["agentmemory"]!["enabled"]).toBe(true);
  });

  it("only wires events Antigravity actually dispatches", () => {
    const bundle = build()["agentmemory"]!;
    const events = Object.keys(bundle).filter((k) => k !== "enabled");
    // PostInvocation is intentionally unwired: PostToolUse already captures
    // the work, so firing both would double-record every turn.
    expect(events.sort()).toEqual(
      ["SessionStart", "PreToolUse", "PostToolUse", "Stop"].sort(),
    );
  });

  it("scopes PreToolUse to the file tools agy actually exposes", () => {
    const matcher = eventEntries(build()["agentmemory"], "PreToolUse")[0]!
      .matcher!;
    for (const tool of ["view_file", "edit_file", "write_to_file", "multi_replace_file_content", "grep_search", "run_command"]) {
      expect(matcher.split("|")).toContain(tool);
    }
  });

  it("keeps user-authored hook bundles untouched", () => {
    const existing: AntigravityHookManifest = {
      "block-run-command": {
        enabled: true,
        PreToolUse: [
          {
            matcher: "run_command",
            hooks: [{ type: "command", command: "/usr/local/bin/deny.sh" }],
          },
        ],
      },
    };
    const merged = build(existing);
    expect(merged["block-run-command"]).toEqual(existing["block-run-command"]);
    expect(merged["agentmemory"]).toBeDefined();
  });

  it("replaces a stale agentmemory bundle instead of duplicating it", () => {
    const stale: AntigravityHookManifest = {
      "agentmemory-legacy": {
        enabled: true,
        Stop: [
          {
            hooks: [
              {
                type: "command",
                command: `node "${PLUGIN_ROOT}/scripts/removed-hook.mjs" Stop`,
              },
            ],
          },
        ],
      },
    };
    const merged = build(stale);
    expect(merged["agentmemory-legacy"]).toBeUndefined();
    expect(Object.keys(merged)).toEqual(["agentmemory"]);
  });

  it("recognises a stale bundle written in the flat lifecycle shape too", () => {
    // Ownership detection has to see through both shapes, or a re-install
    // leaves the old bundle behind and agy runs two copies of every hook.
    const stale: AntigravityHookManifest = {
      "agentmemory-legacy": {
        enabled: true,
        Stop: [
          {
            type: "command",
            command: `node ${PLUGIN_ROOT}/scripts/removed-hook.mjs Stop`,
          },
        ],
      },
    };
    expect(build(stale)["agentmemory-legacy"]).toBeUndefined();
  });

  it("re-install is idempotent", () => {
    const first = build();
    expect(build(first)).toEqual(first);
  });

  it("keeps a pluginRoot containing $-replacement patterns literal", () => {
    // `String.prototype.replace` with a string argument reads `$$`, `$&`,
    // "$`" and `$'` in the replacement as patterns. An install path holding
    // any of them would otherwise be rewritten into a broken command, and
    // the only symptom would be hooks that silently never fire.
    const tmp = mkdtempSync(join(tmpdir(), "am-antigravity-"));
    try {
      const oddRoot = join(tmp, "plug$&$$in");
      mkdirSync(join(oddRoot, "hooks"), { recursive: true });
      copyFileSync(
        join(PLUGIN_ROOT, "hooks", "hooks.antigravity.json"),
        join(oddRoot, "hooks", "hooks.antigravity.json"),
      );

      const command = handlers(
        buildMergedAntigravityHooks(null, oddRoot)["agentmemory"],
        "Stop",
      )[0]!.command;

      expect(command).toContain(`${oddRoot}/scripts/`);
      expect(command).not.toContain("${CLAUDE_PLUGIN_ROOT}");
    } finally {
      rmSync(tmp, { recursive: true, force: true });
    }
  });
});

describe("workspace Antigravity hook registration", () => {
  it("adds the local reliability bundle while preserving existing workspace bundles", () => {
    const hooks = JSON.parse(readFileSync(join(__dirname, "..", ".agents", "hooks.json"), "utf8").replace(/^\uFEFF/, "")) as Record<string, Record<string, unknown>>;
    expect(hooks["superpowers-check"]).toBeDefined();
    expect(hooks["auto-approve-gate"]).toBeDefined();
    const guard = hooks["agentmemory-gravitas"]!;
    expect(guard["SessionStart"]).toBeDefined();
    expect(guard["Stop"]).toBeDefined();
    const pre = (guard["PreToolUse"] as { matcher: string }[])[0]!.matcher;
    expect(pre.split("|")).toContain("multi_replace_file_content");
    expect(pre.split("|")).toContain("run_command");
    expect(allCommands(guard)).toEqual(expect.arrayContaining(["node ./plugin/scripts/antigravity-bridge.mjs SessionStart --guard-only"]));
    expect(allCommands(guard).every((command) => command.endsWith("--guard-only"))).toBe(true);
  });
});

describe("antigravity bridge payload normalization", () => {
  it("maps conversationId and workspacePaths onto the canonical fields", () => {
    const out = normalizePayload("PostToolUse", {
      conversationId: "conv_123",
      workspacePaths: ["/repo/app"],
      transcriptPath: "/tmp/t.jsonl",
    });
    expect(out["session_id"]).toBe("conv_123");
    expect(out["cwd"]).toBe("/repo/app");
    expect(out["transcript_path"]).toBe("/tmp/t.jsonl");
    expect(out["hook_event_name"]).toBe("PostToolUse");
  });

  it("flattens toolCall into tool_name/tool_input with Cascade names mapped", () => {
    const out = normalizePayload("PreToolUse", {
      conversationId: "c1",
      toolCall: {
        name: "view_file",
        args: { AbsolutePath: "/repo/src/index.ts", StartLine: 1 },
      },
    });
    expect(out["tool_name"]).toBe("read");
    expect(out["native_tool_name"]).toBe("view_file");
    expect((out["tool_input"] as Record<string, unknown>)["file_path"]).toBe(
      "/repo/src/index.ts",
    );
    // Original PascalCase args survive for anything downstream that wants them.
    expect((out["tool_input"] as Record<string, unknown>)["StartLine"]).toBe(1);
  });

  it("normalizes a payload captured verbatim from agy 1.0.15", () => {
    // Recorded by pointing a probe hook at a live `agy --print` run. Note
    // there is no `cwd` key at all, and `workspacePaths` came back empty in
    // headless mode — the session id has to come from `conversationId`.
    const out = normalizePayload("PreToolUse", {
      artifactDirectoryPath:
        "C:/Users/u/.gemini/antigravity-cli/brain/53642203-62f2-45e9-bda3-b1304c61bc99",
      conversationId: "53642203-62f2-45e9-bda3-b1304c61bc99",
      modelName: "gemini-3.6-flash-high",
      stepIdx: 3,
      toolCall: {
        args: { DirectoryPath: "C:\\Users\\u\\.gemini\\antigravity-cli" },
        name: "list_dir",
      },
      transcriptPath:
        "C:/Users/u/.gemini/antigravity-cli/brain/53642203/.system_generated/logs/transcript_full.jsonl",
      workspacePaths: [],
    });

    expect(out["session_id"]).toBe("53642203-62f2-45e9-bda3-b1304c61bc99");
    expect(out["tool_name"]).toBe("glob");
    expect(out["native_tool_name"]).toBe("list_dir");
    expect((out["tool_input"] as Record<string, unknown>)["path"]).toBe(
      "C:\\Users\\u\\.gemini\\antigravity-cli",
    );
    expect(out["transcript_path"]).toContain("transcript_full.jsonl");
    // Fields agy sends that no bundled hook reads still survive the trip.
    expect(out["modelName"]).toBe("gemini-3.6-flash-high");
    expect(out["stepIdx"]).toBe(3);
  });

  it("maps every PascalCase arg the canonical hooks read", () => {
    const cases: [string, string, string][] = [
      ["AbsolutePath", "file_path", "/repo/a.ts"],
      ["TargetFile", "file_path", "/repo/b.ts"],
      ["DirectoryPath", "path", "/repo/src"],
      ["SearchDirectory", "path", "/repo/test"],
      ["Pattern", "pattern", "*.ts"],
      ["Query", "pattern", "normalizePayload"],
      ["CommandLine", "command", "npm test"],
    ];
    for (const [from, to, value] of cases) {
      const input = normalizePayload("PreToolUse", {
        toolCall: { name: "view_file", args: { [from]: value } },
      })["tool_input"] as Record<string, unknown>;
      expect(input[to], `${from} -> ${to}`).toBe(value);
      // The original key survives alongside the canonical one.
      expect(input[from], from).toBe(value);
    }
  });

  it("does not let a mapped alias clobber an explicit canonical key", () => {
    const input = normalizePayload("PreToolUse", {
      toolCall: {
        name: "edit_file",
        args: { TargetFile: "/repo/alias.ts", file_path: "/repo/explicit.ts" },
      },
    })["tool_input"] as Record<string, unknown>;
    expect(input["file_path"]).toBe("/repo/explicit.ts");
  });

  it("passes unmapped tool names through unchanged", () => {
    const out = normalizePayload("PostToolUse", {
      toolCall: { name: "run_command", args: { CommandLine: "npm test" } },
    });
    expect(out["tool_name"]).toBe("run_command");
    expect((out["tool_input"] as Record<string, unknown>)["command"]).toBe(
      "npm test",
    );
  });

  it("falls back to a placeholder session id rather than dropping the event", () => {
    expect(normalizePayload("Stop", {})["session_id"]).toBe("unknown");
  });
});

describe("antigravity bridge stdout contract", () => {
  // agy documents `decision` as required on PreToolUse output and treats a
  // response without it as a denial — a bare `{}` there makes the agent
  // refuse every matched tool call instead of passively capturing it.
  it("uses the guard result for tool decisions and enforces guarded stops", () => {
    expect(JSON.parse(responseFor("PreToolUse", { decision: "deny", reason: "out of scope" }, "enforce"))).toEqual({
      decision: "deny",
      reason: "out of scope",
    });
    expect(JSON.parse(responseFor("PreToolUse", undefined, "off"))).toEqual({ decision: "allow" });
    expect(JSON.parse(responseFor("Stop", { allowed: false, reason: "missing validator" }, "enforce", true))).toEqual({
      decision: "continue",
      reason: "missing validator",
    });
    expect(JSON.parse(responseFor("Stop", { allowed: true }, "enforce", true))).toEqual({ decision: "allow" });
    expect(JSON.parse(responseFor("Stop", { allowed: false }, "audit", false))).toEqual({ decision: "allow" });
    for (const event of ["SessionStart", "PostToolUse", ""]) {
      expect(JSON.parse(responseFor(event)), event).toEqual({});
    }
  });

  it("writes that contract to stdout when the bundled script actually runs", () => {
    const script = join(PLUGIN_ROOT, "scripts", "antigravity-bridge.mjs");
    const run = (event: string) =>
      execFileSync(process.execPath, [script, event], {
        input: JSON.stringify({
          conversationId: "c1",
          toolCall: { name: "view_file", args: { AbsolutePath: "/repo/a.ts" } },
        }),
        encoding: "utf-8",
        // No server is listening on port 1, so every capture fetch fails
        // fast: this asserts the response survives a failed capture, which
        // is exactly the case where a swallowed error could emit nothing.
        env: { ...process.env, AGENTMEMORY_URL: "http://127.0.0.1:1" },
        stdio: ["pipe", "pipe", "ignore"],
      });

    expect(JSON.parse(run("PreToolUse"))).toEqual({ decision: "allow" });
    expect(JSON.parse(run("PostToolUse"))).toEqual({});
  });
});

describe("antigravity bridge event routing", () => {
  it("binds once on SessionStart without treating model invocations as user prompts", () => {
    expect(targetsFor("SessionStart", {})).toEqual(["session-start.mjs"]);
    expect(targetsFor("PreInvocation", { invocationNum: 0 })).toEqual([]);
    expect(targetsFor("PreInvocation", { invocationNum: 4 })).toEqual([]);
  });

  it("does not synthesize a user prompt for a missing invocation number", () => {
    expect(targetsFor("PreInvocation", {})).toEqual([]);
  });

  it("keeps workspace-local guard hooks isolated from legacy telemetry scripts", () => {
    for (const event of ["SessionStart", "PreToolUse", "PostToolUse", "Stop"]) {
      expect(targetsFor(event, {}, true)).toEqual([]);
    }
  });

  it("closes the session on Stop", () => {
    expect(targetsFor("Stop", {})).toEqual(["stop.mjs", "session-end.mjs"]);
  });

  it("ignores PostInvocation to avoid double-capturing a turn", () => {
    expect(targetsFor("PostInvocation", {})).toEqual([]);
  });
});

describe("workspace-local Gravitas config and path evidence", () => {
  it("defaults to off and rejects enabled config without an action id", () => {
    expect(normalizeGuardConfig(undefined)).toEqual({ valid: true, config: { mode: "off" } });
    expect(normalizeGuardConfig({ mode: "enforce" })).toMatchObject({ valid: false });
    expect(normalizeGuardConfig({ mode: "other", actionId: "a1" })).toMatchObject({ valid: false });
    expect(normalizeGuardConfig({ mode: "audit", actionId: "a1" })).toEqual({
      valid: true,
      config: { mode: "audit", actionId: "a1" },
    });
  });

  it("canonicalizes workspace paths, hashes existing files, and rejects traversal", () => {
    const root = realpathSync.native(mkdtempSync(resolve(join(tmpdir(), "am-antigravity-guard-"))));
    const outside = `${root}-outside`;
    try {
      mkdirSync(join(root, "src"), { recursive: true });
      const file = join(root, "src", "sample.ts");
      writeFileSync(file, "export const value = 1;\n");
      expect(isAbsolute(root)).toBe(true);
      expect(isAbsolute(file)).toBe(true);
      expect(resolveWorkspaceTarget(root, file)).toMatchObject({
        relativePath: "src/sample.ts",
        fileHash: expect.stringMatching(/^[a-f0-9]{64}$/),
      });
      expect(resolveWorkspaceTarget(root, join(root, "..", "outside.ts"))).toMatchObject({ error: expect.any(String) });
      mkdirSync(outside, { recursive: true });
      writeFileSync(join(outside, "secret.ts"), "export const outside = true;\n");
      const link = join(root, "outside-link");
      let linkCreated = false;
      try {
        symlinkSync(outside, link, process.platform === "win32" ? "junction" : "dir");
        linkCreated = true;
      } catch (error) {
        const code = (error as NodeJS.ErrnoException).code;
        if (code !== "EPERM" && code !== "EACCES") throw error;
      }
      expect(isWithinWorkspace(root, resolve(outside))).toBe(false);
      if (linkCreated) {
        expect(resolveWorkspaceTarget(root, join(link, "secret.ts"))).toMatchObject({ error: expect.any(String) });
      }
    } finally {
      rmSync(root, { recursive: true, force: true });
      rmSync(outside, { recursive: true, force: true });
    }
  });

  it("hashes stable canonical arguments without retaining raw values", () => {
    expect(stableJson({ z: 1, a: { y: true, x: "v" } })).toBe('{"a":{"x":"v","y":true},"z":1}');
    expect(hashValue({ z: 1, a: 2 })).toBe(hashValue({ a: 2, z: 1 }));
    expect(hashValue({ command: "npm test" })).toMatch(/^[a-f0-9]{64}$/);
  });
});

describe("active local bridge failure behavior", () => {
  it("denies guarded writes and keeps Stop open when the local service is unavailable", () => {
    const root = mkdtempSync(resolve(join(tmpdir(), "am-antigravity-bridge-")));
    try {
      mkdirSync(join(root, ".agents"), { recursive: true });
      mkdirSync(join(root, "src"), { recursive: true });
      writeFileSync(join(root, ".agents", "gravitas.local.json"), JSON.stringify({ mode: "enforce", actionId: "act_guarded" }));
      const bridge = resolve(__dirname, "..", "src", "hooks", "antigravity-bridge.ts");
      const tsxLoader = resolve(__dirname, "..", "node_modules", "tsx", "dist", "loader.mjs");
      const run = (event: string, payload: Record<string, unknown>) =>
        JSON.parse(execFileSync(process.execPath, ["--import", pathToFileURL(tsxLoader).href, bridge, event], {
          cwd: root,
          input: JSON.stringify(payload),
          encoding: "utf8",
          env: {
            ...process.env,
            AGENTMEMORY_URL: "http://127.0.0.1:1",
            AGENTMEMORY_SECRET: "test-secret",
          },
        })) as Record<string, unknown>;

      const writeDecision = run("PreToolUse", {
        conversationId: "conv_guarded",
        workspacePaths: [root],
        stepIdx: 0,
        toolCall: { name: "write_to_file", args: { TargetFile: join(root, "src", "new.ts"), CodeContent: "content" } },
      });
      expect(writeDecision).toMatchObject({ decision: "deny" });

      const stopDecision = run("Stop", {
        conversationId: "conv_guarded",
        workspacePaths: [root],
        executionNum: 0,
        fullyIdle: true,
      });
      expect(stopDecision).toMatchObject({ decision: "continue" });
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});
