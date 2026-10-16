import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { registerMcpEndpoints } from "../src/mcp/server.js";
import { registerApiTriggers } from "../src/triggers/api.js";
import { registerKolibriConfigFunction } from "../src/functions/kolibri-config.js";
import { registerKolibriInferenceFunctions } from "../src/functions/kolibri-inference.js";
import { registerKolibriMetricsFunction } from "../src/functions/kolibri-metrics.js";
import { MoeInferenceEngine } from "../src/providers/fast-inference.js";
import type { StateKV } from "../src/types.js";

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
  const triggers = new Map<string, any>();
  return {
    registerFunction: (idOrOpts: string | { id: string }, handler: Function) => {
      const id = typeof idOrOpts === "string" ? idOrOpts : idOrOpts.id;
      functions.set(id, handler);
    },
    registerTrigger: (trigger: any) => {
      triggers.set(trigger.function_id, trigger);
    },
    trigger: async (idOrInput: string | { function_id: string; payload: unknown }, data?: unknown) => {
      const id = typeof idOrInput === "string" ? idOrInput : idOrInput.function_id;
      const payload = typeof idOrInput === "string" ? data : idOrInput.payload;
      const fn = functions.get(id);
      if (!fn) throw new Error(`No function: ${id}`);
      return fn(payload);
    },
    hasFunction: (id: string) => functions.has(id),
    hasTrigger: (id: string) => triggers.has(id),
  };
}

describe("Kolibri MCP & REST API Integration", () => {
  let kv: StateKV;
  let sdk: ReturnType<typeof mockSdk>;

  beforeEach(() => {
    kv = mockKV();
    sdk = mockSdk();

    const mockInvoker = vi.fn().mockResolvedValue({
      content: "MoE local inference response",
      tokensUsed: { prompt: 15, completion: 25, total: 40 },
      cachedExpertHitRate: 0.92,
    });
    const engine = new MoeInferenceEngine({ invoker: mockInvoker });

    registerKolibriConfigFunction(sdk as any, kv);
    registerKolibriInferenceFunctions(sdk as any, kv, engine);
    registerKolibriMetricsFunction(sdk as any, kv);
    registerMcpEndpoints(sdk as any, kv);
    registerApiTriggers(sdk as any, kv);
  });

  it("handles memory_kolibri_configure MCP tool call", async () => {
    const res = await sdk.trigger("mcp::tools::call", {
      body: {
        name: "memory_kolibri_configure",
      arguments: {
        modelId: "kolibri-test-1",
        displayName: "Kolibri-1 Test",
        backend: "colibri",
        backendUrl: "http://localhost:8080/v1",
        expertCount: 384,
        activeExperts: 6,
        quantFormat: "fp8",
        contextWindow: 262144,
        maxContextWindow: 1048576,
      },
    }});

    expect(res.status_code).toBe(200);
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.modelId).toBe("kolibri-test-1");
  });

  it("handles memory_kolibri_infer MCP tool call", async () => {
    // Configure model first
    await sdk.trigger("mem::kolibri-config", {
      action: "set",
      modelId: "kolibri-test-1",
      config: {
        modelId: "kolibri-test-1",
        displayName: "Kolibri-1 Test",
        backend: "vllm",
        backendUrl: "http://localhost:8000/v1",
      },
    });

    const res = await sdk.trigger("mcp::tools::call", {
      body: {
        name: "memory_kolibri_infer",
      arguments: {
        modelId: "kolibri-test-1",
        prompt: "Explain mixture of experts",
        reasoningEffort: "medium",
      },
    }});

    expect(res.status_code).toBe(200);
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.content).toBe("MoE local inference response");
  });

  it("handles memory_kolibri_discover and memory_kolibri_status MCP tool calls", async () => {
    const discRes = await sdk.trigger("mcp::tools::call", {
      body: {
        name: "memory_kolibri_discover",
        arguments: {},
      },
    });
    expect(discRes.status_code).toBe(200);

    const statRes = await sdk.trigger("mcp::tools::call", {
      body: {
        name: "memory_kolibri_status",
        arguments: {},
      },
    });
    expect(statRes.status_code).toBe(200);
    const parsed = JSON.parse(statRes.body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.runtime).toBe("agentmemory-kolibri-v1");
  });

  it("routes REST API triggers correctly", async () => {
    expect(sdk.hasTrigger("api::kolibri-discover")).toBe(true);
    expect(sdk.hasTrigger("api::kolibri-configure")).toBe(true);
    expect(sdk.hasTrigger("api::kolibri-infer")).toBe(true);
    expect(sdk.hasTrigger("api::kolibri-status")).toBe(true);

    const statusApiRes = await sdk.trigger("api::kolibri-status", {
      headers: {},
      query_params: {},
    });
    expect(statusApiRes.status_code).toBe(200);
    expect(statusApiRes.body.success).toBe(true);
  });
});
