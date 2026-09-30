import { describe, it, expect, beforeEach } from "vitest";
import { registerApiTriggers } from "../src/triggers/api.js";

function mockSdk() {
  const functions = new Map<string, Function>();
  const triggers: any[] = [];
  return {
    registerFunction: (id: string, handler: Function) => {
      functions.set(id, handler);
    },
    registerTrigger: (trigger: any) => {
      triggers.push(trigger);
    },
    trigger: async (opts: { function_id: string; payload: any }) => {
      if (opts.function_id === "mem::campaign-orchestrate") {
        return { success: true, campaign: { id: "cmp-123", name: opts.payload.name } };
      }
      if (opts.function_id === "mem::campaign-get") {
        return { success: true, campaign: { id: opts.payload.id, name: "Test" } };
      }
      if (opts.function_id === "mem::campaign-list") {
        return { success: true, campaigns: [{ id: "cmp-1" }], total: 1 };
      }
      if (opts.function_id === "mem::campaign-canvas") {
        return { success: true, canvas: { id: opts.payload.id, columns: {} } };
      }
      return { success: true };
    },
    getFunction: (id: string) => functions.get(id),
    triggers,
  };
}

describe("Campaign REST Endpoints", () => {
  let sdk: ReturnType<typeof mockSdk>;
  const secret = "test-secret";

  beforeEach(() => {
    sdk = mockSdk();
    registerApiTriggers(sdk as any, {} as any, secret);
  });

  it("registers campaign routes in HTTP triggers", () => {
    const paths = sdk.triggers.map((t) => t.config?.api_path);
    expect(paths).toContain("/agentmemory/campaigns/create");
    expect(paths).toContain("/agentmemory/campaigns/get");
    expect(paths).toContain("/agentmemory/campaigns/list");
    expect(paths).toContain("/agentmemory/campaigns/canvas");
  });

  it("enforces authentication on campaign create", async () => {
    const fn = sdk.getFunction("api::campaign-create");
    expect(fn).toBeDefined();

    const unauth = await fn!({ headers: {}, body: { name: "Test" } });
    expect(unauth.status_code).toBe(401);

    const auth = await fn!({
      headers: { authorization: "Bearer test-secret" },
      body: { name: "Launch Agent" },
    });
    expect(auth.status_code).toBe(200);
    expect(auth.body.success).toBe(true);
  });

  it("handles campaign retrieval via GET query params", async () => {
    const fn = sdk.getFunction("api::campaign-get");
    expect(fn).toBeDefined();

    const missing = await fn!({
      headers: { authorization: "Bearer test-secret" },
      query_params: {},
    });
    expect(missing.status_code).toBe(400);

    const valid = await fn!({
      headers: { authorization: "Bearer test-secret" },
      query_params: { id: "cmp-123" },
    });
    expect(valid.status_code).toBe(200);
    expect(valid.body.campaign.id).toBe("cmp-123");
  });

  it("handles campaign canvas retrieval", async () => {
    const fn = sdk.getFunction("api::campaign-canvas");
    expect(fn).toBeDefined();

    const valid = await fn!({
      headers: { authorization: "Bearer test-secret" },
      query_params: { id: "cmp-123" },
    });
    expect(valid.status_code).toBe(200);
    expect(valid.body.canvas.id).toBe("cmp-123");
  });
});
