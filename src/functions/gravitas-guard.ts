import { createHash } from "node:crypto";
import { posix as posixPath, win32 as win32Path } from "node:path";
import type { ISdk } from "iii-sdk";
import type { StateKV } from "../state/kv.js";
import { KV } from "../state/schema.js";
import { withKeyedLock } from "../state/keyed-mutex.js";
import type {
  Action,
  ActionGuardContract,
  GravitasFailedCall,
  GravitasGuardEvent,
  GravitasGuardState,
  GravitasReadReceipt,
  GravitasValidatorEvidence,
} from "../types.js";
import { recordAudit } from "./audit.js";

const HASH_PATTERN = /^[a-f0-9]{64}$/i;
const MAX_READS = 100;
const MAX_EVIDENCE = 100;
const MAX_EVENTS = 500;
const MAX_FAILURES = MAX_EVENTS;

export type GravitasGuardOperation =
  | { operation: "bind"; actionId: string; conversationId: string; workspaceRoots: string[]; enforcement: "audit" | "enforce" }
  | {
      operation: "pre_tool";
      actionId: string;
      conversationId: string;
      workspaceRoot: string;
      toolName: string;
      relativePath?: string;
      currentFileHash?: string | null;
      isFullFileRead?: boolean;
      argumentHash: string;
      strategyFingerprint?: string;
      commandHash?: string;
      isWrite?: boolean;
      runPersistent?: boolean;
      waitMsBeforeAsync?: number;
      stepIndex: number;
    }
  | {
      operation: "post_tool";
      actionId: string;
      conversationId: string;
      workspaceRoot: string;
      toolName: string;
      relativePath?: string;
      argumentHash: string;
      success: boolean;
      strategyFingerprint?: string;
      commandHash?: string;
      isFullFileRead?: boolean;
      fileHash?: string;
      mutated?: boolean;
      runPersistent?: boolean;
      waitMsBeforeAsync?: number;
      outputHash?: string;
      statusCode?: number;
      stepIndex: number;
    }
  | {
      operation: "rearm_failure";
      actionId: string;
      conversationId: string;
      workspaceRoot: string;
      callHash: string;
      diagnosis: string;
      strategyFingerprint: string;
      nextArgumentHash: string;
    }
  | {
      operation: "stop";
      actionId: string;
      conversationId: string;
      workspaceRoot: string;
      fullyIdle: boolean;
      executionNum: number;
    }
  | { operation: "completion_check"; actionId: string };

export interface GuardDecision {
  success: boolean;
  decision: "allow" | "deny";
  reason?: string;
  validatorId?: string;
  callHash?: string;
  mutationRevision?: number;
}

export interface CompletionCheckResult {
  success: boolean;
  allowed: boolean;
  reason?: string;
  mutationRevision: number;
  fullyIdle: boolean;
  missingCriteria: string[];
  pendingToolEvents: number;
}

export type GuardContractValidation =
  | { valid: true; contract: ActionGuardContract }
  | { valid: false; error: string };

export function hashGuardValue(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function contractFingerprint(contract: ActionGuardContract): string {
  return hashGuardValue(JSON.stringify(contract));
}

export function validateActionGuardContract(value: unknown): GuardContractValidation {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { valid: false, error: "guardContract must be an object" };
  }
  const candidate = value as Record<string, unknown>;
  if (candidate.enforcement !== "audit" && candidate.enforcement !== "enforce") {
    return { valid: false, error: "guardContract.enforcement must be audit or enforce" };
  }
  if (!Array.isArray(candidate.allowedPaths) || candidate.allowedPaths.length > 100) {
    return { valid: false, error: "guardContract.allowedPaths must be an array of at most 100 paths" };
  }
  const allowedPaths: string[] = [];
  for (const value of candidate.allowedPaths) {
    if (typeof value !== "string" || value.length > 240) {
      return { valid: false, error: "guardContract.allowedPaths contains an invalid path" };
    }
    const normalized = normalizeRelativePath(value);
    if (!normalized || normalized.includes("*") || allowedPaths.includes(normalized)) {
      return { valid: false, error: "guardContract.allowedPaths must contain unique workspace-relative paths without wildcards" };
    }
    allowedPaths.push(normalized);
  }
  if (!Array.isArray(candidate.validators) || candidate.validators.length > 100) {
    return { valid: false, error: "guardContract.validators must be an array of at most 100 validators" };
  }
  const validators: ActionGuardContract["validators"] = [];
  const validatorIds = new Set<string>();
  for (const value of candidate.validators) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { valid: false, error: "guardContract.validators contains an invalid validator" };
    }
    const validator = value as Record<string, unknown>;
    if (
      typeof validator.id !== "string" ||
      !isIdentifier(validator.id) ||
      validatorIds.has(validator.id) ||
      typeof validator.command !== "string" ||
      validator.command.trim().length === 0 ||
      validator.command.length > 1000
    ) {
      return { valid: false, error: "guardContract.validators requires unique ids and non-empty commands up to 1000 characters" };
    }
    validatorIds.add(validator.id);
    validators.push({ id: validator.id, command: validator.command });
  }
  if (!Array.isArray(candidate.acceptanceCriteria) || candidate.acceptanceCriteria.length > 100) {
    return { valid: false, error: "guardContract.acceptanceCriteria must be an array of at most 100 criteria" };
  }
  const acceptanceCriteria: ActionGuardContract["acceptanceCriteria"] = [];
  const criterionIds = new Set<string>();
  for (const value of candidate.acceptanceCriteria) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return { valid: false, error: "guardContract.acceptanceCriteria contains an invalid criterion" };
    }
    const criterion = value as Record<string, unknown>;
    if (
      typeof criterion.id !== "string" ||
      !isIdentifier(criterion.id) ||
      criterionIds.has(criterion.id) ||
      typeof criterion.description !== "string" ||
      criterion.description.trim().length === 0 ||
      criterion.description.length > 500 ||
      typeof criterion.validatorId !== "string" ||
      !validatorIds.has(criterion.validatorId)
    ) {
      return { valid: false, error: "guardContract.acceptanceCriteria requires unique ids, descriptions, and known validator ids" };
    }
    criterionIds.add(criterion.id);
    acceptanceCriteria.push({
      id: criterion.id,
      description: criterion.description,
      validatorId: criterion.validatorId,
    });
  }
  if (
    candidate.enforcement === "enforce" &&
    (acceptanceCriteria.length === 0 || validators.length === 0)
  ) {
    return { valid: false, error: "enforce guardContract requires at least one criterion and validator" };
  }
  return {
    valid: true,
    contract: {
      enforcement: candidate.enforcement,
      allowedPaths,
      acceptanceCriteria,
      validators,
    },
  };
}

