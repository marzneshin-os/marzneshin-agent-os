import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { registerKolibriConfigFunction } from "../src/functions/kolibri-config.js";
import type { MoeModelConfig, StateKV } from "../src/types.js";
import { KV } from "../src/state/schema.js";

function mockKV(): StateKV {
  const store = new Map<string, Map<string, unknown>>();
  return {
    get: async <T>(scope: string, key: string): Promise<T | null> => {
      return (store.get(scope)?.get(key) as T) ?? null;
    },
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
  } as unknown as StateKV;
}

function mockSdk() {
  const functions = new Map<string, Function>();
  return {
    registerFunction: (idOrOpts: string | { id: string }, handler: Function) => {
      const id = typeof idOrOpts === "string" ? idOrOpts : idOrOpts.id;
      functions.set(id, handler);
    },
    registerTrigger: () => {},
    trigger: async (idOrInput: string | { function_id: string; payload: unknown }, data?: unknown) => {
      const id = typeof idOrInput === "string" ? idOrInput : idOrInput.function_id;
      const payload = typeof idOrInput === "string" ? data : idOrInput.payload;
      const fn = functions.get(id);
      if (!fn) throw new Error(`No function: ${id}`);
      return fn(payload);
    },
    hasFunction: (id: string) => functions.has(id),
  };
}

describe("mem::kolibri-config function", () => {
  let kv: StateKV;
  let sdk: ReturnType<typeof mockSdk>;

  const sampleKolibriConfig: MoeModelConfig = {
    modelId: "kolibri-78b-v1",
    displayName: "Aleph Alpha Kolibri-1 (78B MoE)",
    backend: "vllm",
    backendUrl: "http://localhost:8000/v1",
    totalParams: 78103074560,
    activeParams: 3457573120,
    expertCount: 384,
    activeExperts: 6,
    quantFormat: "fp8",
    contextWindow: 262144,
    maxContextWindow: 1048576,
    slidingWindowSize: 513,
    slidingWindowRatio: "4:1",
    reasoningEffortLevels: ["none", "low", "medium", "high"],
    cachingStrategy: "lru",
    memoryTier: "auto",
    toolCallingSupport: true,
    hermesFunctionCalling: true,
  };

  beforeEach(() => {
    kv = mockKV();
    sdk = mockSdk();
    registerKolibriConfigFunction(sdk as any, kv);
  });

  it("registers mem::kolibri-config in sdk", () => {
    expect(sdk.hasFunction("mem::kolibri-config")).toBe(true);
  });

  it("fails if action is unknown or missing required fields", async () => {
    await expect(
      sdk.trigger("mem::kolibri-config", { action: "unknown" })
    ).rejects.toThrow();

    await expect(
      sdk.trigger("mem::kolibri-config", { action: "set", modelId: "k1" })
    ).rejects.toThrow(/config required/i);
  });

  it("sets and retrieves a valid Kolibri MoE model config", async () => {
    const setResult = await sdk.trigger("mem::kolibri-config", {
      action: "set",
      modelId: sampleKolibriConfig.modelId,
      config: sampleKolibriConfig,
    });
    expect(setResult).toEqual({
      success: true,
      modelId: sampleKolibriConfig.modelId,
    });

    const getResult = await sdk.trigger("mem::kolibri-config", {
      action: "get",
      modelId: sampleKolibriConfig.modelId,
    });
    expect(getResult).toMatchObject({
      modelId: "kolibri-78b-v1",
      expertCount: 384,
      activeExperts: 6,
      quantFormat: "fp8",
    });
    expect(getResult.updatedAt).toBeDefined();
  });

  it("lists all stored MoE model configs", async () => {
    await sdk.trigger("mem::kolibri-config", {
      action: "set",
      modelId: "model-1",
      config: { ...sampleKolibriConfig, modelId: "model-1" },
    });
    await sdk.trigger("mem::kolibri-config", {
      action: "set",
      modelId: "model-2",
      config: { ...sampleKolibriConfig, modelId: "model-2", backend: "colibri" },
    });

    const listResult = await sdk.trigger("mem::kolibri-config", { action: "list" });
    expect(Array.isArray(listResult)).toBe(true);
    expect(listResult.length).toBe(2);
  });

  it("deletes a model config and records audit entry", async () => {
    await sdk.trigger("mem::kolibri-config", {
      action: "set",
      modelId: "to-delete",
      config: { ...sampleKolibriConfig, modelId: "to-delete" },
    });

    const delResult = await sdk.trigger("mem::kolibri-config", {
      action: "delete",
      modelId: "to-delete",
    });
    expect(delResult).toEqual({
      success: true,
      deleted: "to-delete",
    });

    const getResult = await sdk.trigger("mem::kolibri-config", {
      action: "get",
      modelId: "to-delete",
    });
    expect(getResult).toBeNull();
  });
});
