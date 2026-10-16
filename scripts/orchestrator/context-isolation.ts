import { execSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

export interface WorktreeContext {
  taskId: string;
  branchName: string;
  worktreePath: string;
  createdAt: number;
}

export class ContextIsolationManager {
  private activeWorktrees: Map<string, WorktreeContext> = new Map();
  private baseDir: string;

  constructor(repoRoot: string = process.cwd()) {
    this.baseDir = join(tmpdir(), "agentmemory-worktrees");
    if (!existsSync(this.baseDir)) {
      mkdirSync(this.baseDir, { recursive: true });
    }
  }

  public createWorktree(taskId: string): WorktreeContext {
    const safeId = taskId.replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase();
    const timestamp = Date.now();
    const branchName = `sdd-${safeId}-${timestamp}`;
    const worktreePath = join(this.baseDir, `${safeId}-${timestamp}`);

    try {
      execSync(`git worktree add -b ${branchName} "${worktreePath}" HEAD`, {
        stdio: "pipe",
        encoding: "utf-8",
      });

      const ctx: WorktreeContext = {
        taskId,
        branchName,
        worktreePath,
        createdAt: timestamp,
      };

      this.activeWorktrees.set(taskId, ctx);
      return ctx;
    } catch (err: any) {
      // Fallback: If git worktree fails (e.g. shallow clone or uncommitted changes), create isolated sandbox directory
      mkdirSync(worktreePath, { recursive: true });
      const ctx: WorktreeContext = {
        taskId,
        branchName: "fallback-sandbox",
        worktreePath,
        createdAt: timestamp,
      };
      this.activeWorktrees.set(taskId, ctx);
      return ctx;
    }
  }

  public getModifiedFiles(context: WorktreeContext): string[] {
    try {
      const output = execSync(`git -C "${context.worktreePath}" status --porcelain`, {
        encoding: "utf-8",
      });
      return output
        .split("\n")
        .map((line) => line.trim().slice(3))
        .filter(Boolean);
    } catch {
      return [];
    }
  }

  public mergeWorktree(context: WorktreeContext): { success: boolean; modifiedFiles: string[] } {
    const modifiedFiles = this.getModifiedFiles(context);
    if (context.branchName === "fallback-sandbox") {
      return { success: true, modifiedFiles };
    }

    try {
      // Commit in worktree
      execSync(
        `git -C "${context.worktreePath}" add -A && git -C "${context.worktreePath}" commit -m "sdd(${context.taskId}): task completion" --allow-empty`,
        { stdio: "pipe" },
      );

      // Merge into current branch
      execSync(`git merge ${context.branchName} --no-edit`, { stdio: "pipe" });

      return { success: true, modifiedFiles };
    } catch (err: any) {
      return { success: false, modifiedFiles };
    }
  }

  public cleanupWorktree(context: WorktreeContext): void {
    try {
      if (context.branchName !== "fallback-sandbox") {
        execSync(`git worktree remove --force "${context.worktreePath}"`, {
          stdio: "pipe",
        });
        execSync(`git branch -D ${context.branchName}`, { stdio: "pipe" });
      } else {
        rmSync(context.worktreePath, { recursive: true, force: true });
      }
    } catch {
      // best-effort cleanup
    } finally {
      this.activeWorktrees.delete(context.taskId);
    }
  }

  public cleanupAll(): void {
    for (const ctx of Array.from(this.activeWorktrees.values())) {
      this.cleanupWorktree(ctx);
    }
  }
}
