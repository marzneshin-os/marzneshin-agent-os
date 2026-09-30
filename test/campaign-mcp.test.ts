import { describe, it, expect, beforeEach } from "vitest";
import { getAllTools } from "../src/mcp/tools-registry.js";
import { registerMcpEndpoints } from "../src/mcp/server.js";

function mockSdk() {
  const functions = new Map<string, Function>();
  return {
    registerFunction: (id: string, handler: Function) => {
      functions.set(id, handler);
    },
    registerTrigger: () => {},
    trigger: async (opts: { function_id: string; payload: any }) => {
      if (opts.function_id === "mem::campaign-orchestrate") {
        return { success: true, campaign: { id: "cmp-mcp", name: opts.payload.name } };
      }
      if (opts.function_id === "mem::campaign-get") {
        return { success: true, campaign: { id: opts.payload.id } };
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
  };
}

describe("Campaign MCP Tools", () => {
  let sdk: ReturnType<typeof mockSdk>;

  beforeEach(() => {
    sdk = mockSdk();
    registerMcpEndpoints(sdk as any, {} as any);
  });

  it("registers 4 campaign tools in getAllTools()", () => {
    const tools = getAllTools();
    const names = tools.map((t) => t.name);
    expect(names).toContain("memory_campaign_create");
    expect(names).toContain("memory_campaign_get");
    expect(names).toContain("memory_campaign_list");
    expect(names).toContain("memory_campaign_canvas");
  });

  it("handles memory_campaign_create via mcp::tools::call", async () => {
    const handler = sdk.getFunction("mcp::tools::call");
    expect(handler).toBeDefined();

    const missingName = await handler!({
      body: {
        name: "memory_campaign_create",
        arguments: {},
      },
    });
    expect(missingName.status_code).toBe(400);

    const res = await handler!({
      body: {
        name: "memory_campaign_create",
        arguments: { name: "Agent Launch", prompt: "Create campaign" },
      },
    });
    expect(res.status_code).toBe(200);
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.success).toBe(true);
    expect(parsed.campaign.id).toBe("cmp-mcp");
  });

  it("handles memory_campaign_canvas via mcp::tools::call", async () => {
    const handler = sdk.getFunction("mcp::tools::call");
    const res = await handler!({
      body: {
        name: "memory_campaign_canvas",
        arguments: { id: "cmp-mcp" },
      },
    });
    expect(res.status_code).toBe(200);
    const parsed = JSON.parse(res.body.content[0].text);
    expect(parsed.canvas.id).toBe("cmp-mcp");
  });
});