export function registerGravitasGuardFunction(sdk: ISdk, kv: StateKV): void {
  sdk.registerFunction("mem::gravitas-guard", async (payload: unknown) => {
    const parsed = parseOperation(payload);
    if (!parsed) {
      return { success: false, decision: "deny", reason: "invalid guard operation" };
    }
    const operation = parsed;
    if (operation.operation === "completion_check") {
      return withKeyedLock(`mem:action:${operation.actionId}`, async () => {
        const action = await kv.get<Action>(KV.actions, operation.actionId);
        if (!action) {
          return {
            success: false,
            allowed: false,
            reason: "action not found",
            mutationRevision: 0,
            fullyIdle: false,
            missingCriteria: [],
            pendingToolEvents: 0,
          } satisfies CompletionCheckResult;
        }
        const result = await checkActionCompletion(kv, action);
        if (action.guardContract) {
          await recordAudit(kv, "gravitas_guard", "mem::gravitas-guard", [action.id], {
            operation: "completion_check",
            allowed: result.allowed,
            fullyIdle: result.fullyIdle,
            mutationRevision: result.mutationRevision,
            missingCriteria: result.missingCriteria,
          });
        }
        return result;
      });
    }

    return withKeyedLock(`mem:action:${operation.actionId}`, async () => {
      const action = await kv.get<Action>(KV.actions, operation.actionId);
      if (!action) {
        return { success: false, decision: "deny", reason: "action not found" } satisfies GuardDecision;
      }
      if (!action.guardContract) {
        return {
          success: true,
          decision: "allow",
          reason: "action has no guard contract",
          mutationRevision: 0,
        } satisfies GuardDecision;
      }
      const contractValidation = validateActionGuardContract(action.guardContract);
      if (!contractValidation.valid) {
        return { success: false, decision: "deny", reason: "invalid guard contract" } satisfies GuardDecision;
      }
      const contract = contractValidation.contract;
      const state = (await kv.get<GravitasGuardState>(KV.gravitasGuard, action.id)) ?? emptyGuardState(action.id);

      if (operation.operation === "bind") {
        const workspaceRoot = canonicalWorkspaceRoot(operation.workspaceRoots);
        if (!workspaceRoot) {
          return violation(contract, "bind requires exactly one absolute workspace root", state.mutationRevision);
        }
        if (operation.enforcement !== contract.enforcement) {
          return violation(contract, "workspace enforcement mode does not match the action contract", state.mutationRevision);
        }
        if (!state.conversationId) {
          if (state.workspaceRootHash || state.contractHash || state.enforcement) {
            return violation(contract, "existing guard state is incompletely bound", state.mutationRevision);
          }
          state.conversationId = operation.conversationId;
          state.workspaceRootHash = hashGuardValue(workspaceRoot);
          state.contractHash = contractFingerprint(contract);
          state.enforcement = operation.enforcement;
          await persistState(kv, action, state, "bind", {
            conversationHash: hashGuardValue(operation.conversationId),
            workspaceRootHash: state.workspaceRootHash,
            contractHash: state.contractHash,
          });
          return { success: true, decision: "allow", mutationRevision: state.mutationRevision } satisfies GuardDecision;
        }
        if (
          state.conversationId === operation.conversationId &&
          state.workspaceRootHash === hashGuardValue(workspaceRoot) &&
          state.contractHash === contractFingerprint(contract) &&
          state.enforcement === operation.enforcement
        ) {
          return { success: true, decision: "allow", mutationRevision: state.mutationRevision } satisfies GuardDecision;
        }
        return violation(contract, "action is already bound to another conversation or workspace root", state.mutationRevision);
      }

      if (!state.conversationId || state.conversationId !== operation.conversationId) {
        return violation(contract, "conversation is not bound to this action", state.mutationRevision);
      }
      const workspaceRoot = canonicalWorkspaceRoot([operation.workspaceRoot]);
      if (!workspaceRoot || hashGuardValue(workspaceRoot) !== state.workspaceRootHash) {
        return violation(contract, "workspace root does not match the action binding", state.mutationRevision);
      }
      if (state.enforcement !== contract.enforcement) {
        return violation(contract, "bound enforcement mode no longer matches the action contract", state.mutationRevision);
      }
      if (state.contractHash !== contractFingerprint(contract)) {
        return violation(contract, "bound guard contract no longer matches the action contract", state.mutationRevision);
      }

      if (operation.operation === "pre_tool") {
        return handlePreTool(kv, action, contract, state, operation);
      }
      if (operation.operation === "post_tool") {
        return handlePostTool(kv, action, contract, state, operation);
      }
      if (operation.operation === "stop") {
        if (!Number.isSafeInteger(operation.executionNum) || operation.executionNum < 0) {
          return violation(contract, "stop event requires a non-negative executionNum", state.mutationRevision);
        }
        if (state.lastStopExecutionNum !== undefined && operation.executionNum < state.lastStopExecutionNum) {
          return violation(contract, "stale Stop event", state.mutationRevision);
        }
        if (state.lastStopExecutionNum === operation.executionNum) {
          const sameIdleState = state.fullyIdle === operation.fullyIdle;
          return {
            success: true,
            decision: sameIdleState && state.fullyIdle ? "allow" : "deny",
            reason: sameIdleState
              ? (state.fullyIdle ? undefined : "Antigravity reported active work")
              : "conflicting duplicate Stop event",
            mutationRevision: state.mutationRevision,
          } satisfies GuardDecision;
        }
        state.fullyIdle = operation.fullyIdle;
        state.lastStopExecutionNum = operation.executionNum;
        await persistState(kv, action, state, "stop", {
          fullyIdle: operation.fullyIdle,
          executionNum: operation.executionNum,
        });
        return {
          success: true,
          decision: operation.fullyIdle ? "allow" : "deny",
          reason: operation.fullyIdle ? undefined : "Antigravity reported active work",
          mutationRevision: state.mutationRevision,
        } satisfies GuardDecision;
      }
      return handleRearmFailure(kv, action, contract, state, operation);
    });
  });
}

