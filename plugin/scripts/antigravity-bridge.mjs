#!/usr/bin/env node
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, realpathSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
//#region src/hooks/antigravity-bridge.ts
const SCRIPTS_DIR = dirname(fileURLToPath(import.meta.url));
const TOOL_NAME_MAP = {
	view_file: "read",
	view_line_range: "read",
	view_code_item: "read",
	read_file: "read",
	read_url_content: "read",
	edit_file: "edit",
	replace_file_content: "edit",
	multi_replace_file_content: "edit",
	propose_code: "edit",
	write_to_file: "write",
	create_file: "write",
	grep_search: "grep",
	codebase_search: "grep",
	find_by_name: "glob",
	list_dir: "glob"
};
const ARG_KEY_MAP = {
	AbsolutePath: "file_path",
	TargetFile: "file_path",
	DirectoryPath: "path",
	SearchDirectory: "path",
	Pattern: "pattern",
	Query: "pattern",
	CommandLine: "command",
	StartLine: "start_line",
	EndLine: "end_line"
};
const GUARD_CONFIG = ".agents/gravitas.local.json";
const GUARD_TIMEOUT_MS = 2500;
function normalizeGuardConfig(value) {
	if (value === void 0) return {
		valid: true,
		config: { mode: "off" }
	};
	if (!value || typeof value !== "object" || Array.isArray(value)) return {
		valid: false,
		error: "local guard config must be a JSON object"
	};
	const data = value;
	if (Object.keys(data).some((key) => key !== "mode" && key !== "actionId")) return {
		valid: false,
		error: "local guard config has unknown fields"
	};
	if (data.mode !== "off" && data.mode !== "audit" && data.mode !== "enforce") return {
		valid: false,
		error: "local guard config mode must be off, audit, or enforce"
	};
	if (data.mode === "off") return {
		valid: true,
		config: { mode: "off" }
	};
	if (typeof data.actionId !== "string" || data.actionId.trim().length === 0 || data.actionId.length > 200) return {
		valid: false,
		error: "active local guard config requires an actionId"
	};
	return {
		valid: true,
		config: {
			mode: data.mode,
			actionId: data.actionId
		}
	};
}
function stableJson(value) {
	if (value === null || typeof value !== "object") {
		const encoded = JSON.stringify(value);
		if (encoded === void 0) throw new TypeError("value is not JSON serializable");
		return encoded;
	}
	if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
	const object = value;
	return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${stableJson(object[key])}`).join(",")}}`;
}
function hashValue(value) {
	return createHash("sha256").update(stableJson(value), "utf8").digest("hex");
}
function hashText(value) {
	return createHash("sha256").update(value, "utf8").digest("hex");
}
function resolveWorkspaceTarget(workspaceRoot, inputPath) {
	if (!isAbsolute(workspaceRoot) || inputPath.trim().length === 0) return { error: "workspace root and target path must be absolute/non-empty" };
	try {
		const root = realpathSync.native(workspaceRoot);
		const rawRoot = resolve(workspaceRoot);
		const candidate = isAbsolute(inputPath) ? resolve(inputPath) : resolve(rawRoot, inputPath);
		if (!isWithin(root, candidate) && !isWithin(rawRoot, candidate)) return { error: "target escapes the workspace root" };
		let existingAncestor = candidate;
		while (!existsSync(existingAncestor)) {
			const parent = dirname(existingAncestor);
			if (parent === existingAncestor) return { error: "target has no existing workspace parent" };
			existingAncestor = parent;
		}
		const realAncestor = realpathSync.native(existingAncestor);
		if (!isWithin(root, realAncestor)) return { error: "target resolves outside the workspace root" };
		const target = existsSync(candidate) ? realpathSync.native(candidate) : resolve(realAncestor, relative(existingAncestor, candidate));
		if (!isWithin(root, target)) return { error: "target resolves outside the workspace root" };
		const relativePath = relative(root, target).split(sep).join("/");
		if (!relativePath || relativePath === "." || relativePath.startsWith("../")) return { error: "target must be a workspace file path" };
		const exists = existsSync(target);
		if (exists && !statSync(target).isFile()) return { error: "target is not a regular file" };
		return {
			relativePath,
			fileHash: exists ? createHash("sha256").update(readFileSync(target)).digest("hex") : null,
			exists
		};
	} catch {
		return { error: "workspace target could not be safely canonicalized" };
	}
}
function isWithinWorkspace(root, target) {
	const path = relative(root, target);
	return path === "" || path !== ".." && !path.startsWith(`..${sep}`) && !isAbsolute(path);
}
const isWithin = isWithinWorkspace;
function workspacePaths(raw) {
	return Array.isArray(raw["workspacePaths"]) ? raw["workspacePaths"].filter((value) => typeof value === "string" && value.length > 0) : [];
}
function hasLocalGuardConfig(root) {
	return existsSync(join(root, GUARD_CONFIG.replaceAll("/", sep)));
}
function loadGuardContext(raw) {
	const declaredRoots = workspacePaths(raw);
	const roots = declaredRoots.length === 0 && hasLocalGuardConfig(process.cwd()) ? [process.cwd()] : declaredRoots;
	if (roots.length !== 1) return roots.some(hasLocalGuardConfig) || roots.length === 0 && hasLocalGuardConfig(process.cwd()) ? {
		mode: "enforce",
		error: "guarded workspace requires exactly one Antigravity workspace root"
	} : { mode: "off" };
	let root;
	try {
		root = realpathSync.native(roots[0]);
	} catch {
		return hasLocalGuardConfig(roots[0]) ? {
			mode: "enforce",
			error: "guarded workspace root cannot be canonicalized"
		} : { mode: "off" };
	}
	const configPath = join(root, GUARD_CONFIG.replaceAll("/", sep));
	if (!existsSync(configPath)) return {
		mode: "off",
		workspaceRoot: root
	};
	const safeConfig = resolveWorkspaceTarget(root, configPath);
	if ("error" in safeConfig) return {
		mode: "enforce",
		workspaceRoot: root,
		error: safeConfig.error
	};
	try {
		const parsed = normalizeGuardConfig(JSON.parse(readFileSync(configPath, "utf8")));
		if (!parsed.valid) return {
			mode: "enforce",
			workspaceRoot: root,
			error: parsed.error
		};
		return {
			...parsed.config,
			workspaceRoot: root
		};
	} catch {
		return {
			mode: "enforce",
			workspaceRoot: root,
			error: "local guard config is not valid JSON"
		};
	}
}
function authHeaders(secret) {
	return {
		"Content-Type": "application/json",
		Authorization: `Bearer ${secret}`
	};
}
async function postGuardEvent(body, env = process.env) {
	const secret = env["AGENTMEMORY_SECRET"];
	if (!secret) throw new Error("AGENTMEMORY_SECRET is required for an active local guard");
	const baseUrl = (env["AGENTMEMORY_URL"] || "http://localhost:3111").replace(/\/+$/, "");
	const response = await fetch(`${baseUrl}/agentmemory/gravitas/event`, {
		method: "POST",
		headers: authHeaders(secret),
		body: JSON.stringify(body),
		signal: AbortSignal.timeout(GUARD_TIMEOUT_MS)
	});
	if (!response.ok) throw new Error(`guard service returned HTTP ${response.status}`);
	const result = await response.json();
	if (!result || typeof result !== "object") throw new Error("guard service returned an invalid response");
	return result;
}
function toolArgs(raw) {
	const toolCall = asObject(raw["toolCall"]);
	return normalizeToolArgs(asObject(toolCall?.["args"]) ?? asObject(toolCall?.["toolArgs"]));
}
function nativeToolName(raw) {
	const call = asObject(raw["toolCall"]);
	return firstString(call?.["name"], call?.["toolName"]);
}
function targetPath(toolName, args) {
	if (![
		"view_file",
		"view_line_range",
		"view_code_item",
		"read_file",
		"edit_file",
		"replace_file_content",
		"multi_replace_file_content",
		"write_to_file",
		"create_file"
	].includes(toolName)) return void 0;
	return firstString(args["file_path"], args["TargetFile"], args["AbsolutePath"]);
}
function isWriteTool(toolName) {
	return [
		"edit_file",
		"replace_file_content",
		"multi_replace_file_content",
		"write_to_file",
		"create_file"
	].includes(toolName);
}
function isFullFileRead(toolName, args) {
	return ["view_file", "read_file"].includes(toolName) && args["StartLine"] === void 0 && args["EndLine"] === void 0 && args["start_line"] === void 0 && args["end_line"] === void 0;
}
function strategyFingerprint(toolName, args) {
	return hashText(firstString(args["Instruction"], args["Description"], args["CommandLine"], args["command"], args["TargetContent"]) ?? toolName);
}
function actionBinding(context, raw) {
	if (!context.actionId || !context.workspaceRoot) throw new Error("guard action or workspace binding is missing");
	const conversationId = firstString(raw["conversationId"]);
	if (!conversationId) throw new Error("Antigravity conversationId is missing");
	return {
		actionId: context.actionId,
		conversationId,
		workspaceRoot: context.workspaceRoot
	};
}
async function guardEvent(event, raw, context) {
	if (context.mode === "off") return void 0;
	if (context.error) return {
		decision: "deny",
		allowed: false,
		reason: context.error
	};
	const binding = actionBinding(context, raw);
	if (event === "SessionStart") return postGuardEvent({
		operation: "bind",
		actionId: binding.actionId,
		conversationId: binding.conversationId,
		workspaceRoots: [binding.workspaceRoot],
		enforcement: context.mode
	});
	if (event === "PreToolUse" || event === "PostToolUse") {
		const toolName = nativeToolName(raw);
		const args = toolArgs(raw);
		const stepIndex = raw["stepIdx"];
		if (!toolName || typeof stepIndex !== "number" || !Number.isInteger(stepIndex) || stepIndex < 0) return {
			decision: "deny",
			allowed: false,
			reason: "Antigravity tool event is missing a valid tool name or stepIdx"
		};
		const argHash = hashValue(args);
		const command = firstString(args["CommandLine"], args["command"]);
		const commandHash = toolName === "run_command" && command ? hashText(command) : void 0;
		const rawTarget = targetPath(toolName, args);
		let target;
		if (rawTarget) target = resolveWorkspaceTarget(binding.workspaceRoot, rawTarget);
		if (event === "PreToolUse") {
			const write = isWriteTool(toolName);
			if (target && "error" in target && write) return context.mode === "enforce" ? {
				decision: "deny",
				allowed: false,
				reason: target.error
			} : {
				decision: "allow",
				allowed: true,
				reason: target.error
			};
			const payload = {
				operation: "pre_tool",
				...binding,
				toolName,
				argumentHash: argHash,
				strategyFingerprint: strategyFingerprint(toolName, args),
				isWrite: write,
				stepIndex
			};
			if (target && !("error" in target)) {
				payload["relativePath"] = target.relativePath;
				if (write || isFullFileRead(toolName, args) && target.exists) payload["currentFileHash"] = target.fileHash;
			}
			if (commandHash) payload["commandHash"] = commandHash;
			if (toolName === "run_command") {
				if (typeof args["RunPersistent"] === "boolean") payload["runPersistent"] = args["RunPersistent"];
				if (Object.hasOwn(args, "WaitMsBeforeAsync")) payload["waitMsBeforeAsync"] = args["WaitMsBeforeAsync"];
			}
			return postGuardEvent(payload);
		}
		const successful = raw["error"] === void 0 || raw["error"] === "";
		const payload = {
			operation: "post_tool",
			...binding,
			toolName,
			argumentHash: argHash,
			success: successful,
			strategyFingerprint: strategyFingerprint(toolName, args),
			stepIndex
		};
		if (target && !("error" in target)) {
			payload["relativePath"] = target.relativePath;
			if (isFullFileRead(toolName, args) && target.fileHash) {
				payload["isFullFileRead"] = true;
				payload["fileHash"] = target.fileHash;
			}
		}
		if (commandHash) payload["commandHash"] = commandHash;
		if (isWriteTool(toolName)) payload["mutated"] = successful;
		if (toolName === "run_command") {
			if (typeof args["RunPersistent"] === "boolean") payload["runPersistent"] = args["RunPersistent"];
			if (Object.hasOwn(args, "WaitMsBeforeAsync")) payload["waitMsBeforeAsync"] = args["WaitMsBeforeAsync"];
		}
		return postGuardEvent(payload);
	}
	if (event === "Stop") {
		const executionNum = raw["executionNum"];
		if (typeof executionNum !== "number" || !Number.isInteger(executionNum) || executionNum < 0) throw new Error("Antigravity Stop is missing a valid executionNum");
		const stopResult = await postGuardEvent({
			operation: "stop",
			...binding,
			fullyIdle: raw["fullyIdle"] === true,
			executionNum
		});
		if (stopResult.decision === "deny") return {
			allowed: false,
			reason: stopResult.reason ?? "guard rejected the Stop event"
		};
		return postGuardEvent({
			operation: "completion_check",
			actionId: binding.actionId
		});
	}
}
function asObject(value) {
	return typeof value === "object" && value !== null && !Array.isArray(value) ? value : void 0;
}
function firstString(...values) {
	for (const v of values) if (typeof v === "string" && v.length > 0) return v;
}
function normalizeToolArgs(args) {
	if (!args) return {};
	const out = { ...args };
	for (const [from, to] of Object.entries(ARG_KEY_MAP)) if (out[to] === void 0 && args[from] !== void 0) out[to] = args[from];
	return out;
}
function normalizePayload(event, raw) {
	const toolCall = asObject(raw["toolCall"]);
	const workspacePaths = Array.isArray(raw["workspacePaths"]) ? raw["workspacePaths"] : [];
	const sessionId = firstString(raw["conversationId"], raw["session_id"], raw["sessionId"]) ?? "unknown";
	const cwd = firstString(raw["cwd"], workspacePaths[0]) ?? process.cwd();
	const out = {
		...raw,
		session_id: sessionId,
		cwd,
		hook_event_name: event
	};
	const transcriptPath = firstString(raw["transcript_path"], raw["transcriptPath"]);
	if (transcriptPath) out["transcript_path"] = transcriptPath;
	if (toolCall) {
		const args = normalizeToolArgs(asObject(toolCall["args"]) ?? asObject(toolCall["toolArgs"]));
		const rawName = firstString(toolCall["name"], toolCall["toolName"], args["ToolName"], args["toolName"]);
		if (rawName) {
			out["tool_name"] = TOOL_NAME_MAP[rawName] ?? rawName;
			out["native_tool_name"] = rawName;
		}
		out["tool_input"] = args;
		const result = toolCall["result"] ?? raw["toolResult"] ?? raw["result"];
		if (result !== void 0) out["tool_result"] = result;
	}
	return out;
}
function targetsFor(event, raw, guardOnly = false) {
	if (guardOnly) return [];
	switch (event) {
		case "SessionStart": return ["session-start.mjs"];
		case "PreInvocation": return [];
		case "PreToolUse": return ["pre-tool-use.mjs"];
		case "PostToolUse": return ["post-tool-use.mjs"];
		case "Stop": return ["stop.mjs", "session-end.mjs"];
		default: return [];
	}
}
function responseFor(event, guardResult, mode = "off", fullyIdle) {
	if (event === "SessionStart" && guardResult?.decision === "deny") return JSON.stringify({ injectSteps: [{ systemMessage: { systemMessage: `The workspace reliability guard could not bind this session: ${guardResult.reason ?? "guard service unavailable"}. Guarded writes will be denied until the local action binding is corrected.` } }] });
	if (event === "PreToolUse") {
		const decision = mode === "off" ? "allow" : guardResult?.decision ?? (mode === "enforce" ? "deny" : "allow");
		const reason = guardResult?.reason ? `${guardResult.reason}${guardResult.callHash ? ` [call:${guardResult.callHash}]` : ""}` : mode === "enforce" && !guardResult ? "guard service unavailable" : void 0;
		return JSON.stringify({
			decision,
			...reason ? { reason } : {}
		});
	}
	if (event === "Stop") {
		if (mode !== "enforce") return JSON.stringify({ decision: "allow" });
		if (fullyIdle !== true) return JSON.stringify({
			decision: "continue",
			reason: "Antigravity still reports active work; wait for it to become idle."
		});
		if (!guardResult?.allowed) return JSON.stringify({
			decision: "continue",
			reason: guardResult?.reason ?? "Guarded action is missing fresh completion evidence."
		});
		return JSON.stringify({ decision: "allow" });
	}
	return "{}";
}
async function main() {
	const event = process.argv[2];
	if (!event) return;
	const guardOnly = process.argv[3] === "--guard-only";
	let input = "";
	for await (const chunk of process.stdin) input += chunk;
	let raw;
	try {
		raw = JSON.parse(input);
	} catch {
		process.stdout.write(responseFor(event, void 0, "enforce"));
		return;
	}
	if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
		process.stdout.write(responseFor(event, void 0, "enforce"));
		return;
	}
	const context = loadGuardContext(raw);
	const effectiveMode = context.error ? "enforce" : context.mode;
	let guardResult;
	try {
		guardResult = await guardEvent(event, raw, context);
	} catch (error) {
		const reason = error instanceof Error ? error.message : "guard service unavailable";
		guardResult = effectiveMode === "enforce" ? {
			decision: "deny",
			allowed: false,
			reason
		} : {
			decision: "allow",
			allowed: true,
			reason
		};
	}
	const hookResponse = responseFor(event, guardResult, effectiveMode, raw["fullyIdle"] === true);
	const decision = JSON.parse(hookResponse).decision;
	if (event === "PreToolUse" && decision === "deny" || event === "Stop" && decision === "continue") {
		process.stdout.write(hookResponse);
		return;
	}
	const payload = JSON.stringify(normalizePayload(event, raw));
	for (const script of targetsFor(event, raw, guardOnly)) spawnSync(process.execPath, [join(SCRIPTS_DIR, script)], {
		input: payload,
		stdio: [
			"pipe",
			"ignore",
			"ignore"
		]
	});
	process.stdout.write(hookResponse);
}
if (process.argv[1] !== void 0 && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main().catch((error) => {
	const event = process.argv[2] ?? "";
	const reason = error instanceof Error ? error.message : "guard service unavailable";
	const mode = event === "PreToolUse" || event === "Stop" ? "enforce" : "off";
	process.stdout.write(responseFor(event, {
		decision: "deny",
		allowed: false,
		reason
	}, mode));
}).finally(() => {
	process.exit(0);
});
//#endregion
export { hashValue, isWithinWorkspace, normalizeGuardConfig, normalizePayload, resolveWorkspaceTarget, responseFor, stableJson, targetsFor };

//# sourceMappingURL=antigravity-bridge.mjs.map