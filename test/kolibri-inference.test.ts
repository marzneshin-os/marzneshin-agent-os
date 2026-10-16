import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import {
  MoeInferenceEngine,
} from "../src/providers/fast-inference.js";
import { registerKolibriInferenceFunctions } from "../src/functions/kolibri-inference.js";
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

describe("MoE / Kolibri Inference Engine & Functions", () => {
  let kv: StateKV;
  let sdk: ReturnType<typeof mockSdk>;

  const sampleModel: MoeModelConfig = {
    modelId: "kolibri-78b",
    displayName: "Aleph Alpha Kolibri-1 78B",
    backend: "vllm",
    backendUrl: "http://127.0.0.1:8000/v1",
    totalParams: 78103074560,
    activeParams: 3457573120,
    expertCount: 384,
    activeExperts: 6,
    quantFormat: "fp8",
    contextWindow: 262144,
    maxContextWindow: 1048576,
    slidingWindowSize: 512,
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

  describe("MoeInferenceEngine Unit Tests", () => {
    it("runs inference with reasoning effort mapping and SWA negotiation", async () => {
      const mockInvoker = vi.fn().mockResolvedValue({
        content: "Reasoned response from Kolibri-1",
        tokensUsed: { prompt: 25, completion: 40, total: 65 },
        cachedExpertHitRate: 0.85,
      });

      const engine = new MoeInferenceEngine({
        invoker: mockInvoker,
      });

      const response = await engine.infer(sampleModel, {
        modelId: sampleModel.modelId,
        prompt: "Analyze MoE sliding window attention",
        reasoningEffort: "high",
      });

      expect(response.content).toBe("Reasoned response from Kolibri-1");
      expect(response.reasoningEffort).toBe("high");
      expect(response.activeExpertsCount).toBe(6);
      expect(response.cachedExpertHitRate).toBe(0.85);
      expect(mockInvoker).toHaveBeenCalledTimes(1);
    });

    it("probes local backend endpoints for discovery", async () => {
      const mockProbe = vi.fn().mockImplementation(async (url: string) => {
        if (url.includes("8000")) {
          return {
            healthy: true,
            type: "vllm",
            modelsLoaded: ["kolibri-78b"],
            latencyMs: 15,
          };
        }
        return {
          healthy: false,
          type: "custom",
          modelsLoaded: [],
          latencyMs: 0,
          error: "Connection refused",
        };
      });

      const engine = new MoeInferenceEngine({
        prober: mockProbe,
      });

      const statuses = await engine.discoverBackends([
        "http://localhost:8000/v1",
        "http://localhost:11434",
      ]);

      expect(statuses.length).toBe(2);
      expect(statuses[0].healthy).toBe(true);
      expect(statuses[0].modelsLoaded).toContain("kolibri-78b");
      expect(statuses[1].healthy).toBe(false);
    });
  });

  describe("Kolibri Inference iii-engine Functions", () => {
    beforeEach(() => {
      const mockInvoker = vi.fn().mockResolvedValue({
        content: "Generated answer from local MoE",
        tokensUsed: { prompt: 10, completion: 20, total: 30 },
        cachedExpertHitRate: 0.9,
      });
      const engine = new MoeInferenceEngine({ invoker: mockInvoker });
      registerKolibriInferenceFunctions(sdk as any, kv, engine);
    });

    it("registers mem::kolibri-discover and mem::kolibri-infer", () => {
      expect(sdk.hasFunction("mem::kolibri-discover")).toBe(true);
      expect(sdk.hasFunction("mem::kolibri-infer")).toBe(true);
    });

    it("executes mem::kolibri-infer using stored model config", async () => {
      // Setup model config in KV
      await sdk.trigger("mem::kolibri-config", {
        action: "set",
        modelId: sampleModel.modelId,
        config: sampleModel,
      });

      const res = await sdk.trigger("mem::kolibri-infer", {
        modelId: sampleModel.modelId,
        prompt: "Hello Kolibri",
        reasoningEffort: "medium",
      });

      expect(res.success).toBe(true);
      expect(res.content).toBe("Generated answer from local MoE");
      expect(res.reasoningEffort).toBe("medium");
      expect(res.latencyMs).toBeGreaterThan(0);
    });

    it("fails mem::kolibri-infer if modelId is not registered in KV", async () => {
      await expect(
        sdk.trigger("mem::kolibri-infer", {
          modelId: "unregistered-moe",
          prompt: "Hello",
        })
      ).rejects.toThrow(/not found/i);
    });
  });
});
