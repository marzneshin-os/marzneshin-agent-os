import type { ISdk } from "iii-sdk";
import type {
  MoeModelConfig,
  MoeInferenceRequest,
  MoeBackendStatus,
  MoeMetricsSummary,
  StateKV,
} from "../types.js";
import { KV } from "../state/schema.js";
import { MoeInferenceEngine } from "../providers/fast-inference.js";
import { safeAudit } from "./audit.js";
import { logger } from "../logger.js";

let globalMoeEngine: MoeInferenceEngine | null = null;

export function getMoeInferenceEngine(): MoeInferenceEngine {
  if (!globalMoeEngine) {
    globalMoeEngine = new MoeInferenceEngine();
  }
  return globalMoeEngine;
}

export function setMoeInferenceEngine(engine: MoeInferenceEngine): void {
  globalMoeEngine = engine;
}

export function registerKolibriInferenceFunctions(
  sdk: ISdk,
  kv: StateKV,
  customEngine?: MoeInferenceEngine
): void {
  const engine = customEngine || getMoeInferenceEngine();

  sdk.registerFunction(
    "mem::kolibri-discover",
    async (data?: { probeUrls?: string[]; timeout?: number }) => {
      try {
        const statuses = await engine.discoverBackends(data?.probeUrls);
        const now = new Date().toISOString();

        for (const st of statuses) {
          await kv.set(KV.moeBackends, st.backendId, st).catch(() => {});
        }

        return {
          success: true,
          timestamp: now,
          count: statuses.length,
          backends: statuses,
        };
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        logger.error(`Error in mem::kolibri-discover: ${msg}`);
        return {
          success: false,
          error: msg,
          backends: [],
        };
      }
    }
  );

  sdk.registerFunction(
    "mem::kolibri-infer",
    async (data: {
      modelId: string;
      prompt: string;
      systemPrompt?: string;
      reasoningEffort?: "none" | "low" | "medium" | "high";
      maxTokens?: number;
      temperature?: number;
      tools?: Array<{ name: string; description: string; parameters: Record<string, unknown> }>;
    }) => {
      if (!data || typeof data.modelId !== "string" || !data.modelId.trim()) {
        throw new Error("modelId is required");
      }
      if (typeof data.prompt !== "string" || !data.prompt.trim()) {
        throw new Error("prompt cannot be empty");
      }

      const model = await kv.get<MoeModelConfig>(KV.moeModels, data.modelId);
      if (!model) {
        throw new Error(`MoE model not found: ${data.modelId}`);
      }

      const res = await engine.infer(model, {
        modelId: data.modelId,
        prompt: data.prompt,
        systemPrompt: data.systemPrompt,
        reasoningEffort: data.reasoningEffort,
        maxTokens: data.maxTokens,
        temperature: data.temperature,
        tools: data.tools,
      });

      await safeAudit(kv, "kolibri_infer", "mem::kolibri-infer", [data.modelId], {
        backend: res.backend,
        latencyMs: res.latencyMs,
        reasoningEffort: res.reasoningEffort,
        tokensUsed: res.tokensUsed,
      });

      // Update aggregate metrics in KV
      const metricKey = `metric_${data.modelId}`;
      const existing = (await kv.get<MoeMetricsSummary>(KV.moeMetrics, metricKey)) || {
        modelId: data.modelId,
        totalRequests: 0,
        avgLatencyMs: 0,
        totalTokens: 0,
        avgExpertHitRate: 0,
        errorCount: 0,
        lastUpdated: new Date().toISOString(),
      };

      const newTotal = existing.totalRequests + 1;
      const newAvgLatency = Math.round(
        (existing.avgLatencyMs * existing.totalRequests + res.latencyMs) / newTotal
      );
      const newTokens = existing.totalTokens + (res.tokensUsed?.total || 0);
      const newHitRate =
        (existing.avgExpertHitRate * existing.totalRequests +
          (res.cachedExpertHitRate || 0)) /
        newTotal;

      await kv.set(KV.moeMetrics, metricKey, {
        modelId: data.modelId,
        totalRequests: newTotal,
        avgLatencyMs: newAvgLatency,
        totalTokens: newTokens,
        avgExpertHitRate: Number(newHitRate.toFixed(2)),
        errorCount: existing.errorCount,
        lastUpdated: new Date().toISOString(),
      }).catch(() => {});

      return {
        success: true,
        ...res,
      };
    }
  );
}
