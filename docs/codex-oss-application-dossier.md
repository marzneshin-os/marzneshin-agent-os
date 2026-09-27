# 📝 Official Application Dossier: OpenAI Codex for Open Source Program
## Application for Marzneshin Agent OS (agentmemory)

> **Application Portal:** [https://developers.openai.com/community/codex-for-oss](https://developers.openai.com/community/codex-for-oss)  
> **Target Benefits:**  
> 1. Six months of ChatGPT Pro with Codex  
> 2. API credits through the Codex Open Source Fund ($1,000,000 Fund)  
> 3. Conditional access to Codex Security for core repository protection  

---

### 1. General Project Information
- **Project Name:** Marzneshin Agent OS (`agentmemory`)
- **Primary Repository:** `https://github.com/marzneshin-os/marzneshin-agent-os`
- **License:** MIT License (Open Source)
- **Primary Programming Languages:** Python 3.11+, TypeScript, Node.js (ESM), Shell
- **Core Maintainer / Applicant GitHub Username:** `PeymanBozorgnezhad`
- **Maintainer Role:** Core Maintainer & Lead Architect (with write & admin access)

---

### 2. Project Overview & Ecosystem Significance
**Question: What does your project do and why is it important to the open-source ecosystem?**

> **Application Response:**
> Marzneshin Agent OS (`agentmemory`) is an open-source, resilient multi-agent operating system and persistent memory framework designed for AI coding agents. Built on deterministic state machines, three-primitive orchestration (Worker / Function / Trigger), and rigorous safety invariants, it solves the critical problem of agent memory decay, hallucinated regressions, and uncoordinated multi-agent execution.
>
> The project provides:
> 1. **Persistent Context & Agent Memory:** Over 54 MCP tools and 130 REST endpoints enabling agents (such as Claude Code, OpenAI Codex, Antigravity, and Cline) to store, recall, and crystallize knowledge across long-running sessions.
> 2. **Two-Key Cryptographic Governance:** An unforgeable audit trail that links every agentic code change from genesis using SHA256 receipts, ensuring AI agents cannot introduce silent vulnerabilities or overwrite safety barriers.
> 3. **Ecosystem Tool Interoperability:** Native MCP (Model Context Protocol) adapters connecting modern developer environments with local and cloud LLM runtimes.
>
> Open source developers rely on our framework to run autonomous coding workflows without context exhaustion, making software maintenance scalable for individual maintainers and distributed teams.

---

### 3. How Codex Will Be Used in Project Workflows
**Question: How will your team use Codex, ChatGPT Pro, and the requested API credits?**

> **Application Response:**
> We have engineered dedicated OpenAI Codex workflows directly into our repository architecture (`.codex/` and `.github/workflows/`):
> 
> 1. **Automated Pull Request Review & Invariant Checking:**
>    - Every pull request triggers our `codex-oss-pr-review.yml` workflow.
>    - Codex acts as an independent reviewer analyzing diffs against Karpathy guidelines (simplicity, surgical changes, think before coding).
>    - Codex evaluates test evidence and verifies machine-checkable invariants (`verify.py --all`) before granting sign-off.
>
> 2. **Autonomous Maintainer Issue Triage:**
>    - Using `codex-maintainer-automation.yml`, maintainers can trigger `@codex` to reproduce bugs, formulate hypotheses, write surgical patches, and execute the test suite in an isolated CI container.
>
> 3. **Codex Security Deep Code Audits:**
>    - Access to Codex Security will allow us to audit token endpoints, localhost IPC sockets, and cryptographic state stores for potential vulnerabilities or privilege escalations before every release.
>
> 4. **API Credit Utilization:**
>    - API credits from the Codex Open Source Fund will directly power our automated CI/CD PR testing loops, regression simulation runs (`scripts/sim.py`), and background code health monitors, removing financial friction from our autonomous engineering pipeline.

---

### 4. Technical Architecture & Safety Alignment
**Question: How does your project ensure safe and responsible use of AI code generation?**

> **Application Response:**
> Our architecture enforces strict **Separation of Duties** and the **Two-Key Verification Contract** (BUILD-SPEC.md v2.0):
> - **No Self-Approval:** The agent authoring code cannot approve its own Pull Request. A dedicated Adversarial Reviewer agent with an independent lineage audits the diff.
> - **Pre-Flight Invariant Gates:** No PR can be merged without passing `scripts/verify.py`, which validates cryptographic receipt continuity from genesis (Invariant I15), strict schema adherence (Invariant I3), and comprehensive test execution (Invariant I11).
> - **Minimal Privileges & Sandboxing:** All local daemon processes bind strictly to `127.0.0.1`, and network access is tightly sandboxed during test execution.

---

### 5. Summary of Requested Grant Tier
- **ChatGPT Pro Access:** 1 Maintainer Seat (6 Months / 1 Year) for high-reasoning triage (`o3-mini`, `gpt-4o`).
- **Codex Open Source Fund API Credits:** $1,000 – $2,500 in platform credits to support automated CI/CD execution and developer community pull requests.
- **Codex Security Access:** Enabled on repository `marzneshin/marzneshin-agent-os`.
