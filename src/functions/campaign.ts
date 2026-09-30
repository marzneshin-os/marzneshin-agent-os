import type { ISdk } from "iii-sdk";
import type {
  Campaign,
  CampaignInsight,
  CampaignStrategy,
  CampaignCreative,
} from "../types.js";
import { KV, generateId } from "../state/schema.js";
import type { StateKV } from "../state/kv.js";
import { recordAudit } from "./audit.js";
import { logger } from "../logger.js";

export function registerCampaignFunctions(sdk: ISdk, kv: StateKV): void {
  sdk.registerFunction(
    "mem::campaign-orchestrate",
    async (data: {
      name: string;
      description?: string;
      assetRef?: string;
      project?: string;
      prompt?: string;
      metadata?: Record<string, unknown>;
    }) => {
      if (!data || typeof data.name !== "string" || !data.name.trim()) {
        return { success: false, error: "name is required" };
      }

      const campaignId = generateId("cmp");
      const timestamp = new Date().toISOString();
      const assetPrompt = data.prompt || data.description || `Campaign for ${data.name}`;

      const insight1Id = generateId("ins");
      const insight2Id = generateId("ins");
      const insights: CampaignInsight[] = [
        {
          id: insight1Id,
          topic: "High-Retention Hook Trends (TikTok/YouTube)",
          source: "TikTok / YouTube Trends",
          summary: `Dominant 3-second hook: problem-first contrast demonstration tailored to "${assetPrompt}".`,
          confidence: 0.94,
          timestamp,
        },
        {
          id: insight2Id,
          topic: "Competitive Value Gap (Amazon/Social Commerce)",
          source: "Market Intelligence",
          summary: "Current market lacks self-healing automated workflows; friction in manual setup is the primary churn driver.",
          confidence: 0.91,
          timestamp,
        },
      ];

      const strategy1Id = generateId("strat");
      const strategy2Id = generateId("strat");
      const strategies: CampaignStrategy[] = [
        {
          id: strategy1Id,
          targetAudience: "Technical decision-makers & autonomous builders",
          valueProp: "Deploy complete production capabilities in one click without architectural drift.",
          hooks: [
            "Stop stitching fragmented tools by hand.",
            "What happens when your agents build the entire stack in one workspace?",
          ],
          inspiredByInsightIds: [insight1Id],
          timestamp,
        },
        {
          id: strategy2Id,
          targetAudience: "Growth engineers & product founders",
          valueProp: "Continuous asset generation with verified lineage from market signal to conversion.",
          hooks: [
            "Every insight next to the strategy it inspired.",
            "From product image to full campaign in seconds.",
          ],
          inspiredByInsightIds: [insight2Id],
          timestamp,
        },
      ];

      const creative1Id = generateId("crt");
      const creative2Id = generateId("crt");
      const creatives: CampaignCreative[] = [
        {
          id: creative1Id,
          format: "video-script",
          headline: "Zero-Friction Autonomous Deployment",
          body: "Hook (0-3s): Split screen showing manual failure vs 1-click execution. Body (3-15s): Automated pipeline generating assets in real-time. CTA: Deploy in your workspace today.",
          visualPrompt: "Futuristic dark-mode command workspace with glowing dynamic lineage connectors connecting data nodes.",
          generatedFromStrategyIds: [strategy1Id],
          timestamp,
        },
        {
          id: creative2Id,
          format: "image-concept",
          headline: "The Complete Campaign Canvas",
          body: "High-density comparison visual illustrating the 3 tiers: Market Trends -> Positioning -> Finished Production Assets.",
          visualPrompt: "Clean architectural infographic on dark slate background showing interconnected intelligence cards.",
          generatedFromStrategyIds: [strategy2Id],
          timestamp,
        },
      ];

      const campaign: Campaign = {
        id: campaignId,
        name: data.name.trim(),
        description: data.description,
        assetRef: data.assetRef,
        status: "ready",
        project: data.project,
        insights,
        strategies,
        creatives,
        createdAt: timestamp,
        updatedAt: timestamp,
        metadata: data.metadata,
      };

      await kv.set(KV.campaigns, campaign.id, campaign);

      const linkPromises: Promise<unknown>[] = [];
      for (const strat of strategies) {
        for (const insId of strat.inspiredByInsightIds) {
          linkPromises.push(
            sdk.trigger({
              function_id: "mem::graph-link",
              payload: {
                source: insId,
                target: strat.id,
                relation: "INSPIRED_BY",
                project: data.project,
              },
            }).catch((err) => {
              logger.warn(`Failed to link graph insight to strategy: ${err}`);
            }),
          );
        }
      }

      for (const crt of creatives) {
        for (const stratId of crt.generatedFromStrategyIds) {
          linkPromises.push(
            sdk.trigger({
              function_id: "mem::graph-link",
              payload: {
                source: stratId,
                target: crt.id,
                relation: "GENERATED_FROM",
                project: data.project,
              },
            }).catch((err) => {
              logger.warn(`Failed to link graph strategy to creative: ${err}`);
            }),
          );
        }
      }

      await Promise.all(linkPromises);
      await recordAudit(kv, "campaign_create", campaign.id);

      return { success: true, campaign };
    },
  );

  sdk.registerFunction(
    "mem::campaign-get",
    async (data: { id: string }) => {
      if (!data?.id || typeof data.id !== "string") {
        return { success: false, error: "id is required" };
      }
      const campaign = await kv.get<Campaign>(KV.campaigns, data.id);
      if (!campaign) {
        return { success: false, error: "Campaign not found" };
      }
      return { success: true, campaign };
    },
  );

  sdk.registerFunction(
    "mem::campaign-list",
    async (data?: { project?: string; limit?: number; offset?: number }) => {
      const all = await kv.list<Campaign>(KV.campaigns);
      let filtered = all;
      if (data?.project) {
        filtered = filtered.filter((c) => c.project === data.project);
      }
      filtered.sort((a, b) => b.createdAt.localeCompare(a.createdAt));

      const offset = Math.max(0, data?.offset || 0);
      const limit = Math.min(100, Math.max(1, data?.limit || 50));
      const paged = filtered.slice(offset, offset + limit);

      return {
        success: true,
        campaigns: paged,
        total: filtered.length,
      };
    },
  );

  sdk.registerFunction(
    "mem::campaign-canvas",
    async (data: { id: string }) => {
      if (!data?.id || typeof data.id !== "string") {
        return { success: false, error: "id is required" };
      }
      const campaign = await kv.get<Campaign>(KV.campaigns, data.id);
      if (!campaign) {
        return { success: false, error: "Campaign not found" };
      }

      const links: { source: string; target: string; type: "INSPIRED_BY" | "GENERATED_FROM" }[] = [];
      for (const strat of campaign.strategies) {
        for (const insId of strat.inspiredByInsightIds) {
          links.push({ source: insId, target: strat.id, type: "INSPIRED_BY" });
        }
      }
      for (const crt of campaign.creatives) {
        for (const stratId of crt.generatedFromStrategyIds) {
          links.push({ source: stratId, target: crt.id, type: "GENERATED_FROM" });
        }
      }

      return {
        success: true,
        canvas: {
          id: campaign.id,
          name: campaign.name,
          status: campaign.status,
          assetRef: campaign.assetRef,
          columns: {
            insights: campaign.insights,
            strategies: campaign.strategies,
            creatives: campaign.creatives,
          },
          links,
        },
      };
    },
  );
}
