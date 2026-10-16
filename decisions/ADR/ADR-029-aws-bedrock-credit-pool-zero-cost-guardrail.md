# ADR-029: AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrail Engine Architecture

**Date:** 2026-10-11  
**Status:** Accepted  
**Author:** Executive Systems Architect, Principal Engineer & Autonomous Architecture Council  
**Workstream:** agentic-core / provider-resilience / zero-cost-governance  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-001, ADR-022, ADR-025, ADR-027, ADR-028  

---

## 1. Context & Reference Analysis

A verified community reference from October 10, 2026 (`@TheMaran` on X, `https://x.com/TheMaran/status/2108870626404655297`) revealed a high-value cloud onboarding mechanism:
- Developers and builders can obtain **up to $200 in AWS promotional credits for $0** with no credit card required for new accounts via the AWS Builder ID signup portal.
- **$100 instant credits** are provisioned immediately upon project creation.
- **An additional $100 credits** are unlocked by completing 5 Explore AWS exploration tasks:
  1. Launch an EC2 instance (~$20 credit value)
  2. Try a model in Amazon Bedrock (~$20 credit value)
  3. Deploy a serverless Lambda application (~$20 credit value)
  4. Create an RDS database (~$20 credit value)
  5. Configure an AWS Cost Budget (~$20 credit value)
- **Rules & Constraints**:
  - Credits expire in 6 months (180 days) or when fully spent.
  - Free plan accounts incur zero charges while within credit grant limits.
  - Overrun into pay-as-you-go or account suspension risks occur if credits hit zero or terms are violated.

### Technical Value for Marzneshin Agent OS:
1. **Premier Foundation Model Capacity at Zero Cost**:
   Amazon Bedrock hosts premier models:
   - `anthropic.claude-3-5-sonnet-20241022-v2:0` ($3/M input, $15/M output)
   - `anthropic.claude-3-7-sonnet-20250219-v1:0`
   - `anthropic.claude-3-5-haiku-20241022-v1:0` ($0.80/M input, $4/M output)
   - `meta.llama3-3-70b-instruct-v1:0` ($0.72/M input, $0.72/M output)
   - `mistral.mistral-large-2407-v1:0` ($2/M input, $6/M output)
   A $200 promotional grant per account yields ~11M to 50M high-throughput tokens with enterprise-grade SLA.
2. **The Zero-Cost Mandate Challenge**:
   In Marzneshin Agent OS, the governing constraint is `max_daily_usd: 0.0`. If promotional credits deplete completely, cloud providers may bill default payment methods or enter pay-as-you-go status.
   Therefore, an automated **Zero-Cost Safety Buffer Guardrail** ($5.00 fail-closed threshold) and **6-Month Expiration Fence** are required to guarantee that no billable overruns ever occur.
3. **Resource Teardown Governance**:
   Tasks like EC2 and RDS must be automatically cleaned up / terminated immediately after completion verification so they do not incur standing infrastructure charges that burn credits intended for LLM reasoning.

---

## 2. Architectural Decisions

### D1: Core Shared Library (`scripts/lib/aws_bedrock_credits.py`)
- Pure Python standard library only (`scripts/verify.py --lint-imports` compliant).
- Virtual clock disciplined via `scripts.lib.clock` (`scripts/verify.py --lint-clock` compliant).
- Implements:
  - `BedrockModelPricing`: Accurate token cost calculation per 1M tokens for Claude 3.5 Sonnet, Llama 3.3, Mistral, and Titan.
  - `BedrockAccount`: Encapsulates account ID, alias, credentials (with automatic `[REDACTED]` masking), initial grant, spent USD, remaining USD, and expiration timestamp.
  - `BedrockCreditPoolManager`:
    - Zero-Cost Safety Buffer: Automatically marks accounts as `depleted` when `remaining_usd <= $5.00`, retiring them before zero-balance rollover.
    - Expiration Fencing: Marks accounts as `expired` when `clock.now() >= expires_at`.
    - Multi-Account Rotation: Selects active account using credit-weighted priority (highest balance first).
    - Task Checklist & Teardown Verification: Tracks completion of the 5 onboarding tasks with verified teardown of temporary compute/database instances.

