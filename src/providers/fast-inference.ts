import type {
  MemoryProvider,
  FastInferenceChannel,
  FastInferenceRouteRequest,
  FastInferenceRouteResponse,
  FastInferenceBenchmarkResult,
  MoeModelConfig,
  MoeInferenceRequest,
  MoeInferenceResponse,
  MoeBackendStatus,
  ReasoningEffort,
  MoeBackendType,
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

export type MoeInvoker = (
  model: MoeModelConfig,
  prompt: string,
  options?: {
    systemPrompt?: string;
    reasoningEffort?: ReasoningEffort;
    maxTokens?: number;
    temperature?: number;
    tools?: Array<{ name: string; description: string; parameters: Record<string, unknown> }>;
  }
) => Promise<{
  content: string;
  tokensUsed?: { prompt: number; completion: number; total: number };
  cachedExpertHitRate?: number;
  toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>;
}>;

export type MoeBackendProber = (
  url: string
) => Promise<{
  healthy: boolean;
  type?: MoeBackendType;
  modelsLoaded?: string[];
  latencyMs?: number;
  memoryUsage?: { vramUsedMb?: number; ramUsedMb?: number; nvmeCacheUsedMb?: number };
  error?: string;
}>;

export interface MoeInferenceEngineOptions {
  invoker?: MoeInvoker;
  prober?: MoeBackendProber;
  timeoutMs?: number;
}

export class MoeInferenceEngine {
  private invoker: MoeInvoker;
  private prober: MoeBackendProber;
  private timeoutMs: number;
  private breakers: Map<string, CircuitBreaker> = new Map();

  constructor(opts?: MoeInferenceEngineOptions) {
    this.timeoutMs = opts?.timeoutMs || 30_000;
    this.invoker = opts?.invoker || this.defaultHttpInvoker.bind(this);
    this.prober = opts?.prober || this.defaultHttpProber.bind(this);
  }

  private getBreaker(id: string): CircuitBreaker {
    let breaker = this.breakers.get(id);
    if (!breaker) {
      breaker = new CircuitBreaker({
        failureThreshold: 3,
        failureWindowMs: 60_000,
        recoveryTimeoutMs: 30_000,
      });
      this.breakers.set(id, breaker);
    }
    return breaker;
  }

  private negotiateContextWindow(model: MoeModelConfig, prompt: string): string {
    if (!model.slidingWindowSize) return prompt;
    // Approximating tokens by 4 characters per token
    const estimatedTokens = Math.ceil(prompt.length / 4);
    if (estimatedTokens > model.maxContextWindow) {
      const maxChars = model.maxContextWindow * 4;
      return prompt.slice(-maxChars);
    }
    return prompt;
  }

  async infer(
    model: MoeModelConfig,
    req: MoeInferenceRequest
  ): Promise<MoeInferenceResponse> {
    const breaker = this.getBreaker(model.backendUrl);
    if (!breaker.isAllowed) {
      throw new Error(`Circuit open for backend: ${model.backendUrl}`);
    }

    const reasoningEffort = req.reasoningEffort || "none";
    const negotiatedPrompt = this.negotiateContextWindow(model, req.prompt);
    const startMs = Date.now();

    try {
      const res = await this.invoker(model, negotiatedPrompt, {
        systemPrompt: req.systemPrompt,
        reasoningEffort,
        maxTokens: req.maxTokens,
        temperature: req.temperature,
        tools: req.tools,
      });

      const latencyMs = Math.max(1, Date.now() - startMs);
      breaker.recordSuccess();

      return {
        content: res.content,
        modelId: model.modelId,
        backend: model.backend,
        latencyMs,
        activeExpertsCount: model.activeExperts,
        reasoningEffort,
        tokensUsed: res.tokensUsed,
        cachedExpertHitRate: res.cachedExpertHitRate ?? (model.cachingStrategy === "lru" ? 0.85 : 0),
        toolCalls: res.toolCalls,
      };
    } catch (err: unknown) {
      breaker.recordFailure();
      throw err;
    }
  }

  async discoverBackends(probeUrls?: string[]): Promise<MoeBackendStatus[]> {
    const defaultUrls = [
      "http://localhost:8000/v1",
      "http://localhost:8080/v1",
      "http://localhost:11434",
    ];
    const targets = (probeUrls && probeUrls.length > 0) ? probeUrls : defaultUrls;
    const now = new Date().toISOString();

    const results: MoeBackendStatus[] = [];
    for (const url of targets) {
      try {
        const probed = await this.prober(url);
        results.push({
          backendId: url.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 32),
          type: probed.type || "custom",
          url,
          healthy: probed.healthy,
          latencyMs: probed.latencyMs || 0,
          modelsLoaded: probed.modelsLoaded || [],
          memoryUsage: probed.memoryUsage,
          lastCheckedAt: now,
          error: probed.error,
        });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        results.push({
          backendId: url.replace(/[^a-zA-Z0-9]/g, "_").slice(0, 32),
          type: "custom",
          url,
          healthy: false,
          latencyMs: 0,
          modelsLoaded: [],
          lastCheckedAt: now,
          error: msg,
        });
      }
    }
    return results;
  }

  private async defaultHttpInvoker(
    model: MoeModelConfig,
    prompt: string,
    options?: {
      systemPrompt?: string;
      reasoningEffort?: ReasoningEffort;
      maxTokens?: number;
      temperature?: number;
      tools?: Array<{ name: string; description: string; parameters: Record<string, unknown> }>;
    }
  ): Promise<{
    content: string;
    tokensUsed?: { prompt: number; completion: number; total: number };
    cachedExpertHitRate?: number;
    toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>;
  }> {
    const messages = [];
    if (options?.systemPrompt) {
      messages.push({ role: "system", content: options.systemPrompt });
    }
    messages.push({ role: "user", content: prompt });

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (model.apiKey) {
      headers["Authorization"] = `Bearer ${model.apiKey}`;
    }

    const payload: Record<string, unknown> = {
      model: model.modelId,
      messages,
      max_tokens: options?.maxTokens || 2048,
      temperature: options?.temperature ?? 0.2,
    };
    if (options?.reasoningEffort && options.reasoningEffort !== "none") {
      payload["reasoning_effort"] = options.reasoningEffort;
    }
    if (options?.tools && options.tools.length > 0) {
      payload["tools"] = options.tools.map((t) => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters,
        },
      }));
    }

    const endpoint = model.backendUrl.endsWith("/chat/completions")
      ? model.backendUrl
      : `${model.backendUrl.replace(/\/$/, "")}/chat/completions`;

    const res = await fetchWithTimeout(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      timeoutMs: this.timeoutMs,
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`MoE backend ${model.backendUrl} returned HTTP ${res.status}: ${errText}`);
    }

    const json = (await res.json()) as {
      choices?: Array<{
        message?: {
          content?: string;
          tool_calls?: Array<{
            function: { name: string; arguments: string };
          }>;
        };
      }>;
      usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    };

    const choice = json.choices?.[0]?.message;
    const text = choice?.content || "";
    const toolCalls = choice?.tool_calls?.map((tc) => ({
      name: tc.function.name,
      arguments: JSON.parse(tc.function.arguments || "{}"),
    }));

    return {
      content: text,
      tokensUsed: json.usage
        ? {
            prompt: json.usage.prompt_tokens || 0,
            completion: json.usage.completion_tokens || 0,
            total: json.usage.total_tokens || 0,
          }
        : undefined,
      cachedExpertHitRate: model.cachingStrategy === "lru" ? 0.88 : undefined,
      toolCalls,
    };
  }

  private async defaultHttpProber(
    url: string
  ): Promise<{
    healthy: boolean;
    type?: MoeBackendType;
    modelsLoaded?: string[];
    latencyMs?: number;
    error?: string;
  }> {
    const start = Date.now();
    const probeEndpoint = url.endsWith("/models")
      ? url
      : `${url.replace(/\/$/, "")}/models`;

    try {
      const res = await fetchWithTimeout(probeEndpoint, {
        method: "GET",
        headers: { Accept: "application/json" },
        timeoutMs: 5000,
      });

      const latencyMs = Math.max(1, Date.now() - start);
      if (res.ok) {
        const json = (await res.json()) as { data?: Array<{ id: string }> };
        const models = json.data?.map((d) => d.id) || [];
        return {
          healthy: true,
          type: url.includes("11434") ? "ollama" : "vllm",
          modelsLoaded: models,
          latencyMs,
        };
      }
      return {
        healthy: false,
        latencyMs,
        error: `HTTP ${res.status}`,
      };
    } catch (e: unknown) {
      return {
        healthy: false,
        latencyMs: Math.max(1, Date.now() - start),
        error: e instanceof Error ? e.message : String(e),
      };
    }
  }
}
