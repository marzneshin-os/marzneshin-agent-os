import { describe, it, expect, vi } from "vitest";
import { proposeProbeCompose, compressWithRetry } from "../src/eval/self-correct.js";
import type { MemoryProvider } from "../src/types.js";

describe("Harness² Contrastive Propose-Probe-Compose Engine", () => {
  it("returns base rollout immediately when initial response is valid", async () => {
    const provider: MemoryProvider = {
      name: "mock",
      compress: vi.fn().mockResolvedValue("<summary>valid base</summary>"),
    };
    const result = await proposeProbeCompose(
      provider,
      "sys",
      "user",
      (res) => ({ valid: res.includes("<summary>") }),
    );
    expect(result.retried).toBe(false);
    expect(result.roundsUsed).toBe(0);
    expect(result.response).toBe("<summary>valid base</summary>");
  });

  it("adopts Invariant Candidate (C_inv) when C_inv passes and C_dom fails", async () => {
    const compressMock = vi
      .fn()
      .mockResolvedValueOnce("malformed base")
      .mockResolvedValueOnce("<summary>fixed by C_inv</summary>")
      .mockResolvedValueOnce("still missing tags in C_dom");

    const provider: MemoryProvider = { name: "mock", compress: compressMock };
    const result = await proposeProbeCompose(
      provider,
      "sys",
      "user",
      (res) => ({
        valid: res.startsWith("<summary>") && res.endsWith("</summary>"),
        errors: ["Missing summary tags"],
      }),
    );

    expect(result.retried).toBe(true);
    expect(result.roundsUsed).toBe(1);
    expect(result.response).toBe("<summary>fixed by C_inv</summary>");
    expect(result.adoptedLesson?.lesson).toContain("Invariant Harness Candidate");
  });

  it("adopts Domain Candidate (C_dom) when C_dom passes and C_inv fails", async () => {
    const compressMock = vi
      .fn()
      .mockResolvedValueOnce("base missing entity")
      .mockResolvedValueOnce("<summary>empty</summary>")
      .mockResolvedValueOnce("<summary>entity:Marzneshin</summary>");

    const provider: MemoryProvider = { name: "mock", compress: compressMock };
    const result = await proposeProbeCompose(
      provider,
      "sys",
      "user",
      (res) => ({
        valid: res.includes("<summary>") && res.includes("entity:Marzneshin"),
        errors: ["Missing entity:Marzneshin"],
      }),
    );

    expect(result.retried).toBe(true);
    expect(result.roundsUsed).toBe(1);
    expect(result.response).toBe("<summary>entity:Marzneshin</summary>");
    expect(result.adoptedLesson?.lesson).toContain("Domain Harness Candidate");
  });

  it("synthesizes via Contrastive Composer when both candidates fail individually", async () => {
    const compressMock = vi
      .fn()
      .mockResolvedValueOnce("base fail")
      .mockResolvedValueOnce("<summary>structural only</summary>")
      .mockResolvedValueOnce("domain entity A->B without tags")
      .mockResolvedValueOnce("<summary>domain entity A->B</summary>");

    const provider: MemoryProvider = { name: "mock", compress: compressMock };
    const result = await proposeProbeCompose(
      provider,
      "sys",
      "user",
      (res) => ({
        valid: res.includes("<summary>") && res.includes("entity A->B"),
        errors: ["Requires both XML tag and entity A->B"],
      }),
    );

    expect(result.retried).toBe(true);
    expect(result.roundsUsed).toBe(1);
    expect(result.response).toBe("<summary>domain entity A->B</summary>");
    expect(result.adoptedLesson?.lesson).toContain("Contrastive Composition");
  });

  it("preserves backward compatibility via compressWithRetry", async () => {
    const provider: MemoryProvider = {
      name: "mock",
      compress: vi.fn().mockResolvedValue("ok"),
    };
    const res = await compressWithRetry(provider, "sys", "usr", () => ({ valid: true }));
    expect(res).toEqual({ response: "ok", retried: false });
  });
});
