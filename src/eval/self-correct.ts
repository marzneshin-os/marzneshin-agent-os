import type { MemoryProvider } from "../types.js";

const STRICTER_SUFFIX = `

IMPORTANT: Your previous response was invalid. Please ensure your output strictly follows the required XML format. Every required field must be present with valid values.`;

export async function compressWithRetry(
  provider: MemoryProvider,
  systemPrompt: string,
  userPrompt: string,
  validator: (response: string) => { valid: boolean; errors?: string[] },
  maxRetries = 1,
): Promise<{ response: string; retried: boolean }> {
  const first = await provider.compress(systemPrompt, userPrompt);
  const result = validator(first);
  if (result.valid) return { response: first, retried: false };

  for (let i = 0; i < maxRetries; i++) {
    const retry = await provider.compress(
      systemPrompt + STRICTER_SUFFIX,
      userPrompt,
    );
    const retryResult = validator(retry);
    if (retryResult.valid) return { response: retry, retried: true };
  }

  return { response: first, retried: true };
}

// === [NEXUS x HARNESS² V3 PROPOSE-PROBE-COMPOSE ENGINE] ===

export interface ValidationProbeResult {
  valid: boolean;
  score?: number;
  errors?: string[];
  behavioralDelta?: string[];
}

export interface HarnessExperienceEntry {
  cue: string;
  lesson: string;
  empiricalEvidence: string;
  timestamp: string;
}

export const INVARIANT_CANDIDATE_DIRECTIVE = `
[HARNESS² INVARIANT CANDIDATE (C_inv)]
Focus on structural, formatting, and protocol invariants:
1. Enforce strict XML/JSON schema completeness and tag closure.
2. Verify all required fields exist and remain non-empty.
3. Eliminate truncation, unescaped tokens, or malformed hierarchy.
`;

export const DOMAIN_CANDIDATE_DIRECTIVE = `
[HARNESS² DOMAIN CANDIDATE (C_dom)]
Focus on agentmemory domain semantics:
1. Preserve high-salience entity relationships, temporal anchors, and causal links.
2. Maintain factual fidelity to source session turns without hallucinated state.
3. Optimize density for hybrid BM25 + vector retrieval recall (R@5).
`;

/**
 * Harness² Level-1 Task Recursion: Propose -> Probe -> Compose
 * Evaluates parallel Invariant (C_inv) and Domain (C_dom) candidates before contrastive composition.
 */
export async function proposeProbeCompose(
  provider: MemoryProvider,
  systemPrompt: string,
  userPrompt: string,
  validator: (response: string) => ValidationProbeResult,
  experienceLessons: string[] = [],
  maxRounds = 2,
): Promise<{
  response: string;
  retried: boolean;
  roundsUsed: number;
  adoptedLesson?: HarnessExperienceEntry;
}> {
  const experienceBlock =
    experienceLessons.length > 0
      ? `\n[HARNESS² PRIOR EXPERIENCE LESSONS]\n${experienceLessons.map((l, i) => `${i + 1}. ${l}`).join("\n")}\n`
      : "";

  // Base Rollout
  const baseResponse = await provider.compress(
    systemPrompt + experienceBlock,
    userPrompt,
  );
  const baseProbe = validator(baseResponse);
  if (baseProbe.valid) {
    return { response: baseResponse, retried: false, roundsUsed: 0 };
  }

  let currentBestResponse = baseResponse;
  let currentBestProbe = baseProbe;

  for (let round = 1; round <= maxRounds; round++) {
    const errorContext = (currentBestProbe.errors ?? ["Validation failed"]).join("; ");

    // 1. PROPOSE & 2. PROBE (Parallel Invariant + Domain Candidates)
    const [invariantResponse, domainResponse] = await Promise.all([
      provider.compress(
        `${systemPrompt}${experienceBlock}\n${INVARIANT_CANDIDATE_DIRECTIVE}\nObserved Failure Trace: ${errorContext}`,
        userPrompt,
      ),
      provider.compress(
        `${systemPrompt}${experienceBlock}\n${DOMAIN_CANDIDATE_DIRECTIVE}\nObserved Failure Trace: ${errorContext}`,
        userPrompt,
      ),
    ]);

    const invProbe = validator(invariantResponse);
    const domProbe = validator(domainResponse);

    if (invProbe.valid && !domProbe.valid) {
      return {
        response: invariantResponse,
        retried: true,
        roundsUsed: round,
        adoptedLesson: {
          cue: errorContext,
          lesson: "Resolved via Invariant Harness Candidate (structural/schema enforcement).",
          empiricalEvidence: `Passed validator on round ${round} (C_inv valid=true, C_dom valid=false).`,
          timestamp: new Date().toISOString(),
        },
      };
    }
    if (domProbe.valid && !invProbe.valid) {
      return {
        response: domainResponse,
        retried: true,
        roundsUsed: round,
        adoptedLesson: {
          cue: errorContext,
          lesson: "Resolved via Domain Harness Candidate (agentmemory semantic fidelity).",
          empiricalEvidence: `Passed validator on round ${round} (C_dom valid=true, C_inv valid=false).`,
          timestamp: new Date().toISOString(),
        },
      };
    }
    if (invProbe.valid && domProbe.valid) {
      const chosen = (domProbe.score ?? 1) >= (invProbe.score ?? 1) ? domainResponse : invariantResponse;
      return {
        response: chosen,
        retried: true,
        roundsUsed: round,
        adoptedLesson: {
          cue: errorContext,
          lesson: "Both C_inv and C_dom passed validation; selected highest-scoring candidate.",
          empiricalEvidence: `Passed validator on round ${round} (both candidates valid).`,
          timestamp: new Date().toISOString(),
        },
      };
    }

    // 3. COMPOSE (Contrastive Synthesis of Both Candidates)
    const composePrompt = `${systemPrompt}${experienceBlock}
[HARNESS² CONTRASTIVE COMPOSER]
Synthesize a single valid output by combining the structural rigor of Candidate A (Invariant) with the domain completeness of Candidate B (Domain), eliminating all remaining errors.
- Base Errors: ${errorContext}
- Candidate A (Invariant) Errors: ${(invProbe.errors ?? []).join("; ") || "None"}
- Candidate B (Domain) Errors: ${(domProbe.errors ?? []).join("; ") || "None"}
- Candidate A Output:
${invariantResponse}
- Candidate B Output:
${domainResponse}`;

    const composedResponse = await provider.compress(composePrompt, userPrompt);
    const composedProbe = validator(composedResponse);

    if (composedProbe.valid) {
      return {
        response: composedResponse,
        retried: true,
        roundsUsed: round,
        adoptedLesson: {
          cue: errorContext,
          lesson: "Resolved via Contrastive Composition of Invariant + Domain candidates.",
          empiricalEvidence: `Passed validator after contrastive compose on round ${round}.`,
          timestamp: new Date().toISOString(),
        },
      };
    }

    currentBestResponse = composedResponse;
    currentBestProbe = composedProbe;
  }

  return {
    response: currentBestResponse,
    retried: true,
    roundsUsed: maxRounds,
  };
}
