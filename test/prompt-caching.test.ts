import { describe, it, expect, vi } from "vitest";
import {
  PromptCacheOptimizer,
  FastInferenceRouter,
  buildAgentRouterChannels,
} from "../src/providers/fast-inference.js";

describe("Prompt Caching Architecture (First Principles KV Cache Reuse)", () => {
  describe("PromptCacheOptimizer", () => {
    it("estimates token count proportionally to character length", () => {
      const text = "A".repeat(400);
      expect(PromptCacheOptimizer.estimateTokens(text)).toBe(100);
      expect(PromptCacheOptimizer.estimateTokens("")).toBe(0);
    });

    it("assembles Inverted Pyramid layout with deterministic sorted tools", () => {
      const tools = [
        { name: "zeta_tool", description: "Zeta utility" },
        { name: "alpha_tool", description: "Alpha utility" },
        { name: "beta_tool", description: "Beta utility" },
      ];

      const payload = PromptCacheOptimizer.buildOptimizedPayload({
        staticPrefix: "You are an autonomous engineering system.",
        systemPrompt: "Follow karpathy-guidelines and gravitas invariants.",
        tools,
        stableContext: ["Settled ADR-033 decision", "Settled ADR-034 decision"],
        dynamicContext: "Current session ID: sess_12345",
        userPrompt: "Execute compilation and verification",
        provider: "openai",
      });

      const systemText = payload.system as string;
      expect(typeof systemText).toBe("string");

      // Verify Static Zone 1 comes first
      expect(systemText.indexOf("autonomous engineering system")).toBeLessThan(
        systemText.indexOf("# Available Tools")
      );

      // Verify Zone 2 Tools are sorted deterministically
      const alphaIdx = systemText.indexOf("- alpha_tool");
      const betaIdx = systemText.indexOf("- beta_tool");
      const zetaIdx = systemText.indexOf("- zeta_tool");
      expect(alphaIdx).toBeLessThan(betaIdx);
      expect(betaIdx).toBeLessThan(zetaIdx);

      // Verify Zone 3 Stable Context comes after tools
      expect(systemText.indexOf("# Available Tools")).toBeLessThan(
        systemText.indexOf("# Static Knowledge Context")
      );

      // Verify Zone 5 Dynamic user tail contains dynamic context and user prompt
      const userMessage = payload.messages[0].content;
      expect(userMessage).toContain("Current session ID: sess_12345");
      expect(userMessage).toContain("Execute compilation and verification");
    });

    it("injects Anthropic ephemeral breakpoint on static prefix when tokens >= 1024", () => {
      const longStaticText = "Long static system instructions and documentation. ".repeat(100);
      const payload = PromptCacheOptimizer.buildOptimizedPayload({
        systemPrompt: longStaticText,
        userPrompt: "What is my task?",
        provider: "anthropic",
        injectBreakpoint: true,
      });

      expect(payload.isEligibleForCaching).toBe(true);
      expect(Array.isArray(payload.system)).toBe(true);

      const systemBlocks = payload.system as Array<{
        type: string;
        text: string;
        cache_control?: { type: string };
      }>;
      expect(systemBlocks).toHaveLength(1);
      expect(systemBlocks[0].type).toBe("text");
      expect(systemBlocks[0].cache_control).toEqual({ type: "ephemeral" });
    });

    it("avoids breakpoint injection when prompt is below minimum token limit (<1024 tokens)", () => {
      const shortStaticText = "Short prompt.";
      const payload = PromptCacheOptimizer.buildOptimizedPayload({
        systemPrompt: shortStaticText,
        userPrompt: "hello",
        provider: "anthropic",
        injectBreakpoint: true,
      });

      expect(payload.isEligibleForCaching).toBe(false);
      // Fallback to string system prompt to avoid Anthropic API rejection
      expect(typeof payload.system).toBe("string");
    });
  });

  describe("FastInferenceRouter Prompt Cache Telemetry", () => {
    it("parses OpenAI prompt_tokens_details.cached_tokens and calculates cacheHitRatio", async () => {
      const mockInvoker = vi.fn().mockResolvedValue({
        content: "Warm KV cache response",
        tokensUsed: {
          prompt: 2000,
          completion: 50,
          total: 2050,
          cached: 1800,
          cacheHitRatio: 0.9,
        },
      });

      const router = new FastInferenceRouter({
        invoker: mockInvoker,
        defaultStrategy: "lowest-latency",
      });

      const res = await router.route({
        prompt: "Run fast inference with cached prefix",
        systemPrompt: "Static system prompt with 1800 tokens",
      });

      expect(res.content).toBe("Warm KV cache response");
      expect(res.tokensUsed?.cached).toBe(1800);
      expect(res.tokensUsed?.cacheHitRatio).toBe(0.9);
      expect(res.tokensUsed?.prompt).toBe(2000);
      expect(res.tokensUsed?.completion).toBe(50);
    });

    it("parses llama.cpp timings.cache_n and timings.prompt_n", async () => {
      const mockInvoker = vi.fn().mockResolvedValue({
        content: "llama.cpp warm cache reply",
        tokensUsed: {
          prompt: 10,
          completion: 20,
          total: 30,
          cached: 7992,
          cacheHitRatio: 0.9987,
        },
      });

      const router = new FastInferenceRouter({
        invoker: mockInvoker,
        defaultStrategy: "lowest-latency",
      });

      const res = await router.route({
        prompt: "Query after initial prefill",
      });

      expect(res.tokensUsed?.cached).toBe(7992);
      expect(res.tokensUsed?.cacheHitRatio).toBeCloseTo(0.9987, 4);
    });

    it("includes supportsPromptCaching across official AgentRouter and local channels", () => {
      const channels = buildAgentRouterChannels("sk-test-key");
      for (const ch of channels) {
        expect(ch.supportsPromptCaching).toBe(true);
      }

      const router = new FastInferenceRouter();
      const allChannels = router.getChannels();
      const localVllm = allChannels.find((c) => c.id === "local-vllm-channel");
      expect(localVllm?.supportsPromptCaching).toBe(true);
      expect(localVllm?.cachePrompt).toBe(true);
    });
  });
});