export async function checkActionCompletion(
  kv: StateKV,
  action: Action,
): Promise<CompletionCheckResult> {
  if (!action.guardContract) {
    return { success: true, allowed: true, mutationRevision: 0, fullyIdle: false, missingCriteria: [], pendingToolEvents: 0 };
  }
  const validation = validateActionGuardContract(action.guardContract);
  if (!validation.valid) {
    const allowed = action.guardContract.enforcement === "audit";
    const result: CompletionCheckResult = {
      success: true,
      allowed,
      reason: "invalid guard contract",
      mutationRevision: 0,
      fullyIdle: false,
      missingCriteria: [],
      pendingToolEvents: 0,
    };
    return result;
  }
  const state = await kv.get<GravitasGuardState>(KV.gravitasGuard, action.id);
  const mutationRevision = state?.mutationRevision ?? 0;
  const fullyIdle = state?.fullyIdle === true;
  const contract = validation.contract;
  const bindingMatches = state?.conversationId !== undefined &&
    state.workspaceRootHash !== undefined &&
    state.enforcement === contract.enforcement &&
    state.contractHash === contractFingerprint(contract);
  const events = Array.isArray(state?.events) ? state.events : [];
  const pendingToolEvents = events.filter((event) =>
    event.phase === "pre_tool" &&
    event.decision === "allow" &&
    !events.some((candidate) =>
      candidate.phase === "post_tool" &&
      candidate.stepIndex === event.stepIndex &&
      candidate.toolNameHash === event.toolNameHash &&
      candidate.argumentHash === event.argumentHash &&
      candidate.callHash === event.callHash,
    ),
  ).length;
  const missingCriteria = validation.contract.acceptanceCriteria
    .filter((criterion) => {
      const validator = contract.validators.find((candidate) => candidate.id === criterion.validatorId);
      return !bindingMatches || !validator || !state?.validatorEvidence.some((evidence) =>
        evidence.validatorId === criterion.validatorId &&
        evidence.commandHash === hashGuardValue(validator.command) &&
        evidence.passed &&
        evidence.mutationRevision === mutationRevision,
      );
    })
    .map((criterion) => criterion.id);
  const allowed = contract.enforcement === "audit" ||
    (bindingMatches && fullyIdle && pendingToolEvents === 0 && missingCriteria.length === 0);
  const result: CompletionCheckResult = {
    success: true,
    allowed,
    reason: !bindingMatches
      ? "action guard contract is not bound to this session"
      : pendingToolEvents > 0
        ? "an allowed pre-tool event has no matching post-tool event"
        : !fullyIdle
          ? "Antigravity has not reported fully idle"
          : missingCriteria.length > 0
            ? "fresh validator evidence is missing"
            : undefined,
    mutationRevision,
    fullyIdle,
    missingCriteria,
    pendingToolEvents,
  };
  return result;
}

