import type {
  MemoryProvider,
  FastInferenceChannel,
  FastInferenceRouteRequest,
  FastInferenceRouteResponse,
  FastInferenceBenchmarkResult,
} from "../types.js";
import { CircuitBreaker } from "./circuit-breaker.js";
import { fetchWithTimeout } from "./_fetch.js";
import { getEnvVar } from "../config.js";

export type ChannelInvoker = (
  channel: FastInferenceChannel,
  prompt: string,
  systemPrompt?: string,
  options?: { maxTokens?: number; temperature?: number }
) => Promise<{
  content: string;
  tokensUsed?: { prompt: number; completion: number; total: number };
}>;

export interface FastInferenceRouterOptions {
  channels?: FastInferenceChannel[];
  defaultStrategy?: "lowest-latency" | "fallback-chain" | "cost-optimized";
  invoker?: ChannelInvoker;
  timeoutMs?: number;
}

export class FastInferenceRouter {
  private channels: Map<string, FastInferenceChannel> = new Map();
  private breakers: Map<string, CircuitBreaker> = new Map();
  private invoker: ChannelInvoker;
  private defaultStrategy: "lowest-latency" | "fallback-chain" | "cost-optimized";
  private timeoutMs: number;

  constructor(opts?: FastInferenceRouterOptions) {
    this.defaultStrategy = opts?.defaultStrategy || "lowest-latency";
    this.timeoutMs = opts?.timeoutMs || 15_000;
    this.invoker = opts?.invoker || this.defaultHttpInvoker.bind(this);

    const initial = opts?.channels || this.buildDefaultChannels();
    for (const ch of initial) {
      this.addChannel(ch);
    }
  }

  addChannel(ch: FastInferenceChannel): void {
    this.channels.set(ch.id, { ...ch });
    if (!this.breakers.has(ch.id)) {
      this.breakers.set(
        ch.id,
        new CircuitBreaker({
          failureThreshold: 3,
          failureWindowMs: 60_000,
          recoveryTimeoutMs: 30_000,
        })
      );
    }
  }

  getChannels(): FastInferenceChannel[] {
    return Array.from(this.channels.values()).map((ch) => {
      const breaker = this.breakers.get(ch.id);
      return {
        ...ch,
        circuitState: breaker ? breaker.getState() : ch.circuitState,
      };
    });
  }

  updateChannel(
    id: string,
    patch: Partial<FastInferenceChannel>
  ): FastInferenceChannel | null {
    const existing = this.channels.get(id);
    if (!existing) return null;
    const updated = { ...existing, ...patch, id };
    this.channels.set(id, updated);
    return updated;
  }

  tripCircuit(channelId: string): void {
    const breaker = this.breakers.get(channelId);
    if (breaker) {
      breaker.recordFailure();
      breaker.recordFailure();
      breaker.recordFailure();
    }
  }

  async route(req: FastInferenceRouteRequest): Promise<FastInferenceRouteResponse> {
    const strategy = req.strategy || this.defaultStrategy;
    const candidates = this.getEligibleChannels(strategy, req.preferredModel);

    if (candidates.length === 0) {
      throw new Error("No available healthy channels for fast inference");
    }

    let failoverCount = 0;
    const failoverHops: string[] = [];
    let lastError: Error | null = null;

    for (const channel of candidates) {
      const breaker = this.breakers.get(channel.id);
      const startMs = Date.now();

      try {
        const result = await this.invoker(
          channel,
          req.prompt,
          req.systemPrompt,
          { maxTokens: req.maxTokens, temperature: req.temperature }
        );

        const latencyMs = Math.max(1, Date.now() - startMs);

        // Update exponential moving average latency: 0.3 * new + 0.7 * old
        const updatedLatency = Math.round(channel.latencyMs * 0.7 + latencyMs * 0.3);
        this.updateChannel(channel.id, {
          latencyMs: updatedLatency,
          lastCheckedAt: new Date().toISOString(),
        });

        if (breaker) {
          breaker.recordSuccess();
        }

        return {
          content: result.content,
          channelId: channel.id,
          channelName: channel.name,
          model: channel.model,
          latencyMs,
          failoverCount,
          failoverHops: failoverHops.length > 0 ? failoverHops : undefined,
          tokensUsed: result.tokensUsed,
        };
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        failoverCount += 1;
        failoverHops.push(channel.id);

        if (breaker) {
          breaker.recordFailure();
        }

        const failCount = (channel.failureCount || 0) + 1;
        this.updateChannel(channel.id, {
          failureCount: failCount,
          lastCheckedAt: new Date().toISOString(),
        });
      }
    }

    throw new Error(
      `Fast inference routing exhausted all ${candidates.length} channels. Hops: [${failoverHops.join(" -> ")}]. Last error: ${lastError?.message}`
    );
  }

  async benchmark(targetChannelId?: string): Promise<FastInferenceBenchmarkResult[]> {
    const channelsToProbe = targetChannelId
      ? Array.from(this.channels.values()).filter((c) => c.id === targetChannelId)
      : Array.from(this.channels.values()).filter((c) => c.enabled);

    const probeTimestamp = new Date().toISOString();

    const results = await Promise.all(
      channelsToProbe.map(async (ch) => {
        const start = Date.now();
        try {
          await this.invoker(ch, "ping", "respond pong");
          const latencyMs = Math.max(1, Date.now() - start);
          this.updateChannel(ch.id, {
            latencyMs,
            lastCheckedAt: probeTimestamp,
          });
          const breaker = this.breakers.get(ch.id);
          if (breaker) breaker.recordSuccess();
          return {
            channelId: ch.id,
            latencyMs,
            healthy: true,
            timestamp: probeTimestamp,
          };
        } catch (err) {
          const latencyMs = Math.max(1, Date.now() - start);
          const breaker = this.breakers.get(ch.id);
          if (breaker) breaker.recordFailure();
          return {
            channelId: ch.id,
            latencyMs,
            healthy: false,
            timestamp: probeTimestamp,
            error: err instanceof Error ? err.message : String(err),
          };
        }
      })
    );

    return results;
  }

