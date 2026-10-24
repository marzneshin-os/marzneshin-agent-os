import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  scrubAgentRouterPayload,
  isAgentRouterEndpoint,
  buildAgentRouterChannels,
  FastInferenceRouter,
} from "../src/providers/fast-inference.js";
import { detectProvider, detectLlmProviderKind } from "../src/config.js";

describe("AgentRouter Multi-Harness Model Mesh (ADR-033)", () => {
  describe("scrubAgentRouterPayload", () => {
    it("strips stateful decryption and storage fields for gpt-6.1sol", () => {
      const payload: Record<string, unknown> = {
        model: "gpt-6.1sol",
        messages: [{ role: "user", content: "hello" }],
        previous_response_id: "resp_prev_123",
        reasoning_encrypted_content: "gAAAAABencrypted...",
        encrypted_content: "enc_data_456",
        store: true,
        output_config: { format: "json" },
        thinking: { type: "adaptive", budget_tokens: 1024 },
        temperature: 0.7,
      };

      const scrubbed = scrubAgentRouterPayload("gpt-6.1sol", payload);

      expect(scrubbed["previous_response_id"]).toBeUndefined();
      expect(scrubbed["reasoning_encrypted_content"]).toBeUndefined();
      expect(scrubbed["encrypted_content"]).toBeUndefined();
      expect(scrubbed["store"]).toBeUndefined();
      expect(scrubbed["output_config"]).toBeUndefined();
      expect(scrubbed["thinking"]).toBeUndefined();
      expect(scrubbed["model"]).toBe("gpt-6.1sol");
      expect(scrubbed["temperature"]).toBe(0.7);
      expect(scrubbed["messages"]).toEqual([{ role: "user", content: "hello" }]);
    });

    it("strips fields for gpt-6-astra and gpt-5.6-sol", () => {
      const payload: Record<string, unknown> = {
        model: "gpt-6-astra",
        previous_response_id: "resp_123",
        store: false,
      };
      const scrubbed = scrubAgentRouterPayload("gpt-6-astra", payload);
      expect(scrubbed["previous_response_id"]).toBeUndefined();
      expect(scrubbed["store"]).toBeUndefined();
    });

    it("preserves standard payloads for non-AgentRouter models without state keys", () => {
      const payload: Record<string, unknown> = {
        model: "llama-3-70b",
        messages: [{ role: "user", content: "ping" }],
        temperature: 0.5,
      };
      const scrubbed = scrubAgentRouterPayload("llama-3-70b", payload);
      expect(scrubbed).toEqual(payload);
    });
  });

  describe("isAgentRouterEndpoint", () => {
    it("identifies official agentrouter domain and local gateway port", () => {
      expect(isAgentRouterEndpoint("https://agentrouter.org/v1/chat/completions")).toBe(true);
      expect(isAgentRouterEndpoint("http://127.0.0.1:8787/v1/messages")).toBe(true);
      expect(isAgentRouterEndpoint("http://localhost:8787/v1")).toBe(true);
    });

    it("returns false for external non-agentrouter endpoints", () => {
      expect(isAgentRouterEndpoint("https://api.openai.com/v1/chat/completions")).toBe(false);
      expect(isAgentRouterEndpoint("https://api.anthropic.com/v1/messages")).toBe(false);
      expect(isAgentRouterEndpoint("")).toBe(false);
    });
  });

  describe("buildAgentRouterChannels", () => {
    it("builds the 5 official AgentRouter channels with correct tiers and priorities", () => {
      const channels = buildAgentRouterChannels("sk-test-key", "https://agentrouter.org/v1");
      expect(channels).toHaveLength(5);

      const ids = channels.map((c) => c.id);
      expect(ids).toContain("agentrouter-gpt-6-1sol");
      expect(ids).toContain("agentrouter-gpt-6-astra");
      expect(ids).toContain("agentrouter-claude-opus-5");
      expect(ids).toContain("agentrouter-glm-5-3");
      expect(ids).toContain("agentrouter-deepseek-v4-flash");

      const sol = channels.find((c) => c.id === "agentrouter-gpt-6-1sol");
      expect(sol?.endpoint).toBe("https://agentrouter.org/v1/chat/completions");
      expect(sol?.model).toBe("gpt-6.1sol");
      expect(sol?.apiKey).toBe("sk-test-key");
    });
  });

  describe("FastInferenceRouter with AgentRouter Mesh", () => {
    it("routes requests to primary channel and falls over on failure", async () => {
      const mockInvoker = vi.fn();
      mockInvoker
        .mockRejectedValueOnce(new Error("Channel agentrouter-gpt-6-1sol returned HTTP 503: Decryption Failure (解密失败)"))
        .mockResolvedValueOnce({
          content: "Successful response from Astra fallback",
          tokensUsed: { prompt: 10, completion: 20, total: 30 },
        });

      const channels = buildAgentRouterChannels("sk-test-key", "http://127.0.0.1:8787/v1");
      const router = new FastInferenceRouter({
        channels,
        invoker: mockInvoker,
        defaultStrategy: "fallback-chain",
      });

      const res = await router.route({
        prompt: "Run mission critical reasoning",
        strategy: "fallback-chain",
      });

      expect(res.content).toBe("Successful response from Astra fallback");
      expect(res.channelId).toBe("agentrouter-gpt-6-astra");
      expect(mockInvoker).toHaveBeenCalledTimes(2);
    });
  });

  describe("detectProvider with AGENTROUTER_API_KEY", () => {
    it("detects AgentRouter as OpenAI-compatible provider when key is set", () => {
      const env = {
        AGENTROUTER_API_KEY: "sk-test-key",
        AGENTROUTER_BASE_URL: "https://agentrouter.org/v1",
        AGENTROUTER_MODEL: "deepseek-v4-flash",
      };

      const provider = detectProvider(env);
      expect(provider.provider).toBe("openai");
      expect(provider.model).toBe("deepseek-v4-flash");
      expect(provider.baseURL).toBe("https://agentrouter.org/v1");
    });

    it("recognizes AGENTROUTER_API_KEY in detectLlmProviderKind", () => {
      const origEnv = process.env.AGENTROUTER_API_KEY;
      try {
        process.env.AGENTROUTER_API_KEY = "sk-test-key";
        const kind = detectLlmProviderKind();
        expect(kind).toBe("llm");
      } finally {
        if (origEnv === undefined) {
          delete process.env.AGENTROUTER_API_KEY;
        } else {
          process.env.AGENTROUTER_API_KEY = origEnv;
        }
      }
    });
  });
});