function handlePreTool(
  kv: StateKV,
  action: Action,
  contract: ActionGuardContract,
  state: GravitasGuardState,
  operation: Extract<GravitasGuardOperation, { operation: "pre_tool" }>,
): Promise<GuardDecision> | GuardDecision {
  const relativePath = operation.relativePath === undefined
    ? undefined
    : normalizeRelativePath(operation.relativePath);
  const callHash = fingerprintCall(operation.toolName, relativePath, operation.argumentHash, operation.commandHash);
  const invalidHash = !isHash(operation.argumentHash) ||
    (operation.strategyFingerprint !== undefined && !isHash(operation.strategyFingerprint)) ||
    (operation.commandHash !== undefined && !isHash(operation.commandHash)) ||
    (operation.currentFileHash !== undefined && operation.currentFileHash !== null && !isHash(operation.currentFileHash));
  if (invalidHash) return violation(contract, "tool event contains an invalid hash", state.mutationRevision, callHash);
  if (operation.relativePath !== undefined && !relativePath) {
    return violation(contract, "file path is not workspace-relative", state.mutationRevision, callHash);
  }
  if (
    operation.isFullFileRead === true &&
    (!isViewFile(operation.toolName) || !relativePath || !isHash(operation.currentFileHash ?? ""))
  ) {
    return violation(contract, "full-file read requires a view_file target and pre-read file hash", state.mutationRevision, callHash);
  }
  const eventCheck = inspectEvent(state, "pre_tool", operation.stepIndex, operation.toolName, operation.argumentHash, contract, callHash);
  if (eventCheck.result) return eventCheck.result;
  state.fullyIdle = false;

  let decision: GuardDecision = { success: true, decision: "allow", mutationRevision: state.mutationRevision };
  let validatorId: string | undefined;
  let retryConsumed = false;
  const isWrite = operation.isWrite ?? isMutatingTool(operation.toolName);
  if (isWrite) {
    if (!relativePath || !isPathAllowed(relativePath, contract.allowedPaths)) {
      decision = violation(contract, "write path is outside the declared scope", state.mutationRevision, callHash);
    } else if (operation.currentFileHash === undefined) {
      decision = violation(contract, "current file state is unknown", state.mutationRevision, callHash);
    } else if (operation.currentFileHash !== null) {
      const receipt = state.reads.find((read) => read.relativePath === relativePath);
      if (!receipt || receipt.fileHash !== operation.currentFileHash) {
        decision = violation(contract, "existing file must be read before it is written", state.mutationRevision, callHash);
      }
    }
  }

  if (decision.decision === "allow" && isRunCommand(operation.toolName)) {
    const validator = operation.commandHash
      ? contract.validators.find((candidate) => hashGuardValue(candidate.command) === operation.commandHash)
      : undefined;
    if (contract.enforcement === "enforce" && !validator) {
      decision = violation(contract, "run_command must match an exact declared validator", state.mutationRevision, callHash);
    }
    const asynchronous = operation.runPersistent === true || operation.waitMsBeforeAsync !== undefined;
    if (asynchronous && validator) {
      decision = violation(contract, "asynchronous run_command cannot serve as a validator", state.mutationRevision, callHash);
    } else {
      validatorId = validator?.id;
    }
  }

  if (decision.decision === "allow") {
    const targetHash = fingerprintTarget(operation.toolName, relativePath);
    const failedCall = [...state.failedCalls].reverse().find((failed) => failed.targetHash === targetHash);
    if (failedCall) {
      const armed = failedCall.retryArmed &&
        failedCall.retryArgumentHash === operation.argumentHash &&
        failedCall.argumentHash !== operation.argumentHash &&
        !!operation.strategyFingerprint &&
        failedCall.retryStrategyFingerprint === operation.strategyFingerprint;
      if (!armed) {
        decision = violation(contract, "failed tool target is blocked; diagnose and re-arm with changed arguments", state.mutationRevision, callHash, validatorId);
      } else {
        failedCall.retryArmed = false;
        failedCall.retryStrategyFingerprint = undefined;
        failedCall.retryArgumentHash = undefined;
        retryConsumed = true;
      }
    }
  }

  const finalized = { ...decision, validatorId, callHash };
  appendEvent(
    state,
    eventCheck.eventKey!,
    operation.stepIndex,
    "pre_tool",
    operation.toolName,
    operation.argumentHash,
    finalized,
    operation.strategyFingerprint,
    operation.isFullFileRead ? operation.currentFileHash ?? undefined : undefined,
  );
  return persistState(kv, action, state, retryConsumed ? "retry_consumed" : "pre_tool", {
    eventKey: eventCheck.eventKey,
    callHash,
    decision: finalized.decision,
    reason: finalized.reason,
    validatorId,
    stepIndex: operation.stepIndex,
  }).then(() => finalized);
}

