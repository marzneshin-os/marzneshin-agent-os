import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { describe, expect, it } from "vitest";
import { ContextIsolationManager } from "../scripts/orchestrator/context-isolation.js";
import { MainAgentOrchestrator } from "../scripts/orchestrator/orchestrator.js";
import type { SpecialistRole, SubagentConfig, TaskBrief } from "../scripts/orchestrator/schemas.js";

function createRepository(): string {
  const parent = mkdtempSync(join(tmpdir(), "agentmemory-orchestrator-test-"));
  const root = join(parent, "repo");
  mkdirSync(root);
  git(root, ["init", "--initial-branch=main"]);
  git(root, ["config", "user.email", "test@example.invalid"]);
  git(root, ["config", "user.name", "Orchestrator Test"]);
  writeFileSync(join(root, "README.md"), "initial\n");
  git(root, ["add", "README.md"]);
  git(root, ["commit", "-m", "initial"]);
  return root;
}

function worktreesDirectory(root: string): string {
  return join(root, "..", basename(root) + "-worktrees");
}

function git(cwd: string, args: string[]): string {
  return execFileSync("git", args, { cwd, encoding: "utf8", stdio: "pipe" });
}

function addAgentConfig(root: string, role: SpecialistRole): SubagentConfig {
  const config: SubagentConfig = {
    name: role,
    description: `${role} test agent`,
    model: "test-model",
    instructions: "Use the task prompt and return validated evidence.",
  };
  const directory = join(root, ".agents", "agents", role);
  mkdirSync(directory, { recursive: true });
  writeFileSync(join(directory, "agent.json"), JSON.stringify(config));
  git(root, ["add", ".agents/agents"]);
  git(root, ["commit", "-m", `add ${role} config`]);
  return config;
}

function task(overrides: Partial<TaskBrief> = {}): TaskBrief {
  return {
    id: "task-1",
    title: "Implement guarded change",
    specialist: "memory-architect",
    prompt: "Make the requested change and validate it.",
    isolation: "direct",
    ...overrides,
  };
}

function normalizedPath(path: string): string {
  return path.replace(/\\/g, "/");
}

