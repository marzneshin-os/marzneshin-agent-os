import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Viewer Fast Inference Monitor Tab", () => {
  const htmlPath = join(import.meta.dirname, "..", "src", "viewer", "index.html");
  const html = readFileSync(htmlPath, "utf-8");

  it("contains the Fast Inference tab button", () => {
    expect(html).toContain('data-tab="inference"');
    expect(html).toContain("Fast Inference");
  });

  it("contains the fast inference view container with channel metrics and latency indicators", () => {
    expect(html).toContain('id="view-inference"');
    expect(html).toContain("Fast Inference Acceleration Layer");
    expect(html).toContain("Inference Channels");
    expect(html).toContain("Run Speed Benchmark");
    expect(html).toContain("Circuit Breaker Status");
  });
});
