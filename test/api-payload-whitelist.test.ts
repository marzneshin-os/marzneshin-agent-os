import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { registerApiTriggers } from "../src/triggers/api.js";

function createSdk() {
  const functions = new Map<string, Function>();
  const calls: Array<{ function_id: string; payload: unknown }> = [];
  const sdk = {
    registerFunction: (id: string, handler: Function) => {
      functions.set(id, handler);
    },
    registerTrigger: () => {},
    trigger: async (call: { function_id: string; payload: unknown }) => {
      calls.push(call);
      return { success: true };
    },
  };
  return { sdk, functions, calls };
}

describe("REST request payload boundaries", () => {
  it("forwards only fields declared by the forget endpoint", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");

    const handler = functions.get("api::forget");
    expect(handler).toBeDefined();
    await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: { sessionId: "session-1", admin: true },
    });

    expect(calls).toHaveLength(1);
    expect(calls[0]?.payload).toEqual({ sessionId: "session-1" });
  });

  it("does not pass request bodies directly into internal functions", () => {
    const api = readFileSync("src/triggers/api.ts", "utf-8");
    expect(api).not.toMatch(/payload\s*:\s*(?:req\.body|body)(?:\s*\|\|\s*\{\})?/);
  });

  it.each([
    ["api::sentinel-create", "mem::sentinel-create", { name: "test", type: "custom", config: {}, linkedActionIds: [], expiresInMs: 10, admin: true }, ["name", "type", "config", "linkedActionIds", "expiresInMs"]],
    ["api::sentinel-trigger", "mem::sentinel-trigger", { sentinelId: "snl-1", result: "ok", admin: true }, ["sentinelId", "result"]],
    ["api::sentinel-cancel", "mem::sentinel-cancel", { sentinelId: "snl-1", admin: true }, ["sentinelId"]],
    ["api::sketch-create", "mem::sketch-create", { title: "test", description: "detail", expiresInMs: 10, project: "p", admin: true }, ["title", "description", "expiresInMs", "project"]],
    ["api::sketch-add", "mem::sketch-add", { sketchId: "sk-1", title: "test", description: "detail", priority: 2, dependsOn: [], admin: true }, ["sketchId", "title", "description", "priority", "dependsOn"]],
    ["api::sketch-promote", "mem::sketch-promote", { sketchId: "sk-1", project: "p", admin: true }, ["sketchId", "project"]],
    ["api::sketch-discard", "mem::sketch-discard", { sketchId: "sk-1", admin: true }, ["sketchId"]],
    ["api::crystallize", "mem::crystallize", { actionIds: ["a-1"], sessionId: "s-1", project: "p", admin: true }, ["actionIds", "sessionId", "project"]],
    ["api::auto-crystallize", "mem::auto-crystallize", { olderThanDays: 3, project: "p", dryRun: true, admin: true }, ["olderThanDays", "project", "dryRun"]],
    ["api::diagnose", "mem::diagnose", { categories: ["actions"], admin: true }, ["categories"]],
    ["api::heal", "mem::heal", { categories: ["actions"], dryRun: true, admin: true }, ["categories", "dryRun"]],
    ["api::facet-tag", "mem::facet-tag", { targetId: "a-1", targetType: "action", dimension: "kind", value: "bug", admin: true }, ["targetId", "targetType", "dimension", "value"]],
    ["api::facet-untag", "mem::facet-untag", { targetId: "a-1", dimension: "kind", value: "bug", admin: true }, ["targetId", "dimension", "value"]],
    ["api::facet-query", "mem::facet-query", { matchAll: ["kind:bug"], matchAny: [], targetType: "action", limit: 4, admin: true }, ["matchAll", "matchAny", "targetType", "limit"]],
    ["api::lesson-search", "mem::lesson-recall", { query: "bug", project: "p", minConfidence: 0.5, limit: 4, admin: true }, ["query", "project", "minConfidence", "limit"]],
    ["api::team-share", "mem::team-share", { itemId: "obs-1", itemType: "observation", sessionId: "session-1", project: "p", admin: true }, ["itemId", "itemType", "sessionId", "project"]],
  ] as const)("whitelists %s to %s", async (apiId, functionId, body, allowedKeys) => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");

    const handler = functions.get(apiId);
    expect(handler).toBeDefined();
    await handler!({
      headers: { authorization: "Bearer test-secret" },
      body,
    });

    const call = calls.find((entry) => entry.function_id === functionId);
    expect(call).toBeDefined();
    expect(Object.keys(call!.payload as object).sort()).toEqual([...allowedKeys].sort());
    expect((call!.payload as Record<string, unknown>).admin).toBeUndefined();
  });

  it("requires configured secret and bearer authentication for Gravitas events", async () => {
    const noSecret = createSdk();
    registerApiTriggers(noSecret.sdk as never, {} as never);
    const noSecretHandler = noSecret.functions.get("api::gravitas-event");
    expect(noSecretHandler).toBeDefined();
    const unavailable = await noSecretHandler!({
      body: { operation: "completion_check", actionId: "act-1" },
    });
    expect(unavailable.status_code).toBe(503);
    expect(noSecret.calls).toHaveLength(0);

    const authed = createSdk();
    registerApiTriggers(authed.sdk as never, {} as never, "test-secret");
    const handler = authed.functions.get("api::gravitas-event");
    const unauthorized = await handler!({
      headers: {},
      body: { operation: "completion_check", actionId: "act-1" },
    });
    expect(unauthorized.status_code).toBe(401);
    expect(authed.calls).toHaveLength(0);
  });

  it("forwards only a valid discriminated Gravitas event", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");
    const handler = functions.get("api::gravitas-event");
    expect(handler).toBeDefined();

    const invalid = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: {
        operation: "bind",
        actionId: "act-1",
        conversationId: "conv-1",
        workspaceRoots: ["/workspace/project"],
        enforcement: "enforce",
        admin: true,
      },
    });
    expect(invalid.status_code).toBe(400);
    expect(calls).toHaveLength(0);

    const accepted = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: {
        operation: "bind",
        actionId: "act-1",
        conversationId: "conv-1",
        workspaceRoots: ["/workspace/project"],
        enforcement: "enforce",
      },
    });
    expect(accepted.status_code).toBe(200);
    expect(calls).toEqual([
      {
        function_id: "mem::gravitas-guard",
        payload: {
          operation: "bind",
          actionId: "act-1",
          conversationId: "conv-1",
          workspaceRoots: ["/workspace/project"],
          enforcement: "enforce",
        },
      },
    ]);
  });

  it("forwards an Antigravity Stop event with its idle state and execution number", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");
    const handler = functions.get("api::gravitas-event")!;
    const payload = {
      operation: "stop",
      actionId: "act-1",
      conversationId: "conv-1",
      workspaceRoot: "/workspace/project",
      fullyIdle: true,
      executionNum: 3,
    };
    const invalid = await handler({
      headers: { authorization: "Bearer test-secret" },
      body: { ...payload, executionNum: Number.MAX_SAFE_INTEGER + 1 },
    });
    expect(invalid.status_code).toBe(400);
    expect(calls).toHaveLength(0);

    const response = await handler({
      headers: { authorization: "Bearer test-secret" },
      body: payload,
    });
    expect(response.status_code).toBe(200);
    expect(calls).toEqual([{ function_id: "mem::gravitas-guard", payload }]);
  });

  it("preserves async execution metadata accepted by the core guard parser", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");
    const handler = functions.get("api::gravitas-event")!;
    const payload = {
      operation: "pre_tool",
      actionId: "act-1",
      conversationId: "conv-1",
      workspaceRoot: "/workspace/project",
      toolName: "write_file",
      relativePath: "src/index.ts",
      argumentHash: "a".repeat(64),
      runPersistent: true,
      waitMsBeforeAsync: 5000,
      stepIndex: 2,
    };
    const response = await handler({
      headers: { authorization: "Bearer test-secret" },
      body: payload,
    });
    expect(response.status_code).toBe(200);
    expect(calls).toEqual([{ function_id: "mem::gravitas-guard", payload }]);
  });

  it("accepts a validated guard contract on action creation and rejects malformed contracts", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");
    const handler = functions.get("api::action-create");
    expect(handler).toBeDefined();
    const guardContract = {
      enforcement: "enforce",
      allowedPaths: ["src"],
      acceptanceCriteria: [
        { id: "tests", description: "Tests pass", validatorId: "unit" },
      ],
      validators: [{ id: "unit", command: "npm test" }],
    };

    const accepted = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: { title: "Guarded work", guardContract, admin: true },
    });
    expect(accepted.status_code).toBe(201);
    expect(calls[0]?.payload).toEqual({ title: "Guarded work", guardContract });

    const invalid = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: { title: "Bad guarded work", guardContract: { enforcement: "always" } },
    });
    expect(invalid.status_code).toBe(400);
    expect(calls).toHaveLength(1);
  });

  it("routes an isolated action-update rearm to the guard without mutating the action", async () => {
    const { sdk, functions, calls } = createSdk();
    registerApiTriggers(sdk as never, {} as never, "test-secret");
    const handler = functions.get("api::action-update");
    expect(handler).toBeDefined();
    const rearmFailure = {
      conversationId: "conv-1",
      workspaceRoot: "/workspace/project",
      callHash: "a".repeat(64),
      diagnosis: "The source import was wrong",
      strategyFingerprint: "b".repeat(64),
      nextArgumentHash: "c".repeat(64),
    };

    const mixed = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: { actionId: "act-1", status: "done", rearmFailure },
    });
    expect(mixed.status_code).toBe(400);
    expect(calls).toHaveLength(0);

    const accepted = await handler!({
      headers: { authorization: "Bearer test-secret" },
      body: { actionId: "act-1", rearmFailure },
    });
    expect(accepted.status_code).toBe(200);
    expect(calls).toEqual([
      {
        function_id: "mem::gravitas-guard",
        payload: {
          operation: "rearm_failure",
          actionId: "act-1",
          ...rearmFailure,
        },
      },
    ]);
  });
});
