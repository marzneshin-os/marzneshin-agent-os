import { describe, it, expect } from "vitest";
import { KV } from "../src/state/schema.js";
import type {
  FastInferenceChannel,
  FastInferenceRouteRequest,
  FastInferenceRouteResponse,
  FastInferenceConfig,
  FastInferenceBenchmarkResult,
  ProviderType,
  AuditEntry,
} from "../src/types.js";

describe("Fast Inference Schema & Types", () => {
  it("defines KV.fastInference scope", () => {
    expect((KV as Record<string, string>).fastInference).toBe("mem:fast_inference");
  });

  it("supports fast-inference provider type", () => {
    const pType: ProviderType = "fast-inference";
    expect(pType).toBe("fast-inference");
  });

  it("verifies fast inference structures compile and hold expected values", () => {
    const channel: FastInferenceChannel = {
      id: "kimi-k3-fast",
      name: "Kimi K3 Fast Channel",
      provider: "fast-inference",
      endpoint: "https://api.moonshot.cn/v1/chat/completions",
      model: "kimi-k3",
      apiKey: "sk-test",
      priority: 1,
      enabled: true,
      latencyMs: 120,
      successRate: 0.99,
      failureCount: 0,
      circuitState: {
        state: "closed",
        failures: 0,
        lastFailureAt: null,
        openedAt: null,
      },
      lastCheckedAt: new Date().toISOString(),
    };

    const req: FastInferenceRouteRequest = {
      prompt: "Explain fast inference routing in 1 sentence",
      systemPrompt: "You are an assistant",
      preferredModel: "kimi-k3",
      strategy: "lowest-latency",
    };

    const resp: FastInferenceRouteResponse = {
      content: "Fast inference routes queries to the lowest-latency channel.",
      channelId: "kimi-k3-fast",
      channelName: "Kimi K3 Fast Channel",
      model: "kimi-k3",
      latencyMs: 120,
      failoverCount: 0,
      tokensUsed: { prompt: 15, completion: 12, total: 27 },
    };

    const benchmark: FastInferenceBenchmarkResult = {
      channelId: "kimi-k3-fast",
      latencyMs: 120,
      healthy: true,
      timestamp: new Date().toISOString(),
    };

    const config: FastInferenceConfig = {
      defaultStrategy: "lowest-latency",
      timeoutMs: 5000,
      maxFailoverRetries: 3,
      channels: [channel],
    };

    expect(channel.id).toBe("kimi-k3-fast");
    expect(req.strategy).toBe("lowest-latency");
    expect(resp.failoverCount).toBe(0);
    expect(benchmark.healthy).toBe(true);
    expect(config.channels.length).toBe(1);
  });

  it("verifies audit entry operation types include fast inference operations", () => {
    const audit1: AuditEntry = {
      id: "aud-1",
      timestamp: new Date().toISOString(),
      operation: "fast_inference_route",
      details: { channelId: "kimi-k3-fast", latencyMs: 120 },
    };
    const audit2: AuditEntry = {
      id: "aud-2",
      timestamp: new Date().toISOString(),
      operation: "fast_inference_configure",
      details: { updatedChannel: "deepseek-v4" },
    };
    expect(audit1.operation).toBe("fast_inference_route");
    expect(audit2.operation).toBe("fast_inference_configure");
  });
});
