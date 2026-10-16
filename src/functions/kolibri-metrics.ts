import type { ISdk } from "iii-sdk";
import type {
  MoeModelConfig,
  MoeBackendStatus,
  MoeMetricsSummary,
  StateKV,
} from "../types.js";
import { KV } from "../state/schema.js";
import { logger } from "../logger.js";

export function registerKolibriMetricsFunction(sdk: ISdk, kv: StateKV): void {
  sdk.registerFunction(
    "mem::kolibri-metrics",
    async (data?: {
      action?: "get" | "list" | "reset";
      modelId?: string;
    }) => {
      const action = data?.action || "list";

      switch (action) {
        case "get": {
          if (!data?.modelId) {
            throw new Error("modelId is required for metrics get");
          }
          const metricKey = `metric_${data.modelId}`;
          return await kv.get<MoeMetricsSummary>(KV.moeMetrics, metricKey);
        }

        case "list": {
          const list = await kv.list<MoeMetricsSummary>(KV.moeMetrics);
          return list || [];
        }

        case "reset": {
          if (!data?.modelId) {
            throw new Error("modelId is required for metrics reset");
          }
          const metricKey = `metric_${data.modelId}`;
          await kv.delete(KV.moeMetrics, metricKey);
          return { success: true, reset: data.modelId };
        }
      }
    }
  );

  sdk.registerFunction(
    "mem::kolibri-status",
    async () => {
      const models = (await kv.list<MoeModelConfig>(KV.moeModels)) || [];
      const backends = (await kv.list<MoeBackendStatus>(KV.moeBackends)) || [];
      const metrics = (await kv.list<MoeMetricsSummary>(KV.moeMetrics)) || [];

      const healthyBackends = backends.filter((b) => b.healthy);
      const totalRequests = metrics.reduce((acc, m) => acc + (m.totalRequests || 0), 0);
      const totalTokens = metrics.reduce((acc, m) => acc + (m.totalTokens || 0), 0);

      return {
        success: true,
        runtime: "agentmemory-kolibri-v1",
        timestamp: new Date().toISOString(),
        modelsCount: models.length,
        backendsCount: backends.length,
        healthyBackendsCount: healthyBackends.length,
        totalInferenceRequests: totalRequests,
        totalTokensGenerated: totalTokens,
        models: models.map((m) => ({
          modelId: m.modelId,
          displayName: m.displayName,
          backend: m.backend,
          quantFormat: m.quantFormat,
          expertCount: m.expertCount,
          activeExperts: m.activeExperts,
        })),
        backends: backends.map((b) => ({
          backendId: b.backendId,
          type: b.type,
          url: b.url,
          healthy: b.healthy,
          latencyMs: b.latencyMs,
          modelsLoaded: b.modelsLoaded,
        })),
      };
    }
  );
}