async function handlePostTool(
  kv: StateKV,
  action: Action,
  contract: ActionGuardContract,
  state: GravitasGuardState,
  operation: Extract<GravitasGuardOperation, { operation: "post_tool" }>,
): Promise<GuardDecision> {
  const relativePath = operation.relativePath === undefined
    ? undefined
    : normalizeRelativePath(operation.relativePath);
  const callHash = fingerprintCall(operation.toolName, relativePath, operation.argumentHash, operation.commandHash);
  if (
    !isHash(operation.argumentHash) ||
    (operation.strategyFingerprint !== undefined && !isHash(operation.strategyFingerprint)) ||
    (operation.commandHash !== undefined && !isHash(operation.commandHash)) ||
    (operation.fileHash !== undefined && !isHash(operation.fileHash)) ||
    (operation.outputHash !== undefined && !isHash(operation.outputHash)) ||
    (operation.relativePath !== undefined && !relativePath) ||
    (operation.statusCode !== undefined && (!Number.isInteger(operation.statusCode) || operation.statusCode < -32768 || operation.statusCode > 65535)) ||
    (operation.stepIndex !== undefined && (!Number.isInteger(operation.stepIndex) || operation.stepIndex < 0))
  ) {
    return violation(contract, "tool event contains invalid bounded metadata", state.mutationRevision, callHash);
  }
  const eventCheck = inspectEvent(state, "post_tool", operation.stepIndex, operation.toolName, operation.argumentHash, contract, callHash);
  if (eventCheck.result) return eventCheck.result;
  const matchingPreEvent = eventCheck.preEvent;
  state.fullyIdle = false;

  const mutates = operation.mutated ?? isMutatingTool(operation.toolName);
  if (operation.success && mutates) {
    state.mutationRevision += 1;
    state.validatorEvidence = [];
    if (relativePath) state.reads = state.reads.filter((read) => read.relativePath !== relativePath);
  }

  const readReceiptIssued = operation.success &&
    operation.isFullFileRead === true &&
    isViewFile(operation.toolName) &&
    !!relativePath &&
    !!matchingPreEvent?.preReadFileHash &&
    matchingPreEvent.preReadFileHash === operation.fileHash;
  if (readReceiptIssued && relativePath && operation.fileHash) {
    upsertReadReceipt(state, { relativePath, fileHash: operation.fileHash });
  }

  const validator = operation.commandHash
    ? contract.validators.find((candidate) => hashGuardValue(candidate.command) === operation.commandHash)
    : undefined;
  const asynchronous = operation.runPersistent === true || operation.waitMsBeforeAsync !== undefined;
  if (isRunCommand(operation.toolName) && validator && !asynchronous) {
    const evidence: GravitasValidatorEvidence = {
      validatorId: validator.id,
      passed: operation.success && (operation.statusCode === undefined || operation.statusCode === 0),
      mutationRevision: state.mutationRevision,
      stepIndex: operation.stepIndex,
      recordedAt: new Date().toISOString(),
      commandHash: operation.commandHash!,
      outputHash: operation.outputHash,
      statusCode: operation.statusCode,
    };
    state.validatorEvidence = state.validatorEvidence.filter((existing) => existing.validatorId !== validator.id);
    state.validatorEvidence.push(evidence);
    state.validatorEvidence = state.validatorEvidence.slice(-MAX_EVIDENCE);
  }

  if (!operation.success) {
    const failure: GravitasFailedCall = {
      callHash,
      targetHash: fingerprintTarget(operation.toolName, relativePath),
      argumentHash: operation.argumentHash,
      toolName: operation.toolName.slice(0, 100),
      strategyFingerprint: operation.strategyFingerprint ?? matchingPreEvent?.strategyFingerprint ?? hashGuardValue("unspecified-strategy"),
      retryArmed: false,
      failedAt: new Date().toISOString(),
    };
    state.failedCalls = state.failedCalls.filter((existing) => existing.callHash !== callHash);
    state.failedCalls.push(failure);
    state.failedCalls = state.failedCalls.slice(-MAX_FAILURES);
  } else {
    const targetHash = fingerprintTarget(operation.toolName, relativePath);
    state.failedCalls = state.failedCalls.filter((failed) => failed.targetHash !== targetHash);
  }

  const result: GuardDecision = {
    success: true,
    decision: "allow",
    reason: operation.success && operation.isFullFileRead && !readReceiptIssued
      ? "pre-read and post-read file hashes did not match; no read receipt was issued"
      : undefined,
    callHash,
    validatorId: validator?.id,
    mutationRevision: state.mutationRevision,
  };
  appendEvent(
    state,
    eventCheck.eventKey!,
    operation.stepIndex,
    "post_tool",
    operation.toolName,
    operation.argumentHash,
    result,
    operation.strategyFingerprint ?? matchingPreEvent?.strategyFingerprint,
  );
  await persistState(kv, action, state, "post_tool", {
    eventKey: eventCheck.eventKey,
    callHash,
    success: operation.success,
    mutated: operation.success && mutates,
    mutationRevision: state.mutationRevision,
    validatorId: validator?.id,
    statusCode: operation.statusCode,
    readReceiptIssued,
  });
  return result;
}

