import { describe, it, expect, vi, beforeEach } from "vitest";
import { registerFastInferenceFunctions, getFastInferenceRouter } from "../src/functions/fast-inference.js";
import type { StateKV } from "../src/types.js";

describe("Fast Inference Core Functions", () => {
  let mockKV: Record<string, unknown>;
  let kv: StateKV;
  let mockFunctions: Record<string, (data: unknown) => Promise<unknown>>;
  let mockSdk: {
    registerFunction: (id: string, handler: (data: unknown) => Promise<unknown>) => void;
  };

  beforeEach(() => {
    mockKV = {};
    kv = {
      get: vi.fn().mockImplementation(async (scope: string, key: string) => mockKV[`${scope}:${key}`] ?? null),
      set: vi.fn().mockImplementation(async (scope: string, key: string, val: unknown) => {
        mockKV[`${scope}:${key}`] = val;
      }),
      delete: vi.fn().mockImplementation(async (scope: string, key: string) => {
        delete mockKV[`${scope}:${key}`];
      }),
      list: vi.fn().mockImplementation(async () => []),
    } as unknown as StateKV;

    mockFunctions = {};
    mockSdk = {
      registerFunction: (id: string, handler: (data: unknown) => Promise<unknown>) => {
        mockFunctions[id] = handler;
      },
    };

    registerFastInferenceFunctions(mockSdk as any, kv);
  });

  it("registers all 4 core functions", () => {
    expect(mockFunctions["mem::fast-inference-route"]).toBeDefined();
    expect(mockFunctions["mem::fast-inference-channels"]).toBeDefined();
    expect(mockFunctions["mem::fast-inference-benchmark"]).toBeDefined();
    expect(mockFunctions["mem::fast-inference-configure"]).toBeDefined();
  });

  it("mem::fast-inference-route requires non-empty prompt", async () => {
    const handler = mockFunctions["mem::fast-inference-route"];
    await expect(handler({})).rejects.toThrow("prompt is required");
    await expect(handler({ prompt: "   " })).rejects.toThrow("prompt cannot be empty");
  });

  it("mem::fast-inference-route executes and returns routing telemetry", async () => {
    const handler = mockFunctions["mem::fast-inference-route"];
    const res = (await handler({
      prompt: "Explain speedup",
      systemPrompt: "You are helpful",
      strategy: "lowest-latency",
    })) as { success: boolean; content: string; channelId: string; latencyMs: number };

    expect(res.success).toBe(true);
    expect(res.content).toBeDefined();
    expect(res.channelId).toBeDefined();
    expect(res.latencyMs).toBeGreaterThan(0);
  });

  it("mem::fast-inference-channels returns channel list with circuit states", async () => {
    const handler = mockFunctions["mem::fast-inference-channels"];
    const res = (await handler({})) as { success: boolean; channels: Array<{ id: string; circuitState: unknown }> };

    expect(res.success).toBe(true);
    expect(Array.isArray(res.channels)).toBe(true);
    expect(res.channels.length).toBeGreaterThan(0);
    expect(res.channels[0].circuitState).toBeDefined();
  });

  it("mem::fast-inference-benchmark probes channels and updates rankings", async () => {
    const handler = mockFunctions["mem::fast-inference-benchmark"];
    const res = (await handler({})) as { success: boolean; results: Array<{ channelId: string; latencyMs: number }> };

    expect(res.success).toBe(true);
    expect(Array.isArray(res.results)).toBe(true);
    expect(res.results.length).toBeGreaterThan(0);
  });

  it("mem::fast-inference-configure updates channel properties", async () => {
    const handler = mockFunctions["mem::fast-inference-configure"];
    const res = (await handler({
      channelId: "fast-inference-primary",
      enabled: false,
    })) as { success: boolean; channel: { id: string; enabled: boolean } };

    expect(res.success).toBe(true);
    expect(res.channel.id).toBe("fast-inference-primary");
    expect(res.channel.enabled).toBe(false);
  });
});
