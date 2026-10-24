import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { MainAgentOrchestrator } from "./orchestrator.js";
import { OrchestrationPlan } from "./schemas.js";

export async function main(args: string[] = process.argv.slice(2)): Promise<void> {
  const orchestrator = new MainAgentOrchestrator();
  const subagents = orchestrator.getAllSubagents();

  console.log("\x1b[1m\x1b[36m=====================================================\x1b[0m");
  console.log("\x1b[1m\x1b[36m   Marzneshin-Agent-OS Multi-Agent Orchestrator      \x1b[0m");
  console.log("\x1b[1m\x1b[36m=====================================================\x1b[0m\n");

  console.log("Discovered " + subagents.size + " valid specialist configs in .agents/agents/:");
  for (const [role, config] of subagents.entries()) {
    console.log("  • @" + role + " [model: " + config.model + "]: " + config.description);
  }
  console.log();

  if (args.includes("--check")) {
    const check = orchestrator.checkSetup();
    console.log("Checked " + check.discoveredSubagents + " valid specialist configuration(s).");
    if (check.issues.length) {
      for (const issue of check.issues) {
        console.error("\x1b[31m✖ " + issue + "\x1b[0m");
      }
      console.error("\x1b[31m✖ Orchestrator setup is not safe to run.\x1b[0m");
      process.exitCode = 1;
    } else {
      console.log("\x1b[32m✔ Specialist configs and worktree prerequisites verified.\x1b[0m");
      process.exitCode = 0;
    }
    return;
  }

  const plan: OrchestrationPlan = {
    id: "plan-" + Date.now(),
    goal: "Verify and orchestrate marzneshin-agent-os across all 15 architectural layers",
    createdAt: new Date().toISOString(),
    tasks: [
      {
        id: "TASK-01",
        title: "Verify Core Memory & State Function Integrity",
        specialist: "memory-architect",
        prompt: "Audit core KV functions, schemas, and vector index configurations.",
        isolation: "direct",
      },
      {
        id: "TASK-02",
        title: "Verify MCP Tools & Endpoint Registration",
        specialist: "mcp-tool-builder",
        prompt: "Audit MCP tool definitions and server dispatch cases.",
        isolation: "direct",
      },
      {
        id: "TASK-03",
        title: "Verify REST API Triggers & Auth Guards",
        specialist: "api-endpoint-builder",
        prompt: "Verify REST endpoints and rate-limit / auth guards.",
        isolation: "direct",
      },
      {
        id: "TASK-04",
        title: "Run Unit & Integration Test Suite",
        specialist: "test-engineer",
        prompt: "Execute the configured Vitest suite and report its exit status.",
        dependsOn: ["TASK-01", "TASK-02", "TASK-03"],
        isolation: "direct",
      },
      {
        id: "TASK-05",
        title: "Run the configured consistency audit",
        specialist: "consistency-guardian",
        prompt: "Run the built-in consistency audit and report every check accurately.",
        dependsOn: ["TASK-04"],
        isolation: "direct",
      },
    ],
  };

  const result = await orchestrator.runPlan(plan);
  console.log("\n\x1b[1m\x1b[36m=== Final Orchestration Summary ===\x1b[0m");
  console.log("Status: " + (result.status === "completed" ? "\x1b[32mCOMPLETED\x1b[0m" : "\x1b[31mFAILED\x1b[0m"));
  console.log("Total Duration: " + result.totalDurationMs + "ms");
  console.log("Consistency Audit: " + result.consistencyAudit.details);
  process.exitCode = result.status === "completed" ? 0 : 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error("Fatal orchestrator error:", error);
    process.exitCode = 1;
  });
}
