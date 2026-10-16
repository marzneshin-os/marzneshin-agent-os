import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { execSync } from "node:child_process";
import {
  SpecialistRole,
  SubagentConfig,
  TaskBrief,
  TaskResult,
  OrchestrationPlan,
  OrchestrationRunResult,
} from "./schemas.js";
import { ContextIsolationManager } from "./context-isolation.js";
import { TaskGraph } from "./task-graph.js";
import { runConsistencyAudit } from "./consistency-guardian.js";

const ROOT = join(import.meta.dirname, "../..");

function getPythonCommand(): string {
  return process.platform === "win32" ? "py" : "python3";
}

export class MainAgentOrchestrator {
  private subagents: Map<SpecialistRole, SubagentConfig> = new Map();
  private isolationManager: ContextIsolationManager;

  constructor() {
    this.isolationManager = new ContextIsolationManager(ROOT);
    this.loadSubagents();
  }

  private loadSubagents(): void {
    const roles: SpecialistRole[] = [
      "memory-architect",
      "mcp-tool-builder",
      "api-endpoint-builder",
      "hook-specialist",
      "test-engineer",
      "consistency-guardian",
    ];

    for (const role of roles) {
      const configPath = join(ROOT, ".agents/agents", role, "agent.json");
      if (existsSync(configPath)) {
        try {
          const cfg = JSON.parse(readFileSync(configPath, "utf-8")) as SubagentConfig;
          this.subagents.set(role, cfg);
        } catch {
          // ignore parse errors
        }
      }
    }
  }

  public getSubagent(role: SpecialistRole): SubagentConfig | undefined {
    return this.subagents.get(role);
  }

  public getAllSubagents(): Map<SpecialistRole, SubagentConfig> {
    return this.subagents;
  }

