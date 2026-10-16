import type { ISdk } from "iii-sdk";
import type { MoeModelConfig, StateKV } from "../types.js";
import { KV } from "../state/schema.js";
import { safeAudit } from "./audit.js";
import { logger } from "../logger.js";

export function validateMoeConfig(config: Partial<MoeModelConfig>): MoeModelConfig {
  if (!config.modelId || typeof config.modelId !== "string") {
    throw new Error("modelId is required and must be a string");
  }
  if (!config.displayName || typeof config.displayName !== "string") {
    throw new Error("displayName is required");
  }
  if (!config.backend || !["vllm", "llamacpp", "colibri", "ollama", "custom"].includes(config.backend)) {
    throw new Error("backend must be one of: vllm, llamacpp, colibri, ollama, custom");
  }
  if (!config.backendUrl || typeof config.backendUrl !== "string") {
    throw new Error("backendUrl is required");
  }

  return {
    modelId: config.modelId.trim(),
    displayName: config.displayName.trim(),
    backend: config.backend,
    backendUrl: config.backendUrl.trim(),
    totalParams: typeof config.totalParams === "number" ? config.totalParams : 0,
    activeParams: typeof config.activeParams === "number" ? config.activeParams : 0,
    expertCount: typeof config.expertCount === "number" ? config.expertCount : 1,
    activeExperts: typeof config.activeExperts === "number" ? config.activeExperts : 1,
    quantFormat: config.quantFormat || "fp8",
    contextWindow: typeof config.contextWindow === "number" ? config.contextWindow : 4096,
    maxContextWindow: typeof config.maxContextWindow === "number" ? config.maxContextWindow : 32768,
    slidingWindowSize: config.slidingWindowSize,
    slidingWindowRatio: config.slidingWindowRatio,
    reasoningEffortLevels: Array.isArray(config.reasoningEffortLevels) ? config.reasoningEffortLevels : ["none"],
    cachingStrategy: config.cachingStrategy || "lru",
    memoryTier: config.memoryTier || "auto",
    toolCallingSupport: Boolean(config.toolCallingSupport),
    hermesFunctionCalling: Boolean(config.hermesFunctionCalling),
    apiKey: config.apiKey,
    createdAt: config.createdAt,
    updatedAt: config.updatedAt,
  };
}

export function registerKolibriConfigFunction(sdk: ISdk, kv: StateKV): void {
  sdk.registerFunction(
    "mem::kolibri-config",
    async (data: {
      action: "set" | "get" | "list" | "delete";
      modelId?: string;
      config?: Partial<MoeModelConfig>;
    }) => {
      if (!data || !["set", "get", "list", "delete"].includes(data.action)) {
        throw new Error("Valid action is required: set, get, list, delete");
      }

      const now = new Date().toISOString();

      switch (data.action) {
        case "set": {
          if (!data.modelId || !data.config) {
            throw new Error("modelId and config required for set action");
          }
          const validated = validateMoeConfig({
            ...data.config,
            modelId: data.modelId,
          });

          const existing = await kv.get<MoeModelConfig>(KV.moeModels, data.modelId);
          const toSave: MoeModelConfig = {
            ...validated,
            createdAt: existing?.createdAt || now,
            updatedAt: now,
          };

          await kv.set(KV.moeModels, data.modelId, toSave);

          await safeAudit(kv, "kolibri_configure", "mem::kolibri-config", [data.modelId], {
            action: "set",
            backend: validated.backend,
            quantFormat: validated.quantFormat,
          });

          return { success: true, modelId: data.modelId };
        }

        case "get": {
          if (!data.modelId) {
            throw new Error("modelId is required for get action");
          }
          return await kv.get<MoeModelConfig>(KV.moeModels, data.modelId);
        }

        case "list": {
          const list = await kv.list<MoeModelConfig>(KV.moeModels);
          return list || [];
        }

        case "delete": {
          if (!data.modelId) {
            throw new Error("modelId is required for delete action");
          }
          await kv.delete(KV.moeModels, data.modelId);

          await safeAudit(kv, "kolibri_configure", "mem::kolibri-config", [data.modelId], {
            action: "delete",
          });

          return { success: true, deleted: data.modelId };
        }
      }
    }
  );
}
