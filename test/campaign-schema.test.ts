import { describe, it, expect } from "vitest";
import { KV } from "../src/state/schema.js";
import type {
  Campaign,
  CampaignInsight,
  CampaignStrategy,
  CampaignCreative,
} from "../src/types.js";

describe("Campaign Schema & Types", () => {
  it("defines KV.campaigns scope", () => {
    expect((KV as Record<string, string>).campaigns).toBe("mem:campaigns");
  });

  it("verifies campaign structure types compile correctly", () => {
    const insight: CampaignInsight = {
      id: "ins-1",
      topic: "Short-form video retention",
      source: "TikTok/YouTube",
      summary: "3-second hook pattern",
      confidence: 0.95,
      timestamp: new Date().toISOString(),
    };
    const strategy: CampaignStrategy = {
      id: "strat-1",
      targetAudience: "Engineers & DevOps",
      valueProp: "Zero configuration deployment",
      hooks: ["Stop debugging configs manually"],
      inspiredByInsightIds: ["ins-1"],
      timestamp: new Date().toISOString(),
    };
    const creative: CampaignCreative = {
      id: "crt-1",
      format: "video-script",
      headline: "How to deploy in 60s",
      body: "Scene 1: terminal opens...",
      visualPrompt: "A sleek dark IDE window",
      generatedFromStrategyIds: ["strat-1"],
      timestamp: new Date().toISOString(),
    };
    const campaign: Campaign = {
      id: "cmp-1",
      name: "Launch Campaign",
      assetRef: "assets/sample.png",
      status: "ready",
      insights: [insight],
      strategies: [strategy],
      creatives: [creative],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    expect(campaign.id).toBe("cmp-1");
    expect(campaign.insights.length).toBe(1);
    expect(campaign.strategies.length).toBe(1);
    expect(campaign.creatives.length).toBe(1);
  });
});