async function handleRearmFailure(
  kv: StateKV,
  action: Action,
  contract: ActionGuardContract,
  state: GravitasGuardState,
  operation: Extract<GravitasGuardOperation, { operation: "rearm_failure" }>,
): Promise<GuardDecision> {
  const diagnosis = operation.diagnosis.trim();
  const failure = state.failedCalls.find((candidate) => candidate.callHash === operation.callHash);
  if (
    !isHash(operation.callHash) ||
    !isHash(operation.strategyFingerprint) ||
    !isHash(operation.nextArgumentHash) ||
    diagnosis.length === 0 ||
    diagnosis.length > 1000
  ) {
    return violation(contract, "failure re-arm requires hashes and a bounded non-empty diagnosis", state.mutationRevision, operation.callHash);
  }
  if (!failure) {
    return violation(contract, "failed call fingerprint was not found", state.mutationRevision, operation.callHash);
  }
  if (failure.retryArmed) {
    return violation(contract, "failed call already has an unconsumed one-use re-arm grant", state.mutationRevision, operation.callHash);
  }
  if (failure.strategyFingerprint === operation.strategyFingerprint) {
    return violation(contract, "failure re-arm requires a changed strategy fingerprint", state.mutationRevision, operation.callHash);
  }
  if (failure.argumentHash === operation.nextArgumentHash) {
    return violation(contract, "failure re-arm requires a changed argument hash", state.mutationRevision, operation.callHash);
  }
  failure.diagnosisHash = hashGuardValue(diagnosis);
  failure.retryStrategyFingerprint = operation.strategyFingerprint;
  failure.retryArgumentHash = operation.nextArgumentHash;
  failure.retryArmed = true;
  await persistState(kv, action, state, "failure_rearmed", {
    callHash: failure.callHash,
    diagnosisHash: failure.diagnosisHash,
    strategyFingerprint: operation.strategyFingerprint,
  });
  return {
    success: true,
    decision: "allow",
    callHash: failure.callHash,
    mutationRevision: state.mutationRevision,
  };
}

async function persistState(
  kv: StateKV,
  action: Action,
  state: GravitasGuardState,
  event: string,
  details: Record<string, unknown>,
): Promise<void> {
  state.updatedAt = new Date().toISOString();
  await kv.set(KV.gravitasGuard, action.id, state);
  await recordAudit(kv, "gravitas_guard", "mem::gravitas-guard", [action.id], {
    event,
    ...details,
  });
}

function emptyGuardState(actionId: string): GravitasGuardState {
  return {
    actionId,
    mutationRevision: 0,
    lastStepIndex: -1,
    fullyIdle: false,
    reads: [],
    failedCalls: [],
    validatorEvidence: [],
    events: [],
    updatedAt: new Date().toISOString(),
  };
}

function inspectEvent(
  state: GravitasGuardState,
  phase: "pre_tool" | "post_tool",
  stepIndex: number,
  toolName: string,
  argumentHash: string,
  contract: ActionGuardContract,
  callHash: string,
): { eventKey?: string; result?: GuardDecision; preEvent?: GravitasGuardEvent } {
  if (!Number.isSafeInteger(stepIndex) || stepIndex < 0) {
    return { result: violation(contract, "hook event requires a non-negative stepIndex", state.mutationRevision, callHash) };
  }
  const eventKey = hashGuardValue(JSON.stringify([stepIndex, phase, toolName, argumentHash]));
  const duplicate = state.events.find((event) => event.eventKey === eventKey);
  if (duplicate) {
    return {
      eventKey,
      result: {
        success: true,
        decision: duplicate.decision,
        reason: duplicate.reason,
        validatorId: duplicate.validatorId,
        callHash: duplicate.callHash,
        mutationRevision: duplicate.mutationRevision,
      },
    };
  }
  const toolNameHash = hashGuardValue(toolName);
  const preEvent = phase === "post_tool"
    ? state.events.find((event) =>
      event.stepIndex === stepIndex &&
      event.phase === "pre_tool" &&
      event.toolNameHash === toolNameHash &&
      event.argumentHash === argumentHash &&
      event.callHash === callHash,
    )
    : undefined;
  if (phase === "post_tool" && !preEvent) {
    return {
      eventKey,
      result: violation(contract, "post-tool event has no matching pre-tool event", state.mutationRevision, callHash),
    };
  }
  if (phase === "post_tool" && preEvent?.decision !== "allow") {
    return {
      eventKey,
      result: violation(contract, "post-tool event follows a denied pre-tool event", state.mutationRevision, callHash),
    };
  }
  if (phase === "pre_tool" && state.events.some((event) =>
    event.stepIndex === stepIndex &&
    event.phase === "post_tool" &&
    event.toolNameHash === toolNameHash &&
    event.argumentHash === argumentHash,
  )) {
    return {
      eventKey,
      result: violation(contract, "pre-tool event arrived after its post-tool event", state.mutationRevision, callHash),
    };
  }
  if (stepIndex < state.lastStepIndex) {
    return { eventKey, result: violation(contract, "stale hook event stepIndex", state.mutationRevision, callHash) };
  }
  if (state.events.length >= MAX_EVENTS) {
    return { eventKey, result: violation(contract, "guard event capacity exhausted", state.mutationRevision, callHash) };
  }
  if (phase === "pre_tool" && state.events.length >= MAX_EVENTS - 1) {
    return { eventKey, result: violation(contract, "guard event capacity cannot reserve a post-tool event", state.mutationRevision, callHash) };
  }
  return { eventKey, preEvent };
}

function appendEvent(
  state: GravitasGuardState,
  eventKey: string,
  stepIndex: number,
  phase: "pre_tool" | "post_tool",
  toolName: string,
  argumentHash: string,
  result: GuardDecision,
  strategyFingerprint?: string,
  preReadFileHash?: string,
): void {
  const event: GravitasGuardEvent = {
    eventKey,
    stepIndex,
    phase,
    toolNameHash: hashGuardValue(toolName),
    argumentHash,
    strategyFingerprint,
    preReadFileHash,
    decision: result.decision,
    reason: result.reason,
    validatorId: result.validatorId,
    callHash: result.callHash,
    mutationRevision: result.mutationRevision ?? state.mutationRevision,
  };
  state.events.push(event);
  state.lastStepIndex = Math.max(state.lastStepIndex, stepIndex);
}

