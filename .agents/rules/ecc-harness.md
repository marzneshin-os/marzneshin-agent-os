# ECC Universal Agent Harness & AgentShield Security Rule

All agents operating in Marzneshin Agent OS must adhere to the Everything Claude Code (ECC) harness discipline:

1. **AgentShield Verification Before Commit**:
   - Before submitting changes, creating PRs, or completing tasks, verify that no raw secrets, prompt injections, or unsafe shell invocations were introduced.
   - Run: `python3 scripts/ecc_cli.py scan`.
   - Any CRITICAL or HIGH finding blocks completion.

2. **Instinct Memory Consultation**:
   - At the beginning of architectural planning or complex debugging, query learned instincts: `python3 scripts/ecc_cli.py instincts --query "<task>"`.
   - Never repeat settled architectural mistakes.

3. **Cross-Agentic Consistency**:
   - Maintain parity across all agent environments. No rule may contradict the Single Source of Truth (`BUILD-SPEC.md` v2.0).