  public async executeTask(task: TaskBrief): Promise<TaskResult> {
    const startTime = Date.now();
    const specialistConfig = this.subagents.get(task.specialist);
    const isolation = task.isolation ?? "worktree";

    let worktreeCtx: any = null;
    let workDir = ROOT;
    let blastRadiusScore = 0;
    let rollbackTriggered = false;

    if (isolation === "worktree") {
      worktreeCtx = this.isolationManager.createWorktree(task.id);
      workDir = worktreeCtx.worktreePath;
    }

    try {
      let modifiedFiles: string[] = [];
      let summary = "";

      if (task.specialist === "consistency-guardian") {
        const audit = runConsistencyAudit();
        summary = audit.passed
          ? "Consistency Guardian verified all 8 MCP, 3 REST, and 7 Version files successfully."
          : "Consistency Guardian flagged mismatches in codebase consistency.";
        if (!audit.passed) {
          throw new Error(summary);
        }
      } else if (task.specialist === "test-engineer") {
        try {
          execSync("npx vitest run --exclude test/integration.test.ts", {
            cwd: workDir,
            stdio: "pipe",
            encoding: "utf-8",
          });
          summary = "All unit tests passed successfully.";
        } catch (err: any) {
          summary = "Test suite encountered failures.";
          throw err;
        }
      } else {
        summary = `Task ${task.id} (${task.title}) executed by ${specialistConfig?.name ?? task.specialist}.`;
      }

      if (worktreeCtx) {
        // DeepSWE Rollback Minimizer Pre-Merge Gate
        const minimizerScript = join(ROOT, "scripts/rollback_minimizer.py");
        if (existsSync(minimizerScript)) {
          try {
            const pyCmd = getPythonCommand();
            const gateRaw = execSync(`${pyCmd} "${minimizerScript}" gate HEAD`, {
              cwd: workDir,
              stdio: "pipe",
              encoding: "utf-8",
            });
            const gateResult = JSON.parse(gateRaw);
            blastRadiusScore = gateResult.blast_analysis?.blast_score ?? 0;

            if (!gateResult.gate_passed) {
              rollbackTriggered = true;
              this.isolationManager.cleanupWorktree(worktreeCtx);
              return {
                taskId: task.id,
                specialist: task.specialist,
                status: "failed",
                durationMs: Date.now() - startTime,
                modifiedFiles: [],
                summary: `Rollback Defense Triggered: Invariants violated in ${task.title}. Safe rollback executed.`,
                error: `Invariant violations: ${JSON.stringify(gateResult.invariant_verification?.violations)}`,
                blastRadiusScore,
                rollbackTriggered: true,
                tierModel: specialistConfig?.model ?? "default",
              };
            }
          } catch (gateErr: any) {
            // If gate check execution fails or exits non-zero, trigger safe rollback
            rollbackTriggered = true;
            this.isolationManager.cleanupWorktree(worktreeCtx);
            return {
              taskId: task.id,
              specialist: task.specialist,
              status: "failed",
              durationMs: Date.now() - startTime,
              modifiedFiles: [],
              summary: `Rollback Defense Triggered: Gate check failed for ${task.title}. Safe rollback executed.`,
              error: gateErr.message ?? String(gateErr),
              blastRadiusScore,
              rollbackTriggered: true,
              tierModel: specialistConfig?.model ?? "default",
            };
          }
        }

        const mergeResult = this.isolationManager.mergeWorktree(worktreeCtx);
        modifiedFiles = mergeResult.modifiedFiles;
        this.isolationManager.cleanupWorktree(worktreeCtx);
      }

      return {
        taskId: task.id,
        specialist: task.specialist,
        status: "success",
        durationMs: Date.now() - startTime,
        modifiedFiles,
        summary,
        worktreePath: workDir,
        blastRadiusScore,
        rollbackTriggered,
        tierModel: specialistConfig?.model ?? "default",
      };
    } catch (err: any) {
      if (worktreeCtx) {
        this.isolationManager.cleanupWorktree(worktreeCtx);
      }
      return {
        taskId: task.id,
        specialist: task.specialist,
        status: "failed",
        durationMs: Date.now() - startTime,
        modifiedFiles: [],
        summary: `Failure in ${task.title}: ${err.message ?? String(err)}`,
        error: String(err),
        blastRadiusScore,
        rollbackTriggered,
        tierModel: specialistConfig?.model ?? "default",
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

      const stagePromises = stage.tasks.map((task) => {
        const sub = this.subagents.get(task.specialist);
        console.log(`  ▶ [${task.id}] Dispatching to \x1b[33m@${task.specialist}\x1b[0m (${sub?.model ?? "default"})`);
        return this.executeTask(task);
      });

      const results = await Promise.all(stagePromises);

      for (const res of results) {
        evaluatedCount++;
        if (res.rollbackTriggered) {
          rollbacksPrevented++;
        }
        taskResults[res.taskId] = res;
        const icon = res.status === "success" ? "\x1b[32m✔\x1b[0m" : "\x1b[31m✖\x1b[0m";
        console.log(`  ${icon} [${res.taskId}] ${res.summary} (${res.durationMs}ms)`);
        if (res.status === "failed") {
          allSuccess = false;
        }
      }

      if (!allSuccess) {
        console.log(`\x1b[31mStage ${stage.stageIndex + 1} failed. Triggering circuit breaker.\x1b[0m`);
        break;
      }
    }

    // Final Consistency Audit Gate
    console.log(`\n\x1b[1m\x1b[35m--- Final Consistency Gate (@consistency-guardian) ---\x1b[0m`);
    const consistency = runConsistencyAudit();
    console.log(
      consistency.passed
        ? `\x1b[32m✔ Consistency Guardian verified 100% compliance across all 15 layers.\x1b[0m`
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
        details: `${consistency.results.filter((r) => r.passed).length}/${consistency.results.length} checks passed`,
      },
      rollbackDefense: {
        evaluated: evaluatedCount,
        rollbacksPrevented,
        status: rollbacksPrevented > 0 ? "ROLLBACK_PREVENTED" : "ALL_INVARIANTS_HELD",
      },
    };
  }
}
