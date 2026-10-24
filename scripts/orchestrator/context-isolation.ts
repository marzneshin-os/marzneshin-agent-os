import { randomUUID } from "node:crypto";
import { execFileSync } from "node:child_process";
import { accessSync, constants, existsSync, mkdirSync, statSync } from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { tmpdir } from "node:os";

export interface WorktreeContext {
  taskId: string;
  branchName: string;
  worktreePath: string;
  baseCommit: string;
  createdAt: number;
}

export interface IsolationCheck {
  passed: boolean;
  issues: string[];
}

export class ContextIsolationManager {
  private repoRoot: string;
  private baseDir: string;

  constructor(
    repoRoot: string = process.cwd(),
    worktreesDir: string = join(tmpdir(), "agentmemory-worktrees"),
  ) {
    this.repoRoot = resolve(repoRoot);
    this.baseDir = resolve(worktreesDir);
  }

  public checkPrerequisites(): IsolationCheck {
    const issues: string[] = [];

    try {
      const gitRoot = resolve(execFileSync("git", ["rev-parse", "--show-toplevel"], {
        cwd: this.repoRoot,
        encoding: "utf-8",
        stdio: "pipe",
      }).trim());
      const destinationRelative = relative(gitRoot, this.baseDir);
      const parentPrefix = ".." + (process.platform === "win32" ? "\\" : "/");
      if (!isAbsolute(destinationRelative) && destinationRelative !== ".." && !destinationRelative.startsWith(parentPrefix)) {
        issues.push("worktree destination must be outside the repository to avoid creating untracked project files");
      }
    } catch {
      issues.push("repository root is not inside a Git worktree");
    }

    try {
      execFileSync("git", ["rev-parse", "--verify", "HEAD"], {
        cwd: this.repoRoot,
        encoding: "utf-8",
        stdio: "pipe",
      });
    } catch {
      issues.push("repository has no committed HEAD to use as an isolation base");
    }

    try {
      const status = execFileSync("git", ["status", "--porcelain=v1", "--untracked-files=normal"], {
        cwd: this.repoRoot,
        encoding: "utf-8",
        stdio: "pipe",
      });
      if (status.trim()) {
        issues.push("working tree is dirty; refusing to omit local changes from an isolated worktree");
      }
    } catch {
      if (!issues.some((issue) => issue.includes("Git worktree"))) {
        issues.push("unable to inspect working tree status safely");
      }
    }

    try {
      let writablePath = this.baseDir;
      while (!existsSync(writablePath) && writablePath !== dirname(writablePath)) {
        writablePath = dirname(writablePath);
      }
      if (!existsSync(writablePath) || !statSync(writablePath).isDirectory()) {
        issues.push("worktree destination has no existing directory parent");
      } else {
        accessSync(writablePath, constants.W_OK);
      }
      if (existsSync(this.baseDir) && !statSync(this.baseDir).isDirectory()) {
        issues.push("worktree destination exists and is not a directory");
      }
    } catch {
      issues.push("worktree destination is not writable");
    }

    return { passed: issues.length === 0, issues };
  }

  public createWorktree(taskId: string): WorktreeContext {
    if (!taskId.trim()) {
      throw new Error("A non-empty task ID is required to create a worktree");
    }

    const prerequisites = this.checkPrerequisites();
    if (!prerequisites.passed) {
      throw new Error(`Cannot create a safe worktree: ${prerequisites.issues.join("; ")}`);
    }

    const safeId = taskId.replace(/[^a-zA-Z0-9_-]/g, "-").toLowerCase().slice(0, 40) || "task";
    const uniqueId = randomUUID();
    const branchName = `sdd-${safeId}-${uniqueId}`;
    const worktreePath = join(this.baseDir, `${safeId}-${uniqueId}`);
    const baseCommit = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: this.repoRoot,
      encoding: "utf-8",
      stdio: "pipe",
    }).trim();
    const timestamp = Date.now();

    mkdirSync(this.baseDir, { recursive: true });
    try {
      execFileSync("git", ["worktree", "add", "-b", branchName, worktreePath, baseCommit], {
        cwd: this.repoRoot,
        encoding: "utf-8",
        stdio: "pipe",
      });
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      throw new Error(`Git worktree creation failed for ${taskId} at ${worktreePath}; no fallback was created and any partial data was retained: ${detail}`);
    }

    return { taskId, branchName, worktreePath, baseCommit, createdAt: timestamp };
  }

  public getModifiedFiles(context: WorktreeContext): string[] {
    const committedChanges = execFileSync("git", ["diff", "--name-only", "-z", "--no-renames", context.baseCommit, "HEAD"], {
      cwd: context.worktreePath,
      encoding: "utf-8",
      stdio: "pipe",
    });
    const status = execFileSync("git", ["status", "--porcelain=v1", "-z", "--untracked-files=all"], {
      cwd: context.worktreePath,
      encoding: "utf-8",
      stdio: "pipe",
    });
    const changed = new Set(committedChanges.split("\0").filter(Boolean));
    const records = status.split("\0").filter(Boolean);
    for (const record of records) {
      if (record.length >= 4) {
        changed.add(record.slice(3));
      }
    }
    return Array.from(changed).sort();
  }
}
