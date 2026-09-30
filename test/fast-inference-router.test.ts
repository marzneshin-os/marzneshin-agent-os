import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  FastInferenceRouter,
  FastInferenceProvider,
} from "../src/providers/fast-inference.js";
import type { FastInferenceChannel } from "../src/types.js";

describe("FastInferenceRouter", () => {
  let channels: FastInferenceChannel[];

  beforeEach(() => {
    channels = [
      {
        id: "channel-fast",
        name: "Fast Channel (Kimi K3 / GLM)",
        provider: "fast-inference",
        endpoint: "https://fast.inference.local/v1/chat/completions",
        model: "kimi-k3",
        priority: 1,
        enabled: true,
        latencyMs: 80,
        successRate: 1.0,
        failureCount: 0,
        circuitState: { state: "closed", failures: 0, lastFailureAt: null, openedAt: null },
      },
      {
        id: "channel-standard",
        name: "Standard Channel (Claude / OpenAI)",
        provider: "openai",
        endpoint: "https://api.openai.com/v1/chat/completions",
        model: "gpt-5.6-luna",
        priority: 2,
        enabled: true,
        latencyMs: 350,
        successRate: 1.0,
        failureCount: 0,
        circuitState: { state: "closed", failures: 0, lastFailureAt: null, openedAt: null },
      },
    ];
  });

  it("routes to the lowest-latency channel by default", async () => {
    const mockInvoker = vi.fn().mockImplementation(async (ch: FastInferenceChannel) => {
      return {
        content: `Response from ${ch.id}`,
        tokensUsed: { prompt: 10, completion: 5, total: 15 },
      };
    });

    const router = new FastInferenceRouter({
      channels,
      defaultStrategy: "lowest-latency",
      invoker: mockInvoker,
    });

    const result = await router.route({
      prompt: "Summarize current context",
    });

    expect(result.channelId).toBe("channel-fast");
    expect(result.content).toBe("Response from channel-fast");
    expect(result.failoverCount).toBe(0);
    expect(mockInvoker).toHaveBeenCalledTimes(1);
  });

  it("automatically fails over to the next channel when the primary fails", async () => {
    const mockInvoker = vi.fn().mockImplementation(async (ch: FastInferenceChannel) => {
      if (ch.id === "channel-fast") {
        throw new Error("HTTP 429 Too Many Requests");
      }
      return {
        content: `Failover response from ${ch.id}`,
        tokensUsed: { prompt: 10, completion: 15, total: 25 },
      };
    });

    const router = new FastInferenceRouter({
      channels,
      defaultStrategy: "lowest-latency",
      invoker: mockInvoker,
    });

    const result = await router.route({
      prompt: "Explain architecture",
    });

    expect(result.channelId).toBe("channel-standard");
    expect(result.content).toBe("Failover response from channel-standard");
    expect(result.failoverCount).toBe(1);
    expect(result.failoverHops).toEqual(["channel-fast"]);
    expect(mockInvoker).toHaveBeenCalledTimes(2);
  });

  it("skips channels whose circuit breaker is tripped open", async () => {
    const mockInvoker = vi.fn().mockImplementation(async (ch: FastInferenceChannel) => {
      return { content: `Response from ${ch.id}` };
    });

    const router = new FastInferenceRouter({
      channels,
      defaultStrategy: "lowest-latency",
      invoker: mockInvoker,
    });

    // Artificially trip circuit breaker on channel-fast
    router.tripCircuit("channel-fast");

    const result = await router.route({
      prompt: "Hello router",
    });

    // Should skip channel-fast and go straight to channel-standard
    expect(result.channelId).toBe("channel-standard");
    expect(result.failoverCount).toBe(0);
    expect(mockInvoker).toHaveBeenCalledTimes(1);
  });

  it("benchmarks enabled channels and updates latency rankings", async () => {
    const mockInvoker = vi.fn().mockImplementation(async (ch: FastInferenceChannel) => {
      return { content: "pong" };
    });

    const router = new FastInferenceRouter({
      channels,
      invoker: mockInvoker,
    });

    const results = await router.benchmark();
    expect(results.length).toBe(2);
    expect(results.every((r) => r.healthy)).toBe(true);

    const updated = router.getChannels();
    expect(updated.length).toBe(2);
    expect(updated[0].lastCheckedAt).toBeDefined();
  });

  it("implements MemoryProvider interface for internal agentmemory usage", async () => {
    const mockInvoker = vi.fn().mockImplementation(async () => {
      return { content: "Compressed memory summary" };
    });

    const router = new FastInferenceRouter({
      channels,
      invoker: mockInvoker,
    });

    const provider = new FastInferenceProvider(router);
    expect(provider.name).toBe("fast-inference");

    const comp = await provider.compress("sys", "user text");
    expect(comp).toBe("Compressed memory summary");

    const sum = await provider.summarize("sys", "user text");
    expect(sum).toBe("Compressed memory summary");
  });
});
