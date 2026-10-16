import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { registerKolibriMetricsFunction } from "../src/functions/kolibri-metrics.js";
import type { StateKV } from "../src/types.js";
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

describe("mem::kolibri-metrics and mem::kolibri-status functions", () => {
  let kv: StateKV;
  let sdk: ReturnType<typeof mockSdk>;

  beforeEach(() => {
    kv = mockKV();
    sdk = mockSdk();
    registerKolibriMetricsFunction(sdk as any, kv);
  });

  it("registers mem::kolibri-metrics and mem::kolibri-status", () => {
    expect(sdk.hasFunction("mem::kolibri-metrics")).toBe(true);
    expect(sdk.hasFunction("mem::kolibri-status")).toBe(true);
  });

  it("retrieves and lists model metrics", async () => {
    await kv.set(KV.moeMetrics, "metric_kolibri-78b", {
      modelId: "kolibri-78b",
      totalRequests: 42,
      avgLatencyMs: 120,
      totalTokens: 15400,
      avgExpertHitRate: 0.88,
      errorCount: 0,
      lastUpdated: new Date().toISOString(),
    });

    const getRes = await sdk.trigger("mem::kolibri-metrics", {
      action: "get",
      modelId: "kolibri-78b",
    });
    expect(getRes).toMatchObject({
      modelId: "kolibri-78b",
      totalRequests: 42,
    });

    const listRes = await sdk.trigger("mem::kolibri-metrics", { action: "list" });
    expect(Array.isArray(listRes)).toBe(true);
    expect(listRes.length).toBe(1);
  });

  it("returns comprehensive runtime status via mem::kolibri-status", async () => {
    await kv.set(KV.moeModels, "kolibri-78b", {
      modelId: "kolibri-78b",
      displayName: "Kolibri-1",
    });
    await kv.set(KV.moeBackends, "vllm_local", {
      backendId: "vllm_local",
      type: "vllm",
      url: "http://localhost:8000/v1",
      healthy: true,
      latencyMs: 25,
      modelsLoaded: ["kolibri-78b"],
      lastCheckedAt: new Date().toISOString(),
    });

    const status = await sdk.trigger("mem::kolibri-status", {});
    expect(status.success).toBe(true);
    expect(status.modelsCount).toBe(1);
    expect(status.backendsCount).toBe(1);
    expect(status.healthyBackendsCount).toBe(1);
  });
});
