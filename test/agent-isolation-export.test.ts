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

import { registerExportImportFunction } from "../src/functions/export-import.js";
import { KV } from "../src/state/schema.js";
import { getSearchIndex } from "../src/functions/search.js";
import type { Session, CompressedObservation, Memory, SessionSummary } from "../src/types.js";

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
    trigger: async (id: string, data?: unknown) => {
      const fn = functions.get(id);
      if (!fn) throw new Error(`No function: ${id}`);
      return fn(data);
    },
  };
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

function observation(id: string, sessionId: string, agentId: string): CompressedObservation {
  return {
    id,
    sessionId,
    timestamp: "2026-01-01T00:00:00Z",
    type: "user_prompt",
    title: id,
    facts: [id],
    narrative: id,
    concepts: [],
    files: [],
    importance: 1,
    agentId,
  };
}

function memory(id: string, agentId: string): Memory {
  return {
    id,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
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

function summary(sessionId: string): SessionSummary {
  return {
    sessionId,
    project: "myapp",
    createdAt: "2026-01-01T00:00:00Z",
    title: sessionId,
    narrative: sessionId,
    keyDecisions: [],
    filesModified: [],
    concepts: [],
    observationCount: 1,
  };
}

describe("mem::export agent-scope isolation", () => {
  let sdk: ReturnType<typeof mockSdk>;
  let kv: ReturnType<typeof mockKV>;

  beforeEach(async () => {
    sdk = mockSdk();
    kv = mockKV();
    getSearchIndex().clear();
    registerExportImportFunction(sdk as never, kv as never);
    configState.agentId = "agent_a";
    configState.isolated = true;

    await kv.set(KV.sessions, "session-a", session("session-a", "agent_a"));
    await kv.set(KV.sessions, "session-b", session("session-b", "agent_b"));
    await kv.set(KV.observations("session-a"), "obs-a", observation("obs-a", "session-a", "agent_a"));
    await kv.set(KV.observations("session-b"), "obs-b", observation("obs-b", "session-b", "agent_b"));
    await kv.set(KV.memories, "mem-a", memory("mem-a", "agent_a"));
    await kv.set(KV.memories, "mem-b", memory("mem-b", "agent_b"));
    await kv.set(KV.summaries, "session-a", summary("session-a"));
    await kv.set(KV.summaries, "session-b", summary("session-b"));
    await kv.set(KV.accessLog, "mem-a", { memoryId: "mem-a", count: 1, lastAt: "", recent: [] });
    await kv.set(KV.accessLog, "mem-b", { memoryId: "mem-b", count: 1, lastAt: "", recent: [] });
    await kv.set(KV.graphNodes, "node-a", {
      id: "node-a", type: "concept", name: "unscoped graph data", properties: {},
      sourceObservationIds: ["obs-a"], createdAt: "2026-01-01T00:00:00Z",
    });
  });

  it("exports only records with provable ownership by the isolated agent", async () => {
    const result = await sdk.trigger("mem::export", {}) as {
      sessions: Session[];
      observations: Record<string, CompressedObservation[]>;
      memories: Memory[];
      summaries: SessionSummary[];
      accessLogs?: Array<{ memoryId: string }>;
      graphNodes?: unknown[];
      profiles?: unknown[];
    };

    expect(result.sessions.map((s) => s.id)).toEqual(["session-a"]);
    expect(Object.keys(result.observations)).toEqual(["session-a"]);
    expect(result.observations["session-a"].map((o) => o.id)).toEqual(["obs-a"]);
    expect(result.memories.map((m) => m.id)).toEqual(["mem-a"]);
    expect(result.summaries.map((s) => s.sessionId)).toEqual(["session-a"]);
    expect(result.accessLogs?.map((entry) => entry.memoryId)).toEqual(["mem-a"]);
    expect(result.graphNodes).toBeUndefined();
    expect(result.profiles).toBeUndefined();
  });

  it("fails closed when isolated export has no agent ID", async () => {
    configState.agentId = undefined;

    await expect(sdk.trigger("mem::export", {})).rejects.toThrow(/AGENTMEMORY_AGENT_SCOPE=isolated/);
  });

  it("rejects a specific export scope that differs from the isolated agent", async () => {
    await expect(
      sdk.trigger("mem::export", { agentId: "agent_b" }),
    ).rejects.toThrow(/must match the configured AGENT_ID/);
  });

  it("allows the explicit wildcard export scope in isolated mode", async () => {
    const result = await sdk.trigger("mem::export", { agentId: "*" }) as {
      sessions: Session[];
      memories: Memory[];
    };

    expect(result.sessions.map((s) => s.id)).toEqual(["session-a", "session-b"]);
    expect(result.memories.map((m) => m.id)).toEqual(["mem-a", "mem-b"]);
  });

  it("allows an explicit wildcard export when the isolated agent ID is missing", async () => {
    configState.agentId = undefined;

    const result = await sdk.trigger("mem::export", { agentId: "*" }) as {
      sessions: Session[];
    };

    expect(result.sessions).toHaveLength(2);
  });

  it("preserves the full export in non-isolated mode", async () => {
    configState.isolated = false;
    configState.agentId = undefined;

    const result = await sdk.trigger("mem::export", {}) as {
      sessions: Session[];
      memories: Memory[];
      graphNodes?: unknown[];
    };

    expect(result.sessions).toHaveLength(2);
    expect(result.memories).toHaveLength(2);
    expect(result.graphNodes).toHaveLength(1);
  });
});