function violation(
  contract: ActionGuardContract,
  reason: string,
  mutationRevision: number,
  callHash?: string,
  validatorId?: string,
): GuardDecision {
  return {
    success: true,
    decision: contract.enforcement === "enforce" ? "deny" : "allow",
    reason,
    callHash,
    validatorId,
    mutationRevision,
  };
}

function parseOperation(value: unknown): GravitasGuardOperation | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const data = value as Record<string, unknown>;
  if (typeof data.actionId !== "string" || data.actionId.length === 0 || data.actionId.length > 200) return null;
  if (data.operation === "completion_check") {
    return hasOnlyKeys(data, ["operation", "actionId"])
      ? { operation: "completion_check", actionId: data.actionId }
      : null;
  }
  if (typeof data.conversationId !== "string" || data.conversationId.trim().length === 0 || data.conversationId.length > 200) return null;
  if (data.operation === "bind") {
    if (
      !hasOnlyKeys(data, ["operation", "actionId", "conversationId", "workspaceRoots", "enforcement"]) ||
      !Array.isArray(data.workspaceRoots) ||
      data.workspaceRoots.length > 10 ||
      !data.workspaceRoots.every((root) => typeof root === "string" && root.length <= 1000) ||
      (data.enforcement !== "audit" && data.enforcement !== "enforce")
    ) return null;
    return {
      operation: "bind",
      actionId: data.actionId,
      conversationId: data.conversationId,
      workspaceRoots: data.workspaceRoots as string[],
      enforcement: data.enforcement,
    };
  }
  if (data.operation === "rearm_failure") {
    if (
      !hasOnlyKeys(data, ["operation", "actionId", "conversationId", "workspaceRoot", "callHash", "diagnosis", "strategyFingerprint", "nextArgumentHash"]) ||
      typeof data.workspaceRoot !== "string" || data.workspaceRoot.length > 1000 ||
      typeof data.callHash !== "string" || typeof data.diagnosis !== "string" || data.diagnosis.length > 1000 ||
      typeof data.strategyFingerprint !== "string" ||
      typeof data.nextArgumentHash !== "string"
    ) return null;
    return {
      operation: "rearm_failure",
      actionId: data.actionId,
      conversationId: data.conversationId,
      workspaceRoot: data.workspaceRoot,
      callHash: data.callHash,
      diagnosis: data.diagnosis,
      strategyFingerprint: data.strategyFingerprint,
      nextArgumentHash: data.nextArgumentHash,
    };
  }
  if (data.operation === "stop") {
    if (
      !hasOnlyKeys(data, ["operation", "actionId", "conversationId", "workspaceRoot", "fullyIdle", "executionNum"]) ||
      typeof data.workspaceRoot !== "string" || data.workspaceRoot.length > 1000 ||
      typeof data.fullyIdle !== "boolean" || typeof data.executionNum !== "number"
    ) return null;
    return {
      operation: "stop",
      actionId: data.actionId,
      conversationId: data.conversationId,
      workspaceRoot: data.workspaceRoot,
      fullyIdle: data.fullyIdle,
      executionNum: data.executionNum,
    };
  }
  if (data.operation === "pre_tool") {
    if (
      !hasOnlyKeys(data, ["operation", "actionId", "conversationId", "workspaceRoot", "toolName", "relativePath", "currentFileHash", "isFullFileRead", "argumentHash", "strategyFingerprint", "commandHash", "isWrite", "runPersistent", "waitMsBeforeAsync", "stepIndex"]) ||
      typeof data.workspaceRoot !== "string" || data.workspaceRoot.length > 1000 ||
      typeof data.toolName !== "string" || data.toolName.length > 100 ||
      typeof data.argumentHash !== "string" || typeof data.stepIndex !== "number"
    ) return null;
    if (data.relativePath !== undefined && (typeof data.relativePath !== "string" || data.relativePath.length > 1000)) return null;
    if (data.currentFileHash !== undefined && data.currentFileHash !== null && typeof data.currentFileHash !== "string") return null;
    if (data.strategyFingerprint !== undefined && typeof data.strategyFingerprint !== "string") return null;
    if (data.commandHash !== undefined && typeof data.commandHash !== "string") return null;
    if (data.isWrite !== undefined && typeof data.isWrite !== "boolean") return null;
    if (data.isFullFileRead !== undefined && typeof data.isFullFileRead !== "boolean") return null;
    if (data.runPersistent !== undefined && typeof data.runPersistent !== "boolean") return null;
    if (data.waitMsBeforeAsync !== undefined && (!Number.isFinite(data.waitMsBeforeAsync) || (data.waitMsBeforeAsync as number) < 0)) return null;
    return {
      operation: "pre_tool",
      actionId: data.actionId,
      conversationId: data.conversationId,
      workspaceRoot: data.workspaceRoot,
      toolName: data.toolName,
      relativePath: data.relativePath as string | undefined,
      currentFileHash: data.currentFileHash as string | null | undefined,
      isFullFileRead: data.isFullFileRead as boolean | undefined,
      argumentHash: data.argumentHash,
      strategyFingerprint: data.strategyFingerprint as string | undefined,
      commandHash: data.commandHash as string | undefined,
      isWrite: data.isWrite as boolean | undefined,
      runPersistent: data.runPersistent as boolean | undefined,
      waitMsBeforeAsync: data.waitMsBeforeAsync as number | undefined,
      stepIndex: data.stepIndex,
    };
  }
  if (data.operation === "post_tool") {
    if (
      !hasOnlyKeys(data, ["operation", "actionId", "conversationId", "workspaceRoot", "toolName", "relativePath", "argumentHash", "success", "strategyFingerprint", "commandHash", "isFullFileRead", "fileHash", "mutated", "runPersistent", "waitMsBeforeAsync", "outputHash", "statusCode", "stepIndex"]) ||
      typeof data.workspaceRoot !== "string" || data.workspaceRoot.length > 1000 ||
      typeof data.toolName !== "string" || data.toolName.length > 100 ||
      typeof data.argumentHash !== "string" || typeof data.success !== "boolean" ||
      typeof data.stepIndex !== "number"
    ) return null;
    for (const key of ["relativePath", "strategyFingerprint", "commandHash", "fileHash", "outputHash"] as const) {
      if (data[key] !== undefined && typeof data[key] !== "string") return null;
    }
    for (const key of ["isFullFileRead", "mutated"] as const) {
      if (data[key] !== undefined && typeof data[key] !== "boolean") return null;
    }
    if (data.runPersistent !== undefined && typeof data.runPersistent !== "boolean") return null;
    if (data.waitMsBeforeAsync !== undefined && (!Number.isFinite(data.waitMsBeforeAsync) || (data.waitMsBeforeAsync as number) < 0)) return null;
    for (const key of ["statusCode", "stepIndex"] as const) {
      if (data[key] !== undefined && typeof data[key] !== "number") return null;
    }
    return {
      operation: "post_tool",
      actionId: data.actionId,
      conversationId: data.conversationId,
      workspaceRoot: data.workspaceRoot,
      toolName: data.toolName,
      relativePath: data.relativePath as string | undefined,
      argumentHash: data.argumentHash,
      success: data.success,
      strategyFingerprint: data.strategyFingerprint as string | undefined,
      commandHash: data.commandHash as string | undefined,
      isFullFileRead: data.isFullFileRead as boolean | undefined,
      fileHash: data.fileHash as string | undefined,
      mutated: data.mutated as boolean | undefined,
      runPersistent: data.runPersistent as boolean | undefined,
      waitMsBeforeAsync: data.waitMsBeforeAsync as number | undefined,
      outputHash: data.outputHash as string | undefined,
      statusCode: data.statusCode as number | undefined,
      stepIndex: data.stepIndex,
    };
  }
  return null;
}

