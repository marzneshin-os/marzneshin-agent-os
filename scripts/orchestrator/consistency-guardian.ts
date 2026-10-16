import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { getAllTools } from "../../src/mcp/tools-registry.js";
import { VERSION } from "../../src/version.js";

const ROOT = join(import.meta.dirname, "../..");

function readText(rel: string): string {
  return readFileSync(join(ROOT, rel), "utf-8");
}

export interface ConsistencyResult {
  passed: boolean;
  category: "MCP" | "REST" | "VERSION";
  file: string;
  rule: string;
  details?: string;
}

export function runConsistencyAudit(): { passed: boolean; results: ConsistencyResult[] } {
  const results: ConsistencyResult[] = [];
  const tools = getAllTools();
  const toolCount = tools.length;
  const pkg = JSON.parse(readText("package.json"));
  const currentVersion = pkg.version;

  // 1. Version checks (7 files)
  results.push({
    passed: VERSION === currentVersion,
    category: "VERSION",
    file: "src/version.ts",
    rule: "VERSION constant matches package.json",
    details: `src/version.ts: ${VERSION} vs package.json: ${currentVersion}`,
  });

  const pluginClaude = JSON.parse(readText("plugin/.claude-plugin/plugin.json"));
  results.push({
    passed: pluginClaude.version === currentVersion,
    category: "VERSION",
    file: "plugin/.claude-plugin/plugin.json",
    rule: "plugin.json version matches package.json",
    details: `plugin: ${pluginClaude.version} vs package: ${currentVersion}`,
  });

  if (existsSync(join(ROOT, "plugin/plugin.json"))) {
    const pluginRoot = JSON.parse(readText("plugin/plugin.json"));
    results.push({
      passed: pluginRoot.version === currentVersion,
      category: "VERSION",
      file: "plugin/plugin.json",
      rule: "plugin/plugin.json version matches package.json",
      details: `pluginRoot: ${pluginRoot.version} vs package: ${currentVersion}`,
    });
  }

  if (existsSync(join(ROOT, "packages/mcp/package.json"))) {
    const pkgMcp = JSON.parse(readText("packages/mcp/package.json"));
    results.push({
      passed: pkgMcp.version === currentVersion,
      category: "VERSION",
      file: "packages/mcp/package.json",
      rule: "packages/mcp version matches root package.json",
      details: `packages/mcp: ${pkgMcp.version} vs root: ${currentVersion}`,
    });
  }

  const exportImport = readText("src/functions/export-import.ts");
  results.push({
    passed: exportImport.includes(`"${currentVersion}"`),
    category: "VERSION",
    file: "src/functions/export-import.ts",
    rule: "supportedVersions includes current version",
  });

  const exportImportTest = readText("test/export-import.test.ts");
  results.push({
    passed: exportImportTest.includes("expect(result.version).toBe(VERSION)") || exportImportTest.includes(currentVersion),
    category: "VERSION",
    file: "test/export-import.test.ts",
    rule: "test verifies current version import/export with VERSION import",
  });

  // 2. MCP Tools checks (8 files)
  const serverCode = readText("src/mcp/server.ts");
  const missingInServer: string[] = [];
  for (const t of tools) {
    if (!serverCode.includes(`case "${t.name}":`)) {
      missingInServer.push(t.name);
    }
  }
  results.push({
    passed: missingInServer.length === 0,
    category: "MCP",
    file: "src/mcp/server.ts",
    rule: "All tools have switch cases in server.ts",
    details: missingInServer.length ? `Missing cases: ${missingInServer.join(", ")}` : "All 54 cases present",
  });

  const readme = readText("README.md");
  results.push({
    passed: readme.includes(`${toolCount} MCP tools`),
    category: "MCP",
    file: "README.md",
    rule: `README advertises ${toolCount} MCP tools`,
  });

  const toolConsistencyTest = readText("test/tool-count-consistency.test.ts");
  results.push({
    passed: toolConsistencyTest.includes(`const EXPECTED_TOOL_COUNT = ${toolCount};`),
    category: "MCP",
    file: "test/tool-count-consistency.test.ts",
    rule: `Tool count test asserts exactly ${toolCount} tools`,
  });

  // 3. REST Endpoint checks (3 files)
  const apiSrc = readText("src/triggers/api.ts");
  const endpointCount = Array.from(apiSrc.matchAll(/api_path:\s*["`]/g)).length;

  results.push({
    passed: readme.includes(`${endpointCount} endpoints on port`),
    category: "REST",
    file: "README.md",
    rule: `README documents ${endpointCount} REST endpoints`,
  });

  const indexSrc = readText("src/index.ts");
  results.push({
    passed: indexSrc.includes(`REST API: ${endpointCount} endpoints`),
    category: "REST",
    file: "src/index.ts",
    rule: `src/index.ts log line reports ${endpointCount} endpoints`,
  });

  const agentsMd = readText("AGENTS.md");
  results.push({
    passed: agentsMd.includes(`${endpointCount} REST endpoints`),
    category: "REST",
    file: "AGENTS.md",
    rule: `AGENTS.md reports ${endpointCount} REST endpoints`,
  });

  const allPassed = results.every((r) => r.passed);
  return { passed: allPassed, results };
}

if (process.argv[1] && process.argv[1].endsWith("consistency-guardian.ts")) {
  console.log("\x1b[1m\x1b[36m=== AgentMemory Consistency Guardian Audit ===\x1b[0m\n");
  const { passed, results } = runConsistencyAudit();
  for (const r of results) {
    const icon = r.passed ? "\x1b[32m✔\x1b[0m" : "\x1b[31m✖\x1b[0m";
    console.log(`${icon} [${r.category}] \x1b[33m${r.file}\x1b[0m: ${r.rule}`);
    if (!r.passed && r.details) {
      console.log(`    \x1b[31mDetails: ${r.details}\x1b[0m`);
    }
  }
  console.log("\n" + (passed ? "\x1b[32m✔ ALL CONSISTENCY CHECKS PASSED!\x1b[0m" : "\x1b[31m✖ CONSISTENCY AUDIT FAILED!\x1b[0m"));
  process.exit(passed ? 0 : 1);
}
