# ADR-025: Antigravity Account Doctor, Health Recovery & Eligibility Remediation Architecture

**Date:** 2026-10-09  
**Status:** Accepted  
**Author:** Executive Systems Architect & Autonomous Architecture Council  
**Workstream:** agentic-core / security-compliance / provider-resilience  
**Governing Standard:** BUILD-SPEC.md v2.0, ADR-001, ADR-022, ADR-024  

---

## 1. Context & Reference Analysis

A recent community reference (Ram Maheshwari / `@rammcodes`, Sep 30, 2026) highlighted the widespread emergence of **"not eligible"** and **403 Forbidden** errors in Google Antigravity and downstream proxies (e.g. 9router), pointing to an open-source tool (`fulldiagnose/antigravity-fixer`).

### Technical Analysis of the Problem & Reference:
1. **Core Symptoms**:
   - `Eligibility check failed: Your current account is not eligible for Antigravity.`
   - `There was an unexpected issue setting up your account. Your current account is not eligible for gemini code assist for individuals at this time.`
   - `403 Forbidden — VALIDATION_REQUIRED`
2. **Root Cause Analysis**:
   - **Stale / Corrupted Credentials**: Expired or desynchronized session tokens stored in OS credential vaults (`service: "gemini"`, `account: "antigravity"` on macOS Keychain, `Target: gemini / antigravity` on Windows Credential Manager).
   - **Account Type Restriction**: Google Workspace / managed organization accounts are rejected by Google for individual Antigravity tiers; only personal `@gmail.com` accounts are eligible.
   - **Age Verification Requirement**: Google requires mandatory age verification (`myaccount.google.com/age-verification`) before allowing agentic coding access.
   - **Filesystem Locks & Daemon Zombies**: Orphaned `.lock` files or hanging language server processes preventing fresh socket binds.
3. **Adversarial & Security Evaluation of the Reference Tool**:
   - **Unsafe Anti-Pattern (REJECTED)**: The reference tool prompts users for raw Google account passwords and uses a stealth headless browser (`camoufox`) to automate Google login. As verified in user feedback (`@james7l2m`), automated bot logins to Google accounts trigger risk scoring, 2FA/CAPTCHA challenges, and severe risk of permanent account bans.
   - **Production Primitives (ADOPTED & ADAPTED)**: Deterministic diagnostic checks, non-destructive OS credential purging without password handling, lockfile remediation, account domain classification, and official OAuth re-auth guidance.

---

## 2. Architectural Decisions

### D1: Core Shared Library (`scripts/lib/antigravity_doctor.py`)
- Standard library only (strictly compliant with `scripts/verify.py --lint-imports`).
- Clock-disciplined via `scripts.lib.clock` (`scripts/verify.py --lint-clock`).
- Never asks for Google passwords or performs headless browser scraping.
- Provides:
  - `diagnose()`: Comprehensive diagnostic matrix evaluating OS credential stores, token JSON, account domains, locks, and processes.
  - `clean()`: Target-specific credential store deletion and stale lock purging.
  - `repair()`: End-to-end recovery returning structured next-action instructions.
  - `check_eligibility()`: Real-time verification of email domain compatibility.

### D2: L0 System Adapter (`adapters/antigravity_doctor.py`)
- Inherits from `adapters.base.Adapter` (§4 / BUILD-SPEC v2.0).
- Exposes capabilities: `diagnose_account`, `clean_credentials`, `repair_environment`, `check_eligibility`, `get_auth_status`.
- Conforms to Circuit Breaker (5 failures -> 60s cooldown) and IdempotencyStore.
- Authentic `dry_run` support.
- Accompanied by simulation fake (`sim/fakes/antigravity_doctor.py`) passing all 9 contract checks in `adapters/contract.py`.

### D3: Autonomous CLI & Multi-Agent MCP Server (`scripts/antigravity_doctor_cli.py` & `scripts/mcp_antigravity_doctor.py`)
- `scripts/antigravity_doctor_cli.py`: Interactive and JSON-mode CLI for operator or agent execution.
- `scripts/mcp_antigravity_doctor.py`: Zero-dependency JSON-RPC 2.0 stdio MCP server registered in root `.mcp.json`.
- Enables Antigravity IDE, Claude Code, Cursor, OpenCode, and Windsurf to self-diagnose and repair authentication failures autonomously.

### D4: Integration with `antigravity-account-switcher`
- Extends existing `antigravity-account-switcher/switcher_core.py` with `--doctor`, `--clean`, `--repair` CLI flags and GUI Doctor menu item.
- Extends `antigravity-account-switcher/switcher_windows.ps1` with `-Doctor`, `-Clean`, `-Repair` flags and WinForms Doctor button.

---

## 3. Verification & Governance
- 100% test coverage via `tests/test_antigravity_doctor.py` and `tests/test_antigravity_doctor_adapter.py`.
- Strict passing of all 6 CI verification gates in `scripts/verify.py`.
