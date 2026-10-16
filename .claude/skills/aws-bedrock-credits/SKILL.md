---
name: aws-bedrock-credits
description: Manage AWS Bedrock promotional credit accounts, execute models at zero cost, and enforce budget guardrails.
---

# AWS Bedrock Promotional Credit Pool & Zero-Cost Engine

Use this skill when dispatching reasoning or coding tasks to Amazon Bedrock models (Claude 3.5 Sonnet, Llama 3.3, Mistral) or managing promotional credit accounts ($100-$200 Builder ID grants).

## Available Commands & MCP Tools

### 1. Check Pool Status & Remaining Credits
```bash
python3 scripts/aws_bedrock_cli.py status
```
Or call MCP tool `bedrock_credit_status`.

### 2. Invoke Foundation Models with Credit Deduction
```bash
python3 scripts/aws_bedrock_cli.py invoke --prompt "Explain the architecture" --model anthropic.claude-3-5-sonnet-20241022-v2:0
```
Or call MCP tool `bedrock_invoke_model`.

### 3. Check / Complete Onboarding Tasks
```bash
python3 scripts/aws_bedrock_cli.py onboarding --task bedrock --complete
```
Or call MCP tool `bedrock_onboarding_checklist`.

## Safety Constraints
1. Never bypass the $5.00 safety buffer.
2. Confirm test EC2 and RDS instances are deleted immediately to avoid draining credits.
