---
name: antigravity-doctor
description: Google Antigravity Account Doctor, Eligibility Remediation & 403 Forbidden Diagnostic Engine.
metadata:
  origin: rammcodes-antigravity-fixer-adr-025
---

# Google Antigravity Account Doctor & Health Recovery

Use this skill when encountering Google Antigravity or 9router authentication errors, "Account not eligible" failures, 403 Forbidden status, or stale OS credential manager entries.

## Core Capabilities

1. **Diagnostic Matrix (`diagnose`)**:
   - Evaluates OS credential stores (Windows Credential Manager / macOS Keychain / Linux Secret Service).
   - Validates session token JSON structure, format, and expiry timestamp.
   - Detects Google Workspace domain incompatibility (@company.com vs personal @gmail.com).
   - Scans for stale filesystem lockfiles and zombie agent daemon processes.
   - Run diagnosis: `python3 scripts/antigravity_doctor_cli.py diagnose`.
   - MCP tool: `antigravity_diagnose`.

2. **Safe Credential Cleaner (`clean`)**:
   - Target-specific removal of `gemini`, `antigravity`, and `agy` credentials without prompting for Google passwords or running headless browser bots.
   - Purges stale `.lock` files.
   - Run clean: `python3 scripts/antigravity_doctor_cli.py clean`.
   - MCP tool: `antigravity_clean_credentials`.

3. **Complete Environment Repair (`repair`)**:
   - Terminates zombie processes, purges stale credentials and locks, and returns step-by-step re-auth instructions.
   - Run repair: `python3 scripts/antigravity_doctor_cli.py repair`.
   - MCP tool: `antigravity_repair`.

4. **Eligibility & Age Verification Guidance**:
   - Direct link to official Google Age Verification: `https://myaccount.google.com/age-verification`
   - Direct link to Google One Family Sharing: `https://families.google.com/`
   - Email domain check: `python3 scripts/antigravity_doctor_cli.py check-email <email>`.
   - MCP tool: `antigravity_check_eligibility`.

## Operating Procedure on 403 / Ineligible Error:
1. Run diagnosis: `python3 scripts/antigravity_doctor_cli.py diagnose`.
2. If domain is Google Workspace, instruct operator to switch to personal `@gmail.com`.
3. If age verification is needed, direct user to `https://myaccount.google.com/age-verification`.
4. If token is corrupt or expired, run `python3 scripts/antigravity_doctor_cli.py clean` and re-authenticate via official `agy` CLI Option 1.
