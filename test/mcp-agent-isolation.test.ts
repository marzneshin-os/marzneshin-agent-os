import { describe, it, expect, beforeEach, vi } from "vitest";

const configState = vi.hoisted(() => ({
  agentId: undefined as string | undefined,
  isolated: false,
}));

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock("../src/config.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/config.js")>();
  return {
    ...actual,
    getAgentId: () => configState.agentId,
    isAgentScopeIsolated: () => configState.isolated,
  };
});

import { registerMcpEndpoints } from "../src/mcp/server.js";
import { registerExportImportFunction } from "../src/functions/export-import.js";
import { KV } from "../src/state/schema.js";
import type { Session, SessionSummary, Memory } from "../src/types.js";

function mockKV() {
  const store = new Map<string, Map<string, unknown>>();
  return {
    get: async <T>(scope: string, key: string): Promise<T | null> =>
      (store.get(scope)?.get(key) as T) ?? null,
    set: async <T>(scope: string, key: string, data: T): Promise<T> => {
      if (!store.has(scope)) store.set(scope, new Map());
      store.get(scope)!.set(key, data);
      return data;
    },
    delete: async (scope: string, key: string): Promise<void> => {
      store.get(scope)?.delete(key);
    },
    list: async <T>(scope: string): Promise<T[]> => {
      const entries = store.get(scope);
      return entries ? (Array.from(entries.values()) as T[]) : [];
    },
  };
}

function mockSdk() {
  const functions = new Map<string, Function>();
  return {
    registerFunction: (idOrOpts: string | { id: string }, handler: Function) => {
      const id = typeof idOrOpts === "string" ? idOrOpts : idOrOpts.id;
      functions.set(id, handler);
    },
    registerTrigger: () => {},
    trigger: async (
      idOrInput: string | { function_id: string; payload: unknown },
      data?: unknown,
    ) => {
      const id = typeof idOrInput === "string" ? idOrInput : idOrInput.function_id;
      const payload = typeof idOrInput === "string" ? data : idOrInput.payload;
      const fn = functions.get(id);
      if (!fn) throw new Error(`No function: ${id}`);
      return fn(payload);
    },
    getFunction: (id: string) => functions.get(id),
  };
}

function makeReq(body?: unknown) {
  return { body, headers: {}, query_params: {} };
}

function session(id: string, agentId: string): Session {
  return {
    id,
    project: "myapp",
    cwd: "/work/myapp",
    startedAt: "2026-01-01T00:00:00Z",
    status: "completed",
    observationCount: 1,
    agentId,
  };
}

function summary(sessionId: string): SessionSummary {
  return {
    sessionId,
    project: "myapp",
    createdAt: "2026-02-01T00:00:00Z",
    title: sessionId,
    narrative: sessionId,
    keyDecisions: [],
    filesModified: [],
    concepts: [],
    observationCount: 1,
  };
}

function memory(id: string, agentId: string): Memory {
  return {
    id,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-02-01T00:00:00Z",
    type: "fact",
    title: id,
    content: id,
    concepts: [],
    files: [],
    sessionIds: [],
    strength: 1,
    version: 1,
    isLatest: true,
    agentId,
  };
}

