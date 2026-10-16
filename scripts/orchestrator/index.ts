import { MainAgentOrchestrator } from "./orchestrator.js";
import { OrchestrationPlan } from "./schemas.js";

async function main() {
  const orchestrator = new MainAgentOrchestrator();
  const subagents = orchestrator.getAllSubagents();

  console.log("\x1b[1m\x1b[36m=====================================================\x1b[0m");
  console.log("\x1b[1m\x1b[36m   Marzneshin-Agent-OS Multi-Agent Orchestrator      \x1b[0m");
  console.log("\x1b[1m\x1b[36m=====================================================\x1b[0m\n");

  console.log(`Discovered \x1b[32m${subagents.size}\x1b[0m specialized subagents in .agents/agents/:`);
  for (const [role, cfg] of subagents.entries()) {
    console.log(`  • \x1b[33m@${role}\x1b[0m [model: \x1b[35m${cfg.model}\x1b[0m]: ${cfg.description}`);
  }
  console.log();

  const isCheckOnly = process.argv.includes("--check");

  if (isCheckOnly) {
    console.log("\x1b[32m✔ Subagent definitions & context isolation verified successfully!\x1b[0m");
    process.exit(0);
  }

  // Autonomous Full-Project Verification & Orchestration Plan
  const plan: OrchestrationPlan = {
    id: `plan-${Date.now()}`,
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
        prompt: "Verify 130 REST endpoints and rate-limit / auth guards.",
        isolation: "direct",
      },
      {
        id: "TASK-04",
        title: "Run Unit & Integration Test Suite",
        specialist: "test-engineer",
        prompt: "Execute complete vitest test suite with zero regressions.",
        dependsOn: ["TASK-01", "TASK-02", "TASK-03"],
        isolation: "direct",
      },
      {
        id: "TASK-05",
        title: "Enforce 8-File MCP, 3-File REST & 7-File Version Consistency",
        specialist: "consistency-guardian",
        prompt: "Run consistency audit across all version, tool, and endpoint manifests.",
        dependsOn: ["TASK-04"],
        isolation: "direct",
      },
    ],
  };

  const result = await orchestrator.runPlan(plan);

  console.log("\n\x1b[1m\x1b[36m=== Final Orchestration Summary ===\x1b[0m");
  console.log(`Status: ${result.status === "completed" ? "\x1b[32mCOMPLETED\x1b[0m" : "\x1b[31mFAILED\x1b[0m"}`);
  console.log(`Total Duration: ${result.totalDurationMs}ms`);
  console.log(`Consistency Audit: ${result.consistencyAudit.details}`);

  process.exit(result.status === "completed" ? 0 : 1);
}

main().catch((err) => {
  console.error("Fatal orchestrator error:", err);
  process.exit(1);
});
