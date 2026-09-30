import type { ISdk } from "iii-sdk";
import type {
  FastInferenceChannel,
  FastInferenceRouteRequest,
  FastInferenceRouteResponse,
  FastInferenceBenchmarkResult,
  StateKV,
} from "../types.js";
import { KV } from "../state/schema.js";
import { FastInferenceRouter } from "../providers/fast-inference.js";
import { recordAudit } from "./audit.js";
import { logger } from "../logger.js";

let globalRouter: FastInferenceRouter | null = null;

export function getFastInferenceRouter(): FastInferenceRouter {
  if (!globalRouter) {
    globalRouter = new FastInferenceRouter();
  }
  return globalRouter;
}

export function setFastInferenceRouter(router: FastInferenceRouter): void {
  globalRouter = router;
}

export function registerFastInferenceFunctions(sdk: ISdk, kv: StateKV): void {
  const router = getFastInferenceRouter();

  sdk.registerFunction(
    "mem::fast-inference-route",
    async (data: {
      prompt: string;
      systemPrompt?: string;
      maxTokens?: number;
      temperature?: number;
      preferredModel?: string;
      strategy?: "lowest-latency" | "fallback-chain" | "cost-optimized";
    }) => {
      if (!data || typeof data.prompt !== "string") {
        throw new Error("prompt is required");
      }
      if (!data.prompt.trim()) {
        throw new Error("prompt cannot be empty");
      }

      const res = await router.route({
        prompt: data.prompt,
        systemPrompt: data.systemPrompt,
        maxTokens: data.maxTokens,
        temperature: data.temperature,
        preferredModel: data.preferredModel,
        strategy: data.strategy,
      });

      // Record audit
      await recordAudit(kv, "fast_inference_route", {
        channelId: res.channelId,
        latencyMs: res.latencyMs,
        failoverCount: res.failoverCount,
        model: res.model,
      }).catch((e) => logger.warn(`Failed to record fast inference audit: ${e}`));

      return {
        success: true,
        ...res,
      };
    }
  );

  sdk.registerFunction(
    "mem::fast-inference-channels",
    async (_data: Record<string, unknown> = {}) => {
      const channels = router.getChannels();
      return {
        success: true,
        channels,
      };
    }
  );

  sdk.registerFunction(
    "mem::fast-inference-benchmark",
    async (data: { channelId?: string } = {}) => {
      const results = await router.benchmark(data.channelId);

      // Persist latest benchmark snapshot into KV
      await kv.set(KV.fastInference, "latest_benchmark", {
        timestamp: new Date().toISOString(),
        results,
      }).catch((e) => logger.warn(`Failed to save benchmark state: ${e}`));

      return {
        success: true,
        results,
      };
    }
  );

  sdk.registerFunction(
    "mem::fast-inference-configure",
    async (data: {
      channelId: string;
      enabled?: boolean;
      priority?: number;
      latencyMs?: number;
      endpoint?: string;
      model?: string;
      apiKey?: string;
    }) => {
      if (!data || typeof data.channelId !== "string" || !data.channelId.trim()) {
        throw new Error("channelId is required");
      }

      const patch: Partial<FastInferenceChannel> = {};
      if (typeof data.enabled === "boolean") patch.enabled = data.enabled;
      if (typeof data.priority === "number") patch.priority = data.priority;
      if (typeof data.latencyMs === "number") patch.latencyMs = data.latencyMs;
      if (typeof data.endpoint === "string") patch.endpoint = data.endpoint;
      if (typeof data.model === "string") patch.model = data.model;
      if (typeof data.apiKey === "string") patch.apiKey = data.apiKey;

      const updated = router.updateChannel(data.channelId, patch);
      if (!updated) {
        throw new Error(`Channel ${data.channelId} not found`);
      }

      await recordAudit(kv, "fast_inference_configure", {
        channelId: data.channelId,
        patch,
      }).catch((e) => logger.warn(`Failed to record fast inference config audit: ${e}`));

      return {
        success: true,
        channel: updated,
      };
    }
  );
}
