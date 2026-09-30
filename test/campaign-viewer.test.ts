import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Viewer Campaign Canvas Tab", () => {
  const htmlPath = join(import.meta.dirname, "..", "src", "viewer", "index.html");
  const html = readFileSync(htmlPath, "utf-8");

  it("contains the Campaign Canvas tab button", () => {
    expect(html).toContain('data-tab="campaigns"');
    expect(html).toContain("Campaign Canvas");
  });

  it("contains the campaigns view container with 3 columns", () => {
    expect(html).toContain('id="view-campaigns"');
    expect(html).toContain("canvas-column");
    expect(html).toContain("Market Insights");
    expect(html).toContain("Campaign Strategy");
    expect(html).toContain("Creative Assets");
  });
});
