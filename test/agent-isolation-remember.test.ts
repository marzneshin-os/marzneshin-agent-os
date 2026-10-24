import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

const configState = vi.hoisted(() => ({
  agentId: undefined as string | undefined,
  isolated: false,
}));

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

vi.mock("../src/state/keyed-mutex.js", () => ({
  withKeyedLock: <T>(_key: string, fn: () => Promise<T>) => fn(),
}));

vi.mock("../src/config.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/config.js")>();
  return {
    ...actual,
    getAgentId: () => configState.agentId,
    isAgentScopeIsolated: () => configState.isolated,
  };
});

vi.mock("iii-sdk", async (importOriginal) => {
  const actual = await importOriginal<typeof import("iii-sdk")>();
  return {
    ...actual,
    TriggerAction: {
      ...actual.TriggerAction,
      Void: vi.fn(() => ({ type: "void" })),
    },
  };
});

import { registerRememberFunction } from "../src/functions/remember.js";
import { getSearchIndex, setIndexPersistence } from "../src/functions/search.js";

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
    registerFunction: (id: string, handler: Function) => functions.set(id, handler),
    registerTrigger: () => {},
    trigger: async (input: { function_id: string; payload: unknown }) => {
      const fn = functions.get(input.function_id);
      return fn ? fn(input.payload) : {};
    },
  };
}

describe("mem::remember agent ownership", () => {
  beforeEach(() => {
    configState.agentId = undefined;
    configState.isolated = false;
    getSearchIndex().clear();
    setIndexPersistence(null);
  });

  afterEach(() => {
    setIndexPersistence(null);
  });

  it("does not supersede another agent's memory in the same project", async () => {
    const sdk = mockSdk();
    const kv = mockKV();
    registerRememberFunction(sdk as never, kv as never);

    configState.agentId = "agent_a";
    const first = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "always use express-jwt middleware for token validation in this project",
        type: "pattern",
        project: "api",
      },
    }) as { memory: { id: string } };

    configState.agentId = "agent_b";
    const second = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "always use express-jwt middleware for token validation in this project",
        type: "pattern",
        project: "api",
      },
    }) as { memory: { supersedes: string[] } };

    expect(second.memory.supersedes).toEqual([]);
    const original = await kv.get<{ isLatest: boolean }>("mem:memories", first.memory.id);
    expect(original?.isLatest).toBe(true);
  });

  it("still supersedes a prior version owned by the same agent", async () => {
    const sdk = mockSdk();
    const kv = mockKV();
    registerRememberFunction(sdk as never, kv as never);
    configState.agentId = "agent_a";

    const first = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "always use express-jwt middleware for token validation in this project",
        type: "pattern",
        project: "api",
      },
    }) as { memory: { id: string } };
    const second = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "always use express-jwt middleware for token validation in this project",
        type: "pattern",
        project: "api",
      },
    }) as { memory: { supersedes: string[] } };

    expect(second.memory.supersedes).toContain(first.memory.id);
  });

  it("rejects a caller-supplied owner that differs from the configured isolated agent", async () => {
    const sdk = mockSdk();
    const kv = mockKV();
    registerRememberFunction(sdk as never, kv as never);
    configState.agentId = "agent_a";
    configState.isolated = true;

    const result = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "a caller cannot claim another agent's memory",
        agentId: "agent_b",
      },
    }) as { success: boolean; error: string };

    expect(result.success).toBe(false);
    expect(result.error).toMatch(/must match the configured AGENT_ID/);
    expect(await kv.list("mem:memories")).toEqual([]);
  });

  it("fails closed when isolated remember has no configured agent ID", async () => {
    const sdk = mockSdk();
    const kv = mockKV();
    registerRememberFunction(sdk as never, kv as never);
    configState.agentId = undefined;
    configState.isolated = true;

    const result = await sdk.trigger({
      function_id: "mem::remember",
      payload: {
        content: "a caller cannot provide the isolated owner",
        agentId: "agent_a",
      },
    }) as { success: boolean; error: string };

    expect(result.success).toBe(false);
    expect(result.error).toMatch(/AGENTMEMORY_AGENT_SCOPE=isolated/);
    expect(await kv.list("mem:memories")).toEqual([]);
  });

  it("does not supersede other-agent or unowned memories in isolated mode", async () => {
    const sdk = mockSdk();
    const kv = mockKV();
    registerRememberFunction(sdk as never, kv as never);
    const content = "keep this exact isolated ownership boundary for duplicates";
    const oldAgentMemory = {
      id: "mem-agent-a",
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
      type: "fact",
      title: content,
      content,
      concepts: [],
      files: [],
      sessionIds: [],
      strength: 1,
      version: 1,
      isLatest: true,
      agentId: "agent_a",
    };
    const unownedMemory = { ...oldAgentMemory, id: "mem-unowned", agentId: undefined };
    await kv.set("mem:memories", oldAgentMemory.id, oldAgentMemory);
    await kv.set("mem:memories", unownedMemory.id, unownedMemory);
    configState.agentId = "agent_b";
    configState.isolated = true;

    const result = await sdk.trigger({
      function_id: "mem::remember",
      payload: { content, type: "fact", project: "api" },
    }) as { memory: { supersedes: string[] } };

    expect(result.memory.supersedes).toEqual([]);
    expect((await kv.get<{ isLatest: boolean }>("mem:memories", oldAgentMemory.id))?.isLatest).toBe(true);
    expect((await kv.get<{ isLatest: boolean }>("mem:memories", unownedMemory.id))?.isLatest).toBe(true);
  });
});