describe("orchestrator isolation safety", () => {
  it("refuses a dirty repository instead of returning an empty fallback sandbox", () => {
    const root = createRepository();
    const worktreesDir = worktreesDirectory(root);
    writeFileSync(join(root, "user-change.txt"), "keep this change\n");
    const manager = new ContextIsolationManager(root, worktreesDir);

    expect(() => manager.createWorktree("dirty-task")).toThrow(/working tree.*dirty/i);
    expect(existsSync(worktreesDir)).toBe(false);
    expect(readFileSync(join(root, "user-change.txt"), "utf8")).toBe("keep this change\n");
    expect(git(root, ["worktree", "list", "--porcelain"]).match(/^worktree /gm)).toHaveLength(1);
  }, 60000);

  it("reports unsupported specialist work instead of claiming the prompt ran", async () => {
    const root = createRepository();
    addAgentConfig(root, "memory-architect");
    const orchestrator = new MainAgentOrchestrator({ repoRoot: root, worktreesDir: worktreesDirectory(root) });

    const result = await orchestrator.executeTask(task({ isolation: "direct" }));

    expect(result.status).toBe("failed");
    expect(result.error).toMatch(/no task dispatcher/i);
    expect(result.summary).toMatch(/prompt was not executed/i);
  }, 60000);

  it("passes the complete task prompt to a real dispatcher and requires validation", async () => {
    const root = createRepository();
    addAgentConfig(root, "memory-architect");
    let receivedPrompt = "";
    const orchestrator = new MainAgentOrchestrator({
      repoRoot: root,
      dispatcher: async ({ task: dispatchedTask }) => {
        receivedPrompt = dispatchedTask.prompt;
        return { status: "success", summary: "Finished requested change.", validated: true };
      },
    });
    const prompt = "Update the persistence boundary and run its focused checks.";

    const result = await orchestrator.executeTask(task({ prompt }));

    expect(receivedPrompt).toBe(prompt);
    expect(result.status).toBe("success");

    const unvalidated = new MainAgentOrchestrator({
      repoRoot: root,
      dispatcher: async () => ({ status: "success", summary: "No proof supplied.", validated: false }),
    });
    const rejected = await unvalidated.executeTask(task());
    expect(rejected.status).toBe("failed");
    expect(rejected.error).toMatch(/validation/i);
  }, 60000);

  it("retains failed dispatcher worktree data without committing or merging it", async () => {
    const root = createRepository();
    addAgentConfig(root, "memory-architect");
    const baseCommit = git(root, ["rev-parse", "HEAD"]).trim();
    const orchestrator = new MainAgentOrchestrator({
      repoRoot: root,
      worktreesDir: worktreesDirectory(root),
      dispatcher: async ({ workingDirectory }) => {
        writeFileSync(join(workingDirectory, "partial-result.txt"), "retain me\n");
        return { status: "failed", summary: "The specialist could not finish.", validated: false };
      },
    });

    const result = await orchestrator.executeTask(task({ isolation: "worktree" }));

    expect(result.status).toBe("failed");
    expect(result.worktreePath).toBeTruthy();
    expect(readFileSync(join(result.worktreePath!, "partial-result.txt"), "utf8")).toBe("retain me\n");
    expect(git(root, ["rev-parse", "HEAD"]).trim()).toBe(baseCommit);
    expect(git(root, ["status", "--porcelain"]).trim()).toBe("");
    expect(normalizedPath(git(root, ["worktree", "list", "--porcelain"]))).toContain(normalizedPath(result.worktreePath!));
  }, 60000);

  it("keeps successful isolated output available and unmerged for review", async () => {
    const root = createRepository();
    addAgentConfig(root, "memory-architect");
    const baseCommit = git(root, ["rev-parse", "HEAD"]).trim();
    const orchestrator = new MainAgentOrchestrator({
      repoRoot: root,
      worktreesDir: worktreesDirectory(root),
      dispatcher: async ({ workingDirectory, task: dispatchedTask }) => {
        expect(dispatchedTask.prompt).toContain("requested change");
        writeFileSync(join(workingDirectory, "result.txt"), "ready for review\n");
        return { status: "success", summary: "Change validated.", validated: true };
      },
    });

    const result = await orchestrator.executeTask(task({ isolation: "worktree" }));

    expect(result.status).toBe("success");
    expect(result.modifiedFiles).toContain("result.txt");
    expect(result.summary).toMatch(/retained for review/i);
    expect(existsSync(join(result.worktreePath!, "result.txt"))).toBe(true);
    expect(existsSync(join(root, "result.txt"))).toBe(false);
    expect(git(root, ["rev-parse", "HEAD"]).trim()).toBe(baseCommit);
    expect(git(result.worktreePath!, ["status", "--porcelain"]).trim()).toContain("result.txt");
    expect(normalizedPath(git(root, ["worktree", "list", "--porcelain"]))).toContain(normalizedPath(result.worktreePath!));
  }, 60000);

  it("makes --check setup validation fail for invalid configs and unsafe worktree state", () => {
    const root = createRepository();
    const configDir = join(root, ".agents", "agents", "memory-architect");
    mkdirSync(configDir, { recursive: true });
    writeFileSync(join(configDir, "agent.json"), "{not json");
    git(root, ["add", ".agents"]);
    git(root, ["commit", "-m", "add invalid config"]);

    const invalidConfig = new MainAgentOrchestrator({ repoRoot: root, worktreesDir: worktreesDirectory(root) }).checkSetup();
    expect(invalidConfig.passed).toBe(false);
    expect(invalidConfig.issues.join(" ")).toMatch(/invalid JSON/i);

    writeFileSync(join(root, "uncommitted.txt"), "dirty\n");
    const unsafeIsolation = new MainAgentOrchestrator({ repoRoot: root, worktreesDir: worktreesDirectory(root) }).checkSetup();
    expect(unsafeIsolation.passed).toBe(false);
    expect(unsafeIsolation.issues.join(" ")).toMatch(/working tree.*dirty/i);
  }, 60000);
});
