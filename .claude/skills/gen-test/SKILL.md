---
name: gen-test
description: Generate unit or integration tests adhering to Marzneshin Agent OS test standards. Use when creating tests for a module or script.
disable-model-invocation: true
allowed-tools: Read, Write, Grep, Glob, Bash
---

# Test Generator — Marzneshin Agent OS

Generate unit or integration tests for: `$ARGUMENTS`

## Test Requirements & Patterns
1. **Location**: Place tests in `tests/test_<name>.py`.
2. **Framework**: Standard `unittest.TestCase` (runnable via `python3 -m unittest discover -s tests`).
3. **Isolation & Safety**:
   - Zero real network calls: mock any sockets, HTTP, or external subprocesses via `unittest.mock.patch`.
   - Never use `datetime.now()`: if testing time, patch `lib.clock.now_iso` or `now_epoch`.
   - Clean up temporary files or use `tempfile.TemporaryDirectory`.
4. **Verification Step**:
   - Run the newly created test immediately:
     ```bash
     python3 -m unittest tests/test_<name>.py
     ```
   - Ensure the test suite passes before completing.
