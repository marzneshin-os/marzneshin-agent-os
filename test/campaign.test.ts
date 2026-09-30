import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../src/logger.js", () => ({
  logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

import { registerCampaignFunctions } from "../src/functions/campaign.js";
import { KV } from "../src/state/schema.js";

function mockKV() {
  const store = new Map<string, Map<string, unknown>>();
  return {
    get: async <T>(scope: string, key: string): Promise<T | null> => {
      return (store.get(scope)?.get(key) as T) ?? null;
    },
    set: async <T>(scope: string, key: string, data: T): Promise<T> => {
      if (!store.has(scope)) store.set(scope, new Map());
      store.get(scope)!.set(key, data);
      return data;
    },
    delete: async (scope: string, key: string): Promise<void> => {
      store.get(scope)?.delete(key);
    },
    list: async <T>(scope: string): Promise<T[]> => {
      const entries = store.get(scope);
      return entries ? (Array.from(entries.values()) as T[]) : [];
    },
  };
}

function mockSdk() {
  const functions = new Map<string, Function>();
  return {
    registerFunction: (idOrOpts: string | { id: string }, handler: Function) => {
      const id = typeof idOrOpts === "string" ? idOrOpts : idOrOpts.id;
      functions.set(id, handler);
    },
    registerTrigger: () => {},
    trigger: async (idOrInput: string | { function_id: string; payload: unknown }, data?: unknown) => {
      const id = typeof idOrInput === "string" ? idOrInput : idOrInput.function_id;
      const payload = typeof idOrInput === "string" ? data : idOrInput.payload;
      const fn = functions.get(id);
      if (!fn) throw new Error(`No function: ${id}`);
      return fn(payload);
    },
  };
}

describe("Campaign Functions", () => {
  let sdk: ReturnType<typeof mockSdk>;
  let kv: ReturnType<typeof mockKV>;

  beforeEach(() => {
    sdk = mockSdk();
    kv = mockKV();
    // mock mem::graph-link so graph linking succeeds
    sdk.registerFunction("mem::graph-link", async (data: unknown) => {
      return { success: true, edgeId: "edge-mock", data };
    });
    registerCampaignFunctions(sdk as any, kv as any);
  });

  it("orchestrates a complete campaign with 3 tiers and lineage", async () => {
    const res = await sdk.trigger("mem::campaign-orchestrate", {
      name: "SaaS Launch",
      description: "Automated agent OS release",
      assetRef: "assets/logo.png",
      project: "marzneshin",
      prompt: "Launch a campaign for this product",
    }) as any;

    expect(res.success).toBe(true);
    expect(res.campaign).toBeDefined();
    expect(res.campaign.id).toMatch(/^cmp_/);
    expect(res.campaign.status).toBe("ready");
    expect(res.campaign.insights.length).toBeGreaterThan(0);
    expect(res.campaign.strategies.length).toBeGreaterThan(0);
    expect(res.campaign.creatives.length).toBeGreaterThan(0);

    // Verify lineage links exist
    const strategy = res.campaign.strategies[0];
    expect(strategy.inspiredByInsightIds.length).toBeGreaterThan(0);
    const creative = res.campaign.creatives[0];
    expect(creative.generatedFromStrategyIds.length).toBeGreaterThan(0);

    // Verify stored in KV
    const stored = await kv.get(KV.campaigns, res.campaign.id);
    expect(stored).toEqual(res.campaign);
  });

  it("retrieves a campaign by ID", async () => {
    const created = await sdk.trigger("mem::campaign-orchestrate", {
      name: "Test Campaign",
    }) as any;

    const res = await sdk.trigger("mem::campaign-get", { id: created.campaign.id }) as any;
    expect(res.success).toBe(true);
    expect(res.campaign.name).toBe("Test Campaign");

    const notFound = await sdk.trigger("mem::campaign-get", { id: "cmp-nonexistent" }) as any;
    expect(notFound.success).toBe(false);
  });

  it("lists campaigns with optional project filtering", async () => {
    await sdk.trigger("mem::campaign-orchestrate", { name: "Camp 1", project: "proj-a" });
    await sdk.trigger("mem::campaign-orchestrate", { name: "Camp 2", project: "proj-b" });
    await sdk.trigger("mem::campaign-orchestrate", { name: "Camp 3", project: "proj-a" });

    const all = await sdk.trigger("mem::campaign-list", {}) as any;
    expect(all.success).toBe(true);
    expect(all.campaigns.length).toBe(3);

    const filtered = await sdk.trigger("mem::campaign-list", { project: "proj-a" }) as any;
    expect(filtered.success).toBe(true);
    expect(filtered.campaigns.length).toBe(2);
  });

  it("prepares a structured canvas payload for the viewer", async () => {
    const created = await sdk.trigger("mem::campaign-orchestrate", {
      name: "Visual Canvas Test",
    }) as any;

    const res = await sdk.trigger("mem::campaign-canvas", { id: created.campaign.id }) as any;
    expect(res.success).toBe(true);
    expect(res.canvas).toBeDefined();
    expect(res.canvas.columns.insights).toBeDefined();
    expect(res.canvas.columns.strategies).toBeDefined();
    expect(res.canvas.columns.creatives).toBeDefined();
    expect(res.canvas.links.length).toBeGreaterThan(0);
  });

  it("validates required input fields", async () => {
    const res = await sdk.trigger("mem::campaign-orchestrate", {}) as any;
    expect(res.success).toBe(false);
    expect(res.error).toMatch(/name is required/i);
  });
});
