import { describe, expect, it } from "vitest";
import { getAllTools } from "../src/mcp/tools-registry.js";
import { registerMcpEndpoints } from "../src/mcp/server.js";

function createSdk() {
  const functions = new Map<string, Function>();
  const calls: Array<{ function_id: string; payload: unknown }> = [];
  const sdk = {
    registerFunction: (id: string, handler: Function) => functions.set(id, handler),
    registerTrigger: () => {},
    trigger: async (call: { function_id: string; payload: unknown }) => {
      calls.push(call);
      return { success: true, decision: "allow" };
    },
  };
  return { sdk, functions, calls };
}

const guardContract = {
  enforcement: "enforce",
  allowedPaths: ["src"],
  acceptanceCriteria: [
    { id: "tests", description: "Tests pass", validatorId: "unit" },
  ],
  validators: [{ id: "unit", command: "npm test" }],
};

describe("Gravitas MCP action integration", () => {
  it("publishes the action guard contract as a nested object schema", () => {
    const actionCreate = getAllTools().find((tool) => tool.name === "memory_action_create");
    expect(actionCreate?.inputSchema.properties.guardContract).toMatchObject({
      type: "object",
      properties: {
        enforcement: { type: "string", enum: ["audit", "enforce"] },
        allowedPaths: { type: "array", items: { type: "string" } },
      },
    });
  });

  it("forwards only a validated guard contract when creating an action", async () => {
    const { sdk, functions, calls } = createSdk();
    registerMcpEndpoints(sdk as never, {} as never);
    const handler = functions.get("mcp::tools::call")!;
    const response = await handler({
      body: {
        name: "memory_action_create",
        arguments: { title: "Guarded work", guardContract, admin: true },
      },
    });
    expect(response.status_code).toBe(200);
    expect(calls).toEqual([
      {
        function_id: "mem::action-create",
        payload: {
          title: "Guarded work",
          description: undefined,
          priority: undefined,
          project: undefined,
          tags: [],
          parentId: undefined,
          edges: undefined,
          guardContract,
        },
      },
    ]);
  });

  it("rejects an invalid action guard contract before creating an action", async () => {
    const { sdk, functions, calls } = createSdk();
    registerMcpEndpoints(sdk as never, {} as never);
    const response = await functions.get("mcp::tools::call")!({
      body: {
        name: "memory_action_create",
        arguments: { title: "Bad guarded work", guardContract: { enforcement: "all" } },
      },
    });
    expect(response.status_code).toBe(400);
    expect(calls).toHaveLength(0);
  });

  it("dispatches isolated action-update rearming to the guard and rejects mixed updates", async () => {
    const { sdk, functions, calls } = createSdk();
    registerMcpEndpoints(sdk as never, {} as never);
    const handler = functions.get("mcp::tools::call")!;
    const rearmFailure = {
      conversationId: "conv-1",
      workspaceRoot: "/workspace/project",
      callHash: "a".repeat(64),
      diagnosis: "The source import was wrong",
      strategyFingerprint: "b".repeat(64),
      nextArgumentHash: "c".repeat(64),
    };
    const mixed = await handler({
      body: {
        name: "memory_action_update",
        arguments: { actionId: "act-1", status: "done", rearmFailure },
      },
    });
    expect(mixed.status_code).toBe(400);
    expect(calls).toHaveLength(0);

    const accepted = await handler({
      body: {
        name: "memory_action_update",
        arguments: { actionId: "act-1", rearmFailure },
      },
    });
    expect(accepted.status_code).toBe(200);
    expect(calls).toEqual([
      {
        function_id: "mem::gravitas-guard",
        payload: {
          operation: "rearm_failure",
          actionId: "act-1",
          ...rearmFailure,
        },
      },
    ]);
  });
});
