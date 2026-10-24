import { describe, it, expect, beforeEach } from "vitest";

import { registerGravitasGuardFunction, hashGuardValue } from "../src/functions/gravitas-guard.js";
import { KV } from "../src/state/schema.js";
import type { Action } from "../src/types.js";
import { mockKV, mockSdk } from "./helpers/mocks.js";

const contract = {
  enforcement: "enforce" as const,
  allowedPaths: ["src"],
  acceptanceCriteria: [{ id: "tests-pass", description: "Tests pass", validatorId: "tests" }],
  validators: [{ id: "tests", command: "npm test" }],
};
const workspaceRoot = "C:\\workspace\\project";

function bindPayload() {
  return {
    operation: "bind",
    actionId: "act_guarded",
    conversationId: "conversation-1",
    workspaceRoots: [workspaceRoot],
    enforcement: "enforce",
  };
}

function makeAction(id: string): Action {
  return {
    id,
    title: "Guarded action",
    description: "",
    status: "active",
    priority: 5,
    createdAt: new Date(0).toISOString(),
    updatedAt: new Date(0).toISOString(),
    createdBy: "test",
    tags: [],
    sourceObservationIds: [],
    sourceMemoryIds: [],
    guardContract: contract,
  };
}

describe("Gravitas guard", () => {
  let sdk: ReturnType<typeof mockSdk>;
  let kv: ReturnType<typeof mockKV>;

  beforeEach(async () => {
    sdk = mockSdk();
    kv = mockKV();
    registerGravitasGuardFunction(sdk as never, kv as never);
    await kv.set(KV.actions, "act_guarded", makeAction("act_guarded"));
  });

  it("binds once and enforces scope and read-before-write", async () => {
    const bind = (await sdk.trigger("mem::gravitas-guard", bindPayload())) as { success: boolean };
    expect(bind.success).toBe(true);

    const outOfScope = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "../secrets.txt",
      currentFileHash: null,
      argumentHash: "a".repeat(64),
      strategyFingerprint: hashGuardValue("s1"),
      isWrite: true,
      stepIndex: 0,
    })) as { decision: string; reason: string };
    expect(outOfScope.decision).toBe("deny");
    expect(outOfScope.reason).toContain("workspace-relative");

    const unread = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/file.ts",
      currentFileHash: "f".repeat(64),
      argumentHash: "b".repeat(64),
      strategyFingerprint: hashGuardValue("s1"),
      isWrite: true,
      stepIndex: 1,
    })) as { decision: string };
    expect(unread.decision).toBe("deny");

    const readEvent = {
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "c".repeat(64),
      stepIndex: 2,
    };
    await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...readEvent,
      currentFileHash: "f".repeat(64),
      isFullFileRead: true,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      ...readEvent,
      success: true,
      isFullFileRead: true,
      fileHash: "f".repeat(64),
    });

    const write = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/file.ts",
      currentFileHash: "f".repeat(64),
      argumentHash: "d".repeat(64),
      strategyFingerprint: hashGuardValue("s1"),
      isWrite: true,
      stepIndex: 3,
    })) as { decision: string };
    expect(write.decision).toBe("allow");

    const persisted = await kv.get<Record<string, unknown>>(KV.gravitasGuard, "act_guarded");
    expect(persisted?.workspaceRootHash).toBe(hashGuardValue("c:/workspace/project"));
    expect(persisted?.workspaceRoot).toBeUndefined();
  });

  it("rejects ambiguous roots and a changed root after binding", async () => {
    const ambiguous = (await sdk.trigger("mem::gravitas-guard", {
      ...bindPayload(),
      workspaceRoots: [workspaceRoot, "C:\\workspace\\other"],
    })) as { decision: string };
    expect(ambiguous.decision).toBe("deny");

    const modeMismatch = (await sdk.trigger("mem::gravitas-guard", {
      ...bindPayload(),
      enforcement: "audit",
    })) as { decision: string; reason: string };
    expect(modeMismatch.decision).toBe("deny");
    expect(modeMismatch.reason).toContain("does not match");

    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const changedRoot = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot: "C:\\workspace\\other",
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "4".repeat(64),
      stepIndex: 0,
    })) as { decision: string; reason: string };
    expect(changedRoot.decision).toBe("deny");
    expect(changedRoot.reason).toContain("workspace root");
  });

  it("requires diagnosis, a changed strategy, and changed arguments before one retry", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());

    const failedCall = {
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "e".repeat(64),
      strategyFingerprint: hashGuardValue("strategy-old"),
      commandHash: hashGuardValue("npm test"),
      stepIndex: 0,
    };
    const first = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...failedCall,
    })) as { decision: string; callHash: string };
    expect(first.decision).toBe("allow");

    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      ...failedCall,
      success: false,
      statusCode: 1,
    });

    const blocked = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...failedCall,
      stepIndex: 1,
    })) as { decision: string; reason: string };
    expect(blocked.decision).toBe("deny");
    expect(blocked.reason).toContain("re-arm");

    const rearmed = (await sdk.trigger("mem::gravitas-guard", {
      operation: "rearm_failure",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      callHash: first.callHash,
      diagnosis: "The local dependency cache was stale",
      strategyFingerprint: hashGuardValue("strategy-new"),
      nextArgumentHash: hashGuardValue("npm test --reporter dot"),
    })) as { success: boolean };
    expect(rearmed.success).toBe(true);

    const retried = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...failedCall,
      argumentHash: hashGuardValue("npm test --reporter dot"),
      strategyFingerprint: hashGuardValue("strategy-new"),
      stepIndex: 2,
    })) as { decision: string };
    expect(retried.decision).toBe("allow");
  });

  it("allows only declared validators and invalidates evidence after a mutation", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());

    const declaredValidator = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "1".repeat(64),
      strategyFingerprint: hashGuardValue("validator-run"),
      commandHash: hashGuardValue("npm test"),
      stepIndex: 0,
    })) as { decision: string; validatorId?: string };
    expect(declaredValidator.decision).toBe("allow");
    expect(declaredValidator.validatorId).toBe("tests");

    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "1".repeat(64),
      commandHash: hashGuardValue("npm test"),
      success: true,
      statusCode: 0,
      outputHash: "c".repeat(64),
      stepIndex: 0,
    });

    const stop = (await sdk.trigger("mem::gravitas-guard", {
      operation: "stop",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      fullyIdle: true,
      executionNum: 0,
    })) as { decision: string };
    expect(stop.decision).toBe("allow");

    const fresh = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; fullyIdle: boolean; mutationRevision: number };
    expect(fresh.allowed).toBe(true);
    expect(fresh.fullyIdle).toBe(true);

    const nextTool = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/new.ts",
      argumentHash: "9".repeat(64),
      stepIndex: 1,
    })) as { decision: string };
    expect(nextTool.decision).toBe("allow");
    const noLongerIdle = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; fullyIdle: boolean };
    expect(noLongerIdle.allowed).toBe(false);
    expect(noLongerIdle.fullyIdle).toBe(false);

    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/new.ts",
      argumentHash: "9".repeat(64),
      success: true,
      stepIndex: 1,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/new.ts",
      currentFileHash: null,
      argumentHash: "2".repeat(64),
      isWrite: true,
      stepIndex: 2,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/new.ts",
      argumentHash: "2".repeat(64),
      success: true,
      mutated: true,
      stepIndex: 2,
    });

    const stale = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; reason: string; fullyIdle: boolean; mutationRevision: number; missingCriteria: string[] };
    expect(stale.allowed).toBe(false);
    expect(stale.reason).toContain("fully idle");
    expect(stale.fullyIdle).toBe(false);
    expect(stale.mutationRevision).toBe(1);
    expect(stale.missingCriteria).toContain("tests-pass");
  });

  it("deduplicates hook events, rejects stale steps, and fails closed at the event cap", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const event = {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/file.ts",
      argumentHash: "5".repeat(64),
      success: true,
      mutated: true,
      stepIndex: 1,
    };
    const pre = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: event.actionId,
      conversationId: event.conversationId,
      workspaceRoot: event.workspaceRoot,
      toolName: event.toolName,
      relativePath: event.relativePath,
      argumentHash: event.argumentHash,
      stepIndex: event.stepIndex,
      currentFileHash: null,
      isWrite: true,
    })) as { decision: string };
    expect(pre.decision).toBe("allow");
    const first = (await sdk.trigger("mem::gravitas-guard", event)) as { mutationRevision: number };
    const duplicate = (await sdk.trigger("mem::gravitas-guard", event)) as { mutationRevision: number };
    expect(first.mutationRevision).toBe(1);
    expect(duplicate.mutationRevision).toBe(1);

    const stale = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "6".repeat(64),
      stepIndex: 0,
    })) as { decision: string; reason: string };
    expect(stale.decision).toBe("deny");
    expect(stale.reason).toContain("stale");

    const state = await kv.get<Record<string, unknown>>(KV.gravitasGuard, "act_guarded");
    const events = Array.from({ length: 500 }, (_, index) => ({
      eventKey: hashGuardValue(`event-${index}`),
      stepIndex: index,
      phase: "pre_tool",
      toolNameHash: hashGuardValue("view_file"),
      argumentHash: hashGuardValue(`args-${index}`),
      decision: "allow",
      mutationRevision: 1,
    }));
    await kv.set(KV.gravitasGuard, "act_guarded", { ...state, events: events.slice(0, 499), lastStepIndex: 498 });
    const noPostCapacity = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "6".repeat(64),
      stepIndex: 499,
    })) as { decision: string; reason: string };
    expect(noPostCapacity.decision).toBe("deny");
    expect(noPostCapacity.reason).toContain("reserve a post-tool");

    await kv.set(KV.gravitasGuard, "act_guarded", { ...state, events, lastStepIndex: 499 });
    const overflow = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "7".repeat(64),
      stepIndex: 500,
    })) as { decision: string; reason: string };
    expect(overflow.decision).toBe("deny");
    expect(overflow.reason).toContain("capacity");
  });

  it("rejects an undeclared shell command in enforce mode", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const result = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "3".repeat(64),
      commandHash: hashGuardValue("rm -rf ."),
      strategyFingerprint: hashGuardValue("shell"),
      stepIndex: 0,
    })) as { decision: string; reason: string };
    expect(result.decision).toBe("deny");
    expect(result.reason).toContain("declared validator");
  });

  it("does not count persistent or async validator commands and requires explicit Stop idle", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const commandHash = hashGuardValue("npm test");
    const argumentHash = "8".repeat(64);
    const pre = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash,
      commandHash,
      strategyFingerprint: hashGuardValue("async-run"),
      runPersistent: true,
      waitMsBeforeAsync: 1000,
      stepIndex: 0,
    })) as { decision: string; reason: string };
    expect(pre.decision).toBe("deny");
    expect(pre.reason).toContain("asynchronous");

    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash,
      commandHash,
      success: true,
      runPersistent: true,
      waitMsBeforeAsync: 1000,
      stepIndex: 0,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "stop",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      fullyIdle: true,
      executionNum: 0,
    });
    const completion = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; missingCriteria: string[] };
    expect(completion.allowed).toBe(false);
    expect(completion.missingCriteria).toContain("tests-pass");
  });

  it("does not accept validator evidence without a matching pre-tool event", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "9".repeat(64),
      commandHash: hashGuardValue("npm test"),
      success: true,
      stepIndex: 0,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "stop",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      fullyIdle: true,
      executionNum: 0,
    });

    const completion = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; missingCriteria: string[] };
    expect(completion.allowed).toBe(false);
    expect(completion.missingCriteria).toContain("tests-pass");
  });

  it("blocks completion while an allowed tool call is missing its post-tool event", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const validator = {
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "7".repeat(64),
      commandHash: hashGuardValue("npm test"),
      stepIndex: 0,
    };
    await sdk.trigger("mem::gravitas-guard", { operation: "pre_tool", ...validator });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      ...validator,
      success: true,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "stop",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      fullyIdle: true,
      executionNum: 0,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "8".repeat(64),
      stepIndex: 1,
    });
    await sdk.trigger("mem::gravitas-guard", {
      operation: "stop",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      fullyIdle: true,
      executionNum: 1,
    });

    const completion = (await sdk.trigger("mem::gravitas-guard", {
      operation: "completion_check",
      actionId: "act_guarded",
    })) as { allowed: boolean; pendingToolEvents?: number };
    expect(completion.allowed).toBe(false);
    expect(completion.pendingToolEvents).toBe(1);
  });

  it("issues a read receipt only when the file hash is stable across the view call", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const read = {
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "view_file",
      relativePath: "src/file.ts",
      argumentHash: "d".repeat(64),
      stepIndex: 0,
    };
    const pre = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...read,
      currentFileHash: "a".repeat(64),
      isFullFileRead: true,
    })) as { decision: string };
    expect(pre.decision).toBe("allow");
    const post = (await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      ...read,
      success: true,
      isFullFileRead: true,
      fileHash: "b".repeat(64),
    })) as { decision: string };
    expect(post.decision).toBe("allow");

    const write = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "write_to_file",
      relativePath: "src/file.ts",
      currentFileHash: "b".repeat(64),
      argumentHash: "e".repeat(64),
      isWrite: true,
      stepIndex: 1,
    })) as { decision: string; reason?: string };
    expect(write.decision).toBe("deny");
    expect(write.reason).toContain("read before");
  });

  it("rejects a validator whenever WaitMsBeforeAsync is supplied, including zero", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const result = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "a".repeat(64),
      commandHash: hashGuardValue("npm test"),
      waitMsBeforeAsync: 0,
      stepIndex: 0,
    })) as { decision: string; reason?: string };
    expect(result.decision).toBe("deny");
    expect(result.reason).toContain("asynchronous");
  });

  it("does not allow a failure re-arm grant to be overwritten before consumption", async () => {
    await sdk.trigger("mem::gravitas-guard", bindPayload());
    const failedCall = {
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      toolName: "run_command",
      argumentHash: "b".repeat(64),
      strategyFingerprint: hashGuardValue("strategy-old"),
      commandHash: hashGuardValue("npm test"),
      stepIndex: 0,
    };
    const pre = (await sdk.trigger("mem::gravitas-guard", {
      operation: "pre_tool",
      ...failedCall,
    })) as { callHash: string };
    await sdk.trigger("mem::gravitas-guard", {
      operation: "post_tool",
      ...failedCall,
      success: false,
      stepIndex: 0,
    });

    const firstGrant = {
      operation: "rearm_failure",
      actionId: "act_guarded",
      conversationId: "conversation-1",
      workspaceRoot,
      callHash: pre.callHash,
      diagnosis: "Changed test strategy",
      strategyFingerprint: hashGuardValue("strategy-new"),
      nextArgumentHash: hashGuardValue("npm test --reporter dot"),
    };
    const first = (await sdk.trigger("mem::gravitas-guard", firstGrant)) as { decision: string };
    const second = (await sdk.trigger("mem::gravitas-guard", {
      ...firstGrant,
      nextArgumentHash: hashGuardValue("npm test --runInBand"),
    })) as { decision: string; reason?: string };
    expect(first.decision).toBe("allow");
    expect(second.decision).toBe("deny");
    expect(second.reason).toContain("unconsumed");
  });
});
