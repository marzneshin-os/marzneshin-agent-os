import { describe, it, expect, vi, beforeEach } from "vitest";
import { getAllTools, FAST_INFERENCE_TOOLS } from "../src/mcp/tools-registry.js";
import { registerMcpEndpoints } from "../src/mcp/server.js";
import type { StateKV } from "../src/types.js";

describe("Fast Inference MCP Tools", () => {
  let mockKV: Record<string, unknown>;
  let kv: StateKV;
  let mockFunctions: Record<string, (req: any) => Promise<any>>;
  let mockSdk: any;

  beforeEach(() => {
    mockKV = {};
    kv = {
      get: vi.fn(),
      set: vi.fn(),
      delete: vi.fn(),
      list: vi.fn().mockResolvedValue([]),
    } as unknown as StateKV;

    mockFunctions = {};
    mockSdk = {
      registerFunction: vi.fn().mockImplementation((id: string, handler: any) => {
        mockFunctions[id] = handler;
      }),
      registerTrigger: vi.fn(),
      trigger: vi.fn().mockImplementation(async ({ function_id, payload }: any) => {
        if (function_id === "mem::fast-inference-route") {
          return {
            success: true,
            content: "Fast response",
            channelId: "kimi-k3-fast",
            latencyMs: 85,
            failoverCount: 0,
          };
        }
        if (function_id === "mem::fast-inference-channels") {
          return {
            success: true,
            channels: [{ id: "kimi-k3-fast", latencyMs: 85, enabled: true }],
          };
        }
        if (function_id === "mem::fast-inference-benchmark") {
          return {
            success: true,
            results: [{ channelId: "kimi-k3-fast", latencyMs: 85, healthy: true }],
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

    registerMcpEndpoints(mockSdk, kv, "test-secret");
  });

  it("exposes 4 fast inference tools in FAST_INFERENCE_TOOLS and getAllTools", () => {
    expect(FAST_INFERENCE_TOOLS.length).toBe(4);
    const names = FAST_INFERENCE_TOOLS.map((t) => t.name);
    expect(names).toContain("memory_fast_inference_route");
    expect(names).toContain("memory_fast_inference_channels");
    expect(names).toContain("memory_fast_inference_benchmark");
    expect(names).toContain("memory_fast_inference_configure");

    const all = getAllTools();
    for (const name of names) {
      expect(all.some((t) => t.name === name)).toBe(true);
    }
  });

  it("handles memory_fast_inference_route tool call successfully", async () => {
    const callHandler = mockFunctions["mcp::tools::call"];
    expect(callHandler).toBeDefined();

    const res = await callHandler({
      headers: { authorization: "Bearer test-secret" },
      body: {
        name: "memory_fast_inference_route",
        arguments: { prompt: "Test fast routing" },
      },
    });

    expect(res.status_code).toBe(200);
    const body = res.body;
    expect(body.content).toBeDefined();
    expect(body.content[0].type).toBe("text");
    const parsed = JSON.parse(body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.channelId).toBe("kimi-k3-fast");
  });

  it("handles memory_fast_inference_channels tool call successfully", async () => {
    const callHandler = mockFunctions["mcp::tools::call"];
    const res = await callHandler({
      headers: { authorization: "Bearer test-secret" },
      body: {
        name: "memory_fast_inference_channels",
        arguments: {},
      },
    });

    expect(res.status_code).toBe(200);
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.channels.length).toBe(1);
  });

  it("rejects memory_fast_inference_route with missing prompt", async () => {
    const callHandler = mockFunctions["mcp::tools::call"];
    const res = await callHandler({
      headers: { authorization: "Bearer test-secret" },
      body: {
        name: "memory_fast_inference_route",
        arguments: {},
      },
    });

    expect(res.status_code).toBe(400);
    expect(res.body.error).toContain("prompt is required");
  });
});