function hasOnlyKeys(data: Record<string, unknown>, allowed: string[]): boolean {
  return Object.keys(data).every((key) => allowed.includes(key));
}

function normalizeRelativePath(value: string): string | null {
  const replaced = value.replace(/\\/g, "/");
  if (!replaced || replaced.startsWith("/") || /^[a-z]:/i.test(replaced)) return null;
  const parts = replaced.split("/").filter((part) => part !== "" && part !== ".");
  if (parts.length === 0 || parts.some((part) => part === ".." || part.includes("\0"))) return null;
  return parts.join("/");
}

function canonicalWorkspaceRoot(values: string[]): string | null {
  if (values.length !== 1 || typeof values[0] !== "string") return null;
  const value = values[0].trim();
  if (!value || value.includes("\0")) return null;
  if (win32Path.isAbsolute(value)) {
    return win32Path.normalize(value).replace(/\\/g, "/").replace(/^([A-Z]):/, (_, drive: string) => `${drive.toLowerCase()}:`);
  }
  if (posixPath.isAbsolute(value)) return posixPath.normalize(value);
  return null;
}

function isPathAllowed(relativePath: string, allowedPaths: string[]): boolean {
  return allowedPaths.some((allowed) => relativePath === allowed || relativePath.startsWith(`${allowed}/`));
}

function fingerprintCall(toolName: string, relativePath: string | null | undefined, argumentHash: string, commandHash?: string): string {
  return hashGuardValue(JSON.stringify([toolName, relativePath ?? "", argumentHash, commandHash ?? ""]));
}

function fingerprintTarget(toolName: string, relativePath: string | null | undefined): string {
  return hashGuardValue(JSON.stringify([toolName.toLowerCase(), relativePath ?? ""]));
}

function isHash(value: string): boolean {
  return HASH_PATTERN.test(value);
}

function isIdentifier(value: string): boolean {
  return /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}$/.test(value);
}

function isRunCommand(toolName: string): boolean {
  return toolName.toLowerCase() === "run_command" || toolName.toLowerCase() === "runcommand";
}

function isViewFile(toolName: string): boolean {
  return toolName.toLowerCase() === "view_file" || toolName.toLowerCase() === "viewfile";
}

function isMutatingTool(toolName: string): boolean {
  return new Set([
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
    "edit_file",
    "create_file",
    "delete_file",
    "move_file",
    "rename_file",
  ]).has(toolName.toLowerCase());
}

function upsertReadReceipt(state: GravitasGuardState, receipt: GravitasReadReceipt): void {
  state.reads = state.reads.filter((existing) => existing.relativePath !== receipt.relativePath);
  state.reads.push(receipt);
  state.reads = state.reads.slice(-MAX_READS);
}