  private getEligibleChannels(
    strategy: "lowest-latency" | "fallback-chain" | "cost-optimized",
    preferredModel?: string
  ): FastInferenceChannel[] {
    const list = Array.from(this.channels.values()).filter((c) => c.enabled);

    // Filter out tripped circuit breakers unless all are open
    const closed = list.filter((c) => {
      const breaker = this.breakers.get(c.id);
      return !breaker || breaker.isAllowed;
    });

    const activePool = closed.length > 0 ? closed : list;

    if (preferredModel) {
      const modelMatches = activePool.filter((c) => c.model.includes(preferredModel));
      if (modelMatches.length > 0) return modelMatches;
    }

    switch (strategy) {
      case "lowest-latency":
        return [...activePool].sort((a, b) => a.latencyMs - b.latencyMs);
      case "cost-optimized":
        return [...activePool].sort((a, b) => a.priority - b.priority || a.latencyMs - b.latencyMs);
      case "fallback-chain":
      default:
        return [...activePool].sort((a, b) => a.priority - b.priority);
    }
  }

  private buildDefaultChannels(): FastInferenceChannel[] {
    const fastKey = getEnvVar("FAST_INFERENCE_API_KEY") || getEnvVar("OPENAI_API_KEY") || "";
    const fastUrl =
      getEnvVar("FAST_INFERENCE_BASE_URL") ||
      getEnvVar("OPENAI_BASE_URL") ||
      "https://api.openai.com/v1/chat/completions";

    return [
      {
        id: "fast-inference-primary",
        name: "Fast Inference Ultra Channel",
        provider: "fast-inference",
        endpoint: fastUrl,
        model: getEnvVar("FAST_INFERENCE_MODEL") || "kimi-k3",
        apiKey: fastKey,
        priority: 1,
        enabled: true,
        latencyMs: 95,
        successRate: 0.99,
        failureCount: 0,
        circuitState: { state: "closed", failures: 0, lastFailureAt: null, openedAt: null },
      },
      {
        id: "deepseek-v4-channel",
        name: "DeepSeek V4 Fast Channel",
        provider: "openai",
        endpoint: "https://api.deepseek.com/v1/chat/completions",
        model: "deepseek-chat",
        apiKey: getEnvVar("DEEPSEEK_API_KEY") || fastKey,
        priority: 2,
        enabled: true,
        latencyMs: 140,
        successRate: 0.98,
        failureCount: 0,
        circuitState: { state: "closed", failures: 0, lastFailureAt: null, openedAt: null },
      },
      {
        id: "local-vllm-channel",
        name: "Local High-Speed Engine (vLLM/Ollama)",
        provider: "custom",
        endpoint: "http://127.0.0.1:11434/v1/chat/completions",
        model: "qwen2.5-coder",
        priority: 3,
        enabled: false,
        latencyMs: 45,
        successRate: 1.0,
        failureCount: 0,
        circuitState: { state: "closed", failures: 0, lastFailureAt: null, openedAt: null },
      },
    ];
  }

  private async defaultHttpInvoker(
    channel: FastInferenceChannel,
    prompt: string,
    systemPrompt?: string,
    options?: { maxTokens?: number; temperature?: number }
  ): Promise<{
    content: string;
    tokensUsed?: { prompt: number; completion: number; total: number };
  }> {
    if (!channel.apiKey && !channel.endpoint.includes("localhost") && !channel.endpoint.includes("127.0.0.1")) {
      // Deterministic zero-LLM fallback if no keys configured
      return {
        content: `[zero-llm fast-inference] Heuristic response for: ${prompt.slice(0, 100)}`,
        tokensUsed: { prompt: prompt.length / 4, completion: 20, total: prompt.length / 4 + 20 },
      };
    }

    const messages = [];
    if (systemPrompt) {
      messages.push({ role: "system", content: systemPrompt });
    }
    messages.push({ role: "user", content: prompt });

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (channel.apiKey) {
      headers["Authorization"] = `Bearer ${channel.apiKey}`;
    }

    const res = await fetchWithTimeout(channel.endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: channel.model,
        messages,
        max_tokens: options?.maxTokens || 1024,
        temperature: options?.temperature ?? 0.2,
      }),
      timeoutMs: this.timeoutMs,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Channel ${channel.id} returned HTTP ${res.status}: ${errText}`);
    }

    const json = (await res.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
      usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    };

    const text = json.choices?.[0]?.message?.content || "";
    return {
      content: text,
      tokensUsed: json.usage
        ? {
            prompt: json.usage.prompt_tokens || 0,
            completion: json.usage.completion_tokens || 0,
            total: json.usage.total_tokens || 0,
          }
        : undefined,
    };
  }
}

export class FastInferenceProvider implements MemoryProvider {
  name = "fast-inference";

  constructor(private router: FastInferenceRouter) {}

  async compress(systemPrompt: string, userPrompt: string): Promise<string> {
    const res = await this.router.route({
      systemPrompt,
      prompt: userPrompt,
      strategy: "lowest-latency",
    });
    return res.content;
  }

  async summarize(systemPrompt: string, userPrompt: string): Promise<string> {
    const res = await this.router.route({
      systemPrompt,
      prompt: userPrompt,
      strategy: "lowest-latency",
    });
    return res.content;
  }
}