### D2: Provider Catalog & Routing Integration
- Extended `PROVIDER_CATALOG` in `scripts/lib/freellm_pool.py` with `aws_bedrock` (100M monthly tokens capacity).
- Added `aws_bedrock` to `FALLBACK_LADDERS` in `SmartFallbackRouter` for `coding` and `reasoning`.
- Registered `aws_bedrock` pool in `configs/keys_pool.json`.
- Added `aws-bedrock-pool` combo in `configs/router.json`, and prepended Bedrock Claude 3.5 Sonnet to `smart`, `freellm-coding`, and `freellm-reasoning`.

### D3: L0 System Adapter & Simulation Fake (`adapters/aws_bedrock.py`, `sim/fakes/aws_bedrock.py`)
- Conforms strictly to BUILD-SPEC.md §4 Adapter protocol:
  - `CircuitBreaker` (5 consecutive failures -> 60s cooldown).
  - `IdempotencyStore` (`forever`, `scoped`, `none`).
  - Strict `dry_run` support (calculates predicted cost without mutating credit ledger).
  - Virtual time deadline remaining checks.
- Accompanied by simulation fake in `sim/fakes/aws_bedrock.py`.
- Verified by `adapters/contract.py` running all 9 contract invariants with 100% pass rate.

### D4: Autonomous CLI & Multi-Agent MCP Server (`scripts/aws_bedrock_cli.py`, `scripts/mcp_aws_bedrock.py`)
- `scripts/aws_bedrock_cli.py`: Subcommands `status`, `register`, `rotate`, `onboarding`, `invoke`.
- `scripts/mcp_aws_bedrock.py`: Zero-dependency JSON-RPC 2.0 stdio server registered in root `.mcp.json`.
- MCP Tools exposed:
  - `bedrock_credit_status`: Real-time account balances, expiration telemetry, and zero-cost safety buffer status.
  - `bedrock_invoke_model`: Invokes foundation models with automatic token cost deduction.
  - `bedrock_rotate_account`: Switches active account.
  - `bedrock_onboarding_checklist`: Tracks and claims the 5 Explore AWS exploration tasks.

---

## 3. System Thinking & Data Flow Map

```text
External AWS Promotion ($100-$200 Builder ID Grant)
                    │
                    ▼
   [BedrockCreditPoolManager (vault.json)]
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
[Account Status] [Expiration Fence] [Zero-Cost Guardrail]
(Active / Cool)  (<= 180 Days)      (Remaining > $5.00 Buffer)
   │                │                │
   └────────────────┼────────────────┘
                    │
                    ▼
     [AWSBedrockAdapter (L0 System Adapter)]
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
[CircuitBreaker] [Idempotency]  [Dry Run / Pricing]
   │                │                │
   └────────────────┼────────────────┘
                    │
                    ▼
 [Multi-Agent Runtimes (Antigravity, Claude, Cursor, OpenCode)]
        │                                    │
        ▼                                    ▼
[MCP Server (.mcp.json)]           [Router Server (router.json)]
```

---

## 4. Verification Evidence & Quality Gates

1. **Unit Test Suite**:
   - `tests/test_aws_bedrock_credits.py`: 7/7 PASSED (100%).
   - `tests/test_aws_bedrock_adapter.py`: 7/7 PASSED (100%).
2. **Adapter Contract Suite**:
   - Both `AWSBedrockFake` and `AWSBedrockAdapter` passed all checks in `adapters/contract.py` (healthz, capabilities, execution, unknown op refused, forever idempotency, dry run isolation, rollback).
3. **Repository Verification**:
   - `scripts/verify.py`: 6/6 checks GREEN (`lint-imports` and `lint-clock` verified).
4. **Router & FreeLLM Pool Compatibility**:
   - `tests/test_freellm_pool.py`: 5/5 PASSED.
   - `tests/test_router.py`: 13/13 PASSED.

---

## 5. Security & Operational Safety

- **Zero-Cost Guarantee**: All accounts are permanently guarded by a fail-closed $5.00 safety buffer. If credit balance drops to or below $5.00, the account is immediately retired and the router fails closed to free fallback providers, preventing billable charges.
- **Credential Protection**: AWS Secret Access Keys and session tokens are strictly masked (`[REDACTED]`) in all CLI outputs, JSON summaries, and MCP tool responses.
- **Resource Teardown**: The onboarding task checklist requires verification that test compute and database resources are terminated, ensuring 100% of promotional credits are reserved for foundation model inference.