describe("MCP agent-scope isolation", () => {
  let sdk: ReturnType<typeof mockSdk>;
  let kv: ReturnType<typeof mockKV>;

  beforeEach(() => {
    sdk = mockSdk();
    kv = mockKV();
    configState.agentId = "agent_b";
    configState.isolated = true;
    registerMcpEndpoints(sdk as never, kv as never);
    registerExportImportFunction(sdk as never, kv as never);
  });

  it("filters memory_sessions to the active agent", async () => {
    await kv.set(KV.sessions, "session-a", session("session-a", "agent_a"));
    await kv.set(KV.sessions, "session-b", session("session-b", "agent_b"));

    const result = (await sdk.getFunction("mcp::tools::call")!(
      makeReq({ name: "memory_sessions", arguments: {} }),
    )) as { status_code: number; body: { content: Array<{ text: string }> } };

    const data = JSON.parse(result.body.content[0].text);
    expect(result.status_code).toBe(200);
    expect(data.sessions.map((s: Session) => s.id)).toEqual(["session-b"]);
  });

  it("filters project recent summaries through their owning sessions", async () => {
    await kv.set(KV.sessions, "session-a", session("session-a", "agent_a"));
    await kv.set(KV.sessions, "session-b", session("session-b", "agent_b"));
    await kv.set(KV.summaries, "session-a", summary("session-a"));
    await kv.set(KV.summaries, "session-b", summary("session-b"));

    const result = (await sdk.getFunction("mcp::resources::read")!(
      makeReq({ uri: "agentmemory://project/myapp/recent" }),
    )) as { status_code: number; body: { contents: Array<{ text: string }> } };

    const data = JSON.parse(result.body.contents[0].text);
    expect(result.status_code).toBe(200);
    expect(data.map((s: SessionSummary) => s.sessionId)).toEqual(["session-b"]);
  });

  it("filters memories/latest to the active agent", async () => {
    await kv.set(KV.memories, "mem-a", memory("mem-a", "agent_a"));
    await kv.set(KV.memories, "mem-b", memory("mem-b", "agent_b"));

    const result = (await sdk.getFunction("mcp::resources::read")!(
      makeReq({ uri: "agentmemory://memories/latest" }),
    )) as { status_code: number; body: { contents: Array<{ text: string }> } };

    const data = JSON.parse(result.body.contents[0].text);
    expect(result.status_code).toBe(200);
    expect(data.map((m: Memory) => m.id)).toEqual(["mem-b"]);
  });

  it("refuses session handoff for a session owned by another agent", async () => {
    await kv.set(KV.sessions, "session-a", session("session-a", "agent_a"));
    await kv.set(KV.summaries, "session-a", summary("session-a"));

    const result = (await sdk.getFunction("mcp::prompts::get")!(
      makeReq({ name: "session_handoff", arguments: { session_id: "session-a" } }),
    )) as { status_code: number; body: unknown };

    expect(result.status_code).toBe(404);
    expect(JSON.stringify(result.body)).not.toContain("session-a");
  });

  it("passes explicit session and project for memory_team_share", async () => {
    let sharedPayload: unknown;
    sdk.registerFunction("mem::team-share", async (payload: unknown) => {
      sharedPayload = payload;
      return { success: true };
    });

    const result = (await sdk.getFunction("mcp::tools::call")!(
      makeReq({
        name: "memory_team_share",
        arguments: {
          itemId: "obs-b",
          itemType: "observation",
          sessionId: "session-b",
          project: "myapp",
        },
      }),
    )) as { status_code: number };

    expect(result.status_code).toBe(200);
    expect(sharedPayload).toEqual({
      itemId: "obs-b",
      itemType: "observation",
      sessionId: "session-b",
      project: "myapp",
    });
  });

  it("fails closed on MCP reads when isolated mode has no agent ID", async () => {
    configState.agentId = undefined;
    await kv.set(KV.sessions, "session-a", session("session-a", "agent_a"));

    const result = (await sdk.getFunction("mcp::tools::call")!(
      makeReq({ name: "memory_sessions", arguments: {} }),
    )) as { status_code: number };

    expect(result.status_code).toBe(500);
  });

  it("rejects an MCP export scope that differs from the active agent", async () => {
    const result = (await sdk.getFunction("mcp::tools::call")!(
      makeReq({ name: "memory_export", arguments: { agentId: "agent_a" } }),
    )) as { status_code: number };

    expect(result.status_code).toBe(500);
  });

  it("preserves the explicit wildcard export escape hatch", async () => {
    await kv.set(KV.memories, "mem-a", memory("mem-a", "agent_a"));
    await kv.set(KV.memories, "mem-b", memory("mem-b", "agent_b"));

    const result = (await sdk.getFunction("mcp::tools::call")!(
      makeReq({ name: "memory_export", arguments: { agentId: "*" } }),
    )) as { status_code: number; body: { content: Array<{ text: string }> } };

    const data = JSON.parse(result.body.content[0].text);
    expect(result.status_code).toBe(200);
    expect(data.memories.map((m: Memory) => m.id)).toEqual(["mem-a", "mem-b"]);
  });
});
