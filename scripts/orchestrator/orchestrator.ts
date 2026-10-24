import { readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import {
  SpecialistRole,
  SubagentConfig,
  TaskBrief,
  TaskResult,
  OrchestrationPlan,
  OrchestrationRunResult,
} from "./schemas.js";
import { ContextIsolationManager, WorktreeContext } from "./context-isolation.js";
import { TaskGraph } from "./task-graph.js";
import { runConsistencyAudit } from "./consistency-guardian.js";

const ROOT = resolve(join(import.meta.dirname, "../.."));

const ROLES: SpecialistRole[] = [
  "memory-architect",
  "mcp-tool-builder",
  "api-endpoint-builder",
  "hook-specialist",
  "test-engineer",
  "consistency-guardian",
];

export interface TaskDispatchRequest {
  task: TaskBrief;
  workingDirectory: string;
  specialist: SubagentConfig;
}

export interface TaskDispatchResult {
  status: "success" | "failed" | "skipped";
  summary: string;
  validated: boolean;
  modifiedFiles?: string[];
}

export type TaskDispatcher = (request: TaskDispatchRequest) => Promise<TaskDispatchResult>;

export interface OrchestratorOptions {
  repoRoot?: string;
  worktreesDir?: string;
  dispatcher?: TaskDispatcher;
}

export interface OrchestratorSetupCheck {
  passed: boolean;
  discoveredSubagents: number;
  issues: string[];
}

function validConfig(value: unknown): value is SubagentConfig {
  if (!value || typeof value !== "object") {
    return false;
  }
  const config = value as Record<string, unknown>;
  return ["name", "description", "model", "instructions"].every(
    (key) => typeof config[key] === "string" && (config[key] as string).trim().length > 0,
  );
}

export class MainAgentOrchestrator {
  private subagents: Map<SpecialistRole, SubagentConfig> = new Map();
  private configIssues: string[] = [];
  private isolationManager: ContextIsolationManager;
  private repoRoot: string;
  private dispatcher?: TaskDispatcher;

  constructor(options: OrchestratorOptions = {}) {
    this.repoRoot = resolve(options.repoRoot ?? ROOT);
    this.isolationManager = new ContextIsolationManager(this.repoRoot, options.worktreesDir);
    this.dispatcher = options.dispatcher;
    this.loadSubagents();
  }

  private loadSubagents(): void {
    this.subagents.clear();
    this.configIssues = [];

    for (const role of ROLES) {
      const configPath = join(this.repoRoot, ".agents/agents", role, "agent.json");
      if (!existsSync(configPath)) {
        this.configIssues.push(`${role}: missing config at ${configPath}`);
        continue;
      }

      try {
        const parsed: unknown = JSON.parse(readFileSync(configPath, "utf-8"));
        if (!validConfig(parsed)) {
          this.configIssues.push(`${role}: config must define non-empty name, description, model, and instructions`);
          continue;
        }
        this.subagents.set(role, parsed);
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        this.configIssues.push(`${role}: invalid JSON (${detail})`);
      }
    }
  }

  public checkSetup(): OrchestratorSetupCheck {
    this.loadSubagents();
    const issues = [...this.configIssues];
    const isolation = this.isolationManager.checkPrerequisites();
    issues.push(...isolation.issues.map((issue) => `isolation: ${issue}`));
    return {
      passed: issues.length === 0,
      discoveredSubagents: this.subagents.size,
      issues,
    };
  }

  public getSubagent(role: SpecialistRole): SubagentConfig | undefined {
    return this.subagents.get(role);
  }

  public getAllSubagents(): Map<SpecialistRole, SubagentConfig> {
    return new Map(this.subagents);
  }

  private failedResult(task: TaskBrief, startTime: number, error: string, worktreePath?: string): TaskResult {
    return {
      taskId: task.id,
      specialist: task.specialist,
      status: "failed",
      durationMs: Date.now() - startTime,
      modifiedFiles: [],
      summary: `Failure in ${task.title}: ${error}`,
      error,
      worktreePath,
      tierModel: this.subagents.get(task.specialist)?.model ?? "built-in",
    };
  }

  private modifiedFilesFor(context?: WorktreeContext): string[] {
    return context ? this.isolationManager.getModifiedFiles(context) : [];
  }

  private runBuiltInTask(task: TaskBrief, workDir: string): TaskDispatchResult | undefined {
    if (task.specialist === "consistency-guardian") {
      if (!/\bconsistency\b/i.test(task.prompt)) {
        return {
          status: "failed",
          summary: "Built-in consistency handler only accepts consistency-audit prompts; request was not executed.",
          validated: false,
        };
      }
      const audit = runConsistencyAudit();
      const passedCount = audit.results.filter((result) => result.passed).length;
      const summary = `Built-in consistency audit ${audit.passed ? "passed" : "failed"} (${passedCount}/${audit.results.length} checks).`;
      return { status: audit.passed ? "success" : "failed", summary, validated: audit.passed };
    }

    if (task.specialist === "test-engineer") {
      if (!/\b(test|vitest|tests)\b/i.test(task.prompt)) {
        return {
          status: "failed",
          summary: "Built-in test handler only accepts test-suite prompts; request was not executed.",
          validated: false,
        };
      }
      const vitestCli = join(this.repoRoot, "node_modules", "vitest", "vitest.mjs");
      if (!existsSync(vitestCli)) {
        return {
          status: "failed",
          summary: "Built-in test suite could not start because the repository Vitest CLI is unavailable.",
          validated: false,
        };
      }
      try {
        execFileSync(process.execPath, [vitestCli, "run", "--exclude", "test/integration.test.ts"], {
          cwd: workDir,
          stdio: "pipe",
          encoding: "utf-8",
        });
        return { status: "success", summary: "Built-in Vitest suite passed.", validated: true };
      } catch (error) {
        const detail = error instanceof Error ? error.message : String(error);
        return { status: "failed", summary: `Built-in Vitest suite failed: ${detail}`, validated: false };
      }
    }

    return undefined;
  }

  public async executeTask(task: TaskBrief): Promise<TaskResult> {
    const startTime = Date.now();
    if (!task.prompt.trim()) {
      return this.failedResult(task, startTime, "task prompt is empty and cannot be dispatched");
    }

    const builtin = task.specialist === "test-engineer" || task.specialist === "consistency-guardian";
    const specialistConfig = this.subagents.get(task.specialist);
    if (!builtin && !this.dispatcher) {
      return this.failedResult(
        task,
        startTime,
        `No task dispatcher is configured for ${task.specialist}; prompt was not executed.`,
      );
    }
    if (!builtin && !specialistConfig) {
      return this.failedResult(task, startTime, `No valid subagent config is available for ${task.specialist}.`);
    }

    const isolation = task.isolation ?? "worktree";
    if (isolation === "sandbox") {
      return this.failedResult(task, startTime, "sandbox isolation is unsupported; no substitute directory was created");
    }

    let worktreeContext: WorktreeContext | undefined;
    let workDir = this.repoRoot;
    let rollbackTriggered = false;
    let blastRadiusScore = 0;

    try {
      if (isolation === "worktree") {
        worktreeContext = this.isolationManager.createWorktree(task.id);
        workDir = worktreeContext.worktreePath;
      }

      const result = this.runBuiltInTask(task, workDir) ?? await this.dispatcher!({
        task,
        workingDirectory: workDir,
        specialist: specialistConfig!,
      });

      if (result.status === "success" && !result.validated) {
        throw new Error("dispatcher reported success without validation evidence");
      }

      const modifiedFiles = worktreeContext
        ? this.modifiedFilesFor(worktreeContext)
        : result.modifiedFiles ?? [];

      if (worktreeContext && result.status === "success") {
        const minimizerScript = join(this.repoRoot, "scripts/rollback_minimizer.py");
        if (existsSync(minimizerScript)) {
          const pyCommand = process.platform === "win32" ? "py" : "python3";
          try {
            const gateRaw = execFileSync(pyCommand, [minimizerScript, "gate", worktreeContext.baseCommit], {
              cwd: workDir,
              stdio: "pipe",
              encoding: "utf-8",
            });
            const gateResult = JSON.parse(gateRaw) as {
              gate_passed?: boolean;
              blast_analysis?: { blast_score?: number };
              invariant_verification?: { violations?: unknown };
            };
            blastRadiusScore = gateResult.blast_analysis?.blast_score ?? 0;
            if (!gateResult.gate_passed) {
              rollbackTriggered = true;
              const violations = JSON.stringify(gateResult.invariant_verification?.violations ?? []);
              return {
                taskId: task.id,
                specialist: task.specialist,
                status: "failed",
                durationMs: Date.now() - startTime,
                modifiedFiles,
                summary: `Rollback gate blocked ${task.title}; worktree data was retained for review.`,
                error: `Invariant violations: ${violations}`,
                worktreePath: workDir,
                blastRadiusScore,
                rollbackTriggered,
                tierModel: specialistConfig?.model ?? "built-in",
              };
            }
          } catch (error) {
            rollbackTriggered = true;
            const detail = error instanceof Error ? error.message : String(error);
            return {
              taskId: task.id,
              specialist: task.specialist,
              status: "failed",
              durationMs: Date.now() - startTime,
              modifiedFiles,
              summary: `Rollback gate could not validate ${task.title}; worktree data was retained for review.`,
              error: detail,
              worktreePath: workDir,
              blastRadiusScore,
              rollbackTriggered,
              tierModel: specialistConfig?.model ?? "built-in",
            };
          }
        }
      }

      const retentionNote = worktreeContext
        ? ` Worktree retained for review at ${worktreeContext.worktreePath}; no automatic commit or merge was performed.`
        : "";
      return {
        taskId: task.id,
        specialist: task.specialist,
        status: result.status,
        durationMs: Date.now() - startTime,
        modifiedFiles,
        summary: `${result.summary}${retentionNote}`,
        worktreePath: worktreeContext?.worktreePath,
        blastRadiusScore,
        rollbackTriggered,
        tierModel: specialistConfig?.model ?? "built-in",
        ...(result.status !== "success" ? { error: result.summary } : {}),
      };
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      let modifiedFiles: string[] = [];
      if (worktreeContext) {
        try {
          modifiedFiles = this.modifiedFilesFor(worktreeContext);
        } catch {
          modifiedFiles = [];
        }
      }
      return {
        taskId: task.id,
        specialist: task.specialist,
        status: "failed",
        durationMs: Date.now() - startTime,
        modifiedFiles,
        summary: `Failure in ${task.title}: ${detail}${worktreeContext ? ` Worktree retained at ${worktreeContext.worktreePath}.` : ""}`,
        error: detail,
        worktreePath: worktreeContext?.worktreePath,
        blastRadiusScore,
        rollbackTriggered,
        tierModel: specialistConfig?.model ?? "built-in",
      };
    }
  }

  public async runPlan(plan: OrchestrationPlan): Promise<OrchestrationRunResult> {
    const startTime = new Date().toISOString();
    const startMs = Date.now();
    const taskResults: Record<string, TaskResult> = {};
    let rollbacksPrevented = 0;
    let evaluatedCount = 0;

    console.log(`\x1b[1m\x1b[35m=== Main Agent Orchestrator: Starting Goal ===\x1b[0m`);
    console.log(`\x1b[36mGoal:\x1b[0m ${plan.goal}`);
    console.log(`\x1b[36mTotal Tasks:\x1b[0m ${plan.tasks.length}\n`);

    const graph = new TaskGraph(plan.tasks);
    const stages = graph.computeStages();

    let allSuccess = true;
    for (const stage of stages) {
      console.log(`\x1b[1m\x1b[34m--- Stage ${stage.stageIndex + 1} (${stage.tasks.length} parallel task(s)) ---\x1b[0m`);
      const results = await Promise.all(stage.tasks.map((task) => {
        const sub = this.subagents.get(task.specialist);
        console.log(`  ▶ [${task.id}] Dispatching to \x1b[33m@${task.specialist}\x1b[0m (${sub?.model ?? "built-in/unsupported"})`);
        return this.executeTask(task);
      }));

      for (const result of results) {
        evaluatedCount++;
        if (result.rollbackTriggered) {
          rollbacksPrevented++;
        }
        taskResults[result.taskId] = result;
        const icon = result.status === "success" ? "\x1b[32m✔\x1b[0m" : "\x1b[31m✖\x1b[0m";
        console.log(`  ${icon} [${result.taskId}] ${result.summary} (${result.durationMs}ms)`);
        if (result.status !== "success") {
          allSuccess = false;
        }
      }

      if (!allSuccess) {
        console.log(`\x1b[31mStage ${stage.stageIndex + 1} failed. Triggering circuit breaker.\x1b[0m`);
        break;
      }
    }

    console.log(`\n\x1b[1m\x1b[35m--- Final Consistency Gate (@consistency-guardian) ---\x1b[0m`);
    const consistency = runConsistencyAudit();
    console.log(
      consistency.passed
        ? `\x1b[32m✔ Consistency Guardian verified ${consistency.results.length} configured checks.\x1b[0m`
        : `\x1b[31m✖ Consistency Guardian found discrepancies.\x1b[0m`,
    );

    const totalDurationMs = Date.now() - startMs;
    const endTime = new Date().toISOString();
    return {
      id: plan.id,
      goal: plan.goal,
      status: allSuccess && consistency.passed ? "completed" : "failed",
      startTime,
      endTime,
      totalDurationMs,
      taskResults,
      consistencyAudit: {
        passed: consistency.passed,
        details: `${consistency.results.filter((result) => result.passed).length}/${consistency.results.length} checks passed`,
      },
      rollbackDefense: {
        evaluated: evaluatedCount,
        rollbacksPrevented,
        status: rollbacksPrevented > 0 ? "ROLLBACK_PREVENTED" : "ALL_INVARIANTS_HELD",
      },
    };
  }
}
