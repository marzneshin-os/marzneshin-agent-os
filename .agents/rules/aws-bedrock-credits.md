# AWS Bedrock Promotional Credit Pool & Zero-Cost Guardrails (ADR-029)

Governs the usage of Amazon Bedrock foundation models and AWS Builder ID promotional credits within Marzneshin Agent OS.

## 1. Zero-Cost Core Principle
- Marzneshin operates strictly under `max_daily_usd: 0.0`.
- All AWS Bedrock executions must be funded exclusively via promotional credit grants ($100-$200 Builder ID grants).
- A mandatory **$5.00 safety buffer** is enforced: if an account's remaining credits reach $5.00 or lower, the account is automatically retired to prevent any pay-as-you-go billable charges.

## 2. Model Tiering & Pricing
- Primary Tier: `anthropic.claude-3-5-sonnet-20241022-v2:0` ($3/M in, $15/M out)
- High-Speed / Cost-Saving Tier: `anthropic.claude-3-5-haiku-20241022-v1:0` ($0.80/M in, $4/M out)
- Open-Weights Tier: `meta.llama3-3-70b-instruct-v1:0` ($0.72/M in, $0.72/M out)

## 3. Account Rotation & 6-Month Expiration Fence
- Promotional credits have a strict 180-day grant expiration date.
- The `BedrockCreditPoolManager` automatically filters out expired accounts and rotates to the active account with the highest remaining credit balance.

## 4. Onboarding Resource Teardown
- When completing the 5 Explore AWS onboarding exploration tasks (EC2, Bedrock, Lambda, RDS, Budget):
  - Any EC2 or RDS instances created must be terminated immediately.
  - An AWS Cost Budget with a $0.01 limit alert must be enabled.
