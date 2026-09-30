import { describe, it, expect, vi, beforeEach } from "vitest";
import { registerApiTriggers } from "../src/triggers/api.js";
import type { StateKV } from "../src/types.js";

describe("Fast Inference REST API Endpoints", () => {
  let mockFunctions: Record<string, (req: any) => Promise<any>>;
  let mockTriggers: Array<{ function_id: string; config: { api_path: string; http_method: string } }>;
  let mockSdk: any;
  let kv: StateKV;
  const secret = "test-api-secret";

  beforeEach(() => {
    mockFunctions = {};
    mockTriggers = [];
    mockSdk = {
      registerFunction: vi.fn().mockImplementation((id: string, handler: any) => {
        mockFunctions[id] = handler;
      }),
      registerTrigger: vi.fn().mockImplementation((trigger: any) => {
        mockTriggers.push(trigger);
      }),
      trigger: vi.fn().mockImplementation(async ({ function_id, payload }: any) => {
        if (function_id === "mem::fast-inference-route") {
          return {
            success: true,
            content: "Routed output",
            channelId: "kimi-k3-fast",
            latencyMs: 92,
          };
        }
        if (function_id === "mem::fast-inference-channels") {
          return {
            success: true,
            channels: [{ id: "kimi-k3-fast", latencyMs: 92 }],
          };
        }
        if (function_id === "mem::fast-inference-benchmark") {
          return {
            success: true,
            results: [{ channelId: "kimi-k3-fast", latencyMs: 92, healthy: true }],
          };
        }
        if (function_id === "mem::fast-inference-configure") {
          return {
            success: true,
            channel: { id: payload.channelId, enabled: payload.enabled },
          };
        }
        return { success: false };
      }),
    };

    kv = {} as unknown as StateKV;
    registerApiTriggers(mockSdk, kv, secret);
  });

  it("registers 4 REST triggers for inference", () => {
    const paths = mockTriggers.map((t) => `${t.config.http_method} ${t.config.api_path}`);
    expect(paths).toContain("POST /agentmemory/inference/route");
    expect(paths).toContain("GET /agentmemory/inference/channels");
    expect(paths).toContain("POST /agentmemory/inference/benchmark");
    expect(paths).toContain("POST /agentmemory/inference/configure");
  });

  it("rejects unauthenticated requests", async () => {
    const routeHandler = mockFunctions["api::inference-route"];
    expect(routeHandler).toBeDefined();

    const res = await routeHandler({
      headers: {},
      body: { prompt: "Test unauth" },
    });

    expect(res.status_code).toBe(401);
  });

  it("handles POST /agentmemory/inference/route successfully", async () => {
    const routeHandler = mockFunctions["api::inference-route"];
    const res = await routeHandler({
      headers: { authorization: `Bearer ${secret}` },
      body: { prompt: "Explain fast inference", strategy: "lowest-latency" },
    });

    expect(res.status_code).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.content).toBe("Routed output");
    expect(res.body.channelId).toBe("kimi-k3-fast");
  });

  it("handles GET /agentmemory/inference/channels successfully", async () => {
    const channelsHandler = mockFunctions["api::inference-channels"];
    expect(channelsHandler).toBeDefined();

    const res = await channelsHandler({
      headers: { authorization: `Bearer ${secret}` },
      query: {},
    });

    expect(res.status_code).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.channels.length).toBe(1);
  });

  it("handles POST /agentmemory/inference/benchmark successfully", async () => {
    const benchHandler = mockFunctions["api::inference-benchmark"];
    expect(benchHandler).toBeDefined();

    const res = await benchHandler({
      headers: { authorization: `Bearer ${secret}` },
      body: {},
    });

    expect(res.status_code).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.results.length).toBe(1);
  });

  it("handles POST /agentmemory/inference/configure successfully", async () => {
    const configHandler = mockFunctions["api::inference-configure"];
    expect(configHandler).toBeDefined();

    const res = await configHandler({
      headers: { authorization: `Bearer ${secret}` },
      body: { channelId: "kimi-k3-fast", enabled: false },
    });

    expect(res.status_code).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.channel.enabled).toBe(false);
  });
});
