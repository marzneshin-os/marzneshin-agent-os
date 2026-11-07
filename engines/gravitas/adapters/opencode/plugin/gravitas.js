/**
 * Gravitas enforcement shim for OpenCode.
 *
 * Maps OpenCode tool calls onto the normalized Gravitas action model and
 * asks `gravitas guard` (Python policy engine) for a decision. Denials
 * throw, which blocks the tool call. There is no "ask" channel in
 * tool.execute.before, so force_ask resolves to a hard deny here -- a
 * documented, deliberate difference from Antigravity.
 *
 * OpenCode V1/V2 both invoke `tool.execute.before` as
 * `(input {tool, sessionID, callID}, output {args})`. Tool arguments live
 * in the SECOND parameter; reading them from `input` yields `{}` and would
 * silently bypass enforcement, so this shim requires `(input, output)`.
 *
 * Failure policy (fail-closed): when protection is enabled, an unreachable
 * guard binary, timeout, nonzero exit, unparseable output, or unknown
 * verdict DENIES the call. Read-only tools with explicit empty args are
 * still evaluated by the guard; mutating tools (bash/edit/write/patch)
 * with missing arguments are denied locally without consulting the guard.
 * The shim never shells to itself (it invokes `gravitas guard` only).
 *
 * Requires `gravitas` (pip install gravitas) and python3 on PATH.
 */

import { execFileSync } from "node:child_process";

const MUTATING_TOOLS = new Set(["bash", "edit", "write", "patch"]);

function hasMutatingArgs(tool, args) {
  if (!MUTATING_TOOLS.has(tool)) return true;
  if (!args || typeof args !== "object") return false;
  if (tool === "bash") return Boolean(args.command);
  return Boolean(args.filePath || args.path);
}

export function toEnvelope(tool, args, directory) {
  const envelope = {
    tool: String(tool || ""),
    args: args && typeof args === "object" ? args : {},
    conversation_id: "",
    workspace_roots: directory ? [directory] : [],
    host: "opencode",
    event: "before_action",
  };
  const a = envelope.args;
  switch (envelope.tool) {
    case "read":
      envelope.tool = "view_file";
      envelope.args = { AbsolutePath: a.filePath || a.path || "" };
      break;
    case "edit":
    case "write":
      envelope.tool = "write_to_file";
      envelope.args = { TargetFile: a.filePath || a.path || "" };
      break;
    case "patch":
      envelope.tool = "replace_file_content";
      envelope.args = { target_file: a.filePath || a.path || "" };
      break;
    case "bash":
      envelope.tool = "run_command";
      envelope.args = { CommandLine: a.command || "" };
      break;
    case "grep":
      envelope.tool = "grep_search";
      break;
    case "glob":
      envelope.tool = "find_by_name";
      break;
    case "list":
      envelope.tool = "list_dir";
      break;
    default:
      break;
  }
  return envelope;
}

function decide(directory, tool, args) {
  const envelope = toEnvelope(tool, args, directory);
  let raw;
  try {
    raw = execFileSync("gravitas", ["guard", "--envelope", JSON.stringify(envelope)], {
      encoding: "utf8",
      timeout: 10000,
      cwd: directory,
    });
  } catch (error) {
    const reason = `gravitas guard unreachable (fail-closed): ${error.message}. Run gravitas doctor.`;
    console.error(`[gravitas] deny ${tool}: ${reason}`);
    return { decision: "deny", reason };
  }
  let verdict;
  try {
    verdict = JSON.parse(raw);
  } catch (error) {
    const reason = `gravitas guard output unparseable (fail-closed): ${error.message}`;
    console.error(`[gravitas] deny ${tool}: ${reason}`);
    return { decision: "deny", reason };
  }
  if (!verdict || (verdict.decision !== "allow" && verdict.decision !== "deny")) {
    const reason = `gravitas guard returned unknown verdict (fail-closed): ${raw.slice(0, 200)}`;
    console.error(`[gravitas] deny ${tool}: ${reason}`);
    return { decision: "deny", reason };
  }
  return verdict;
}

export const GravitasPlugin = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const tool = input?.tool;
      const args = output?.args ?? {};
      if (typeof tool !== "string" || !tool) {
        throw new Error("Gravitas denied call: missing tool name in hook input");
      }
      if (!hasMutatingArgs(tool, args)) {
        throw new Error(
          `Gravitas denied ${tool}: mutating tool called with missing arguments (fail-closed)`
        );
      }
      const verdict = decide(directory, tool, args);
      if (verdict && verdict.decision === "deny") {
        throw new Error(`Gravitas denied ${tool}: ${verdict.reason || "policy decision"}`);
      }
    },
  };
};
