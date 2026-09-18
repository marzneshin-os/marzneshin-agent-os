# ADR-019: Safe Experimentation, SRM Gates, Guardrail Auto-Stop, and Negative Results (VS-9)

**Date:** 2026-09-18
**Status:** Accepted
**Author:** Momo (Tier 0 Lead Agent)
**Workstream:** agentic-core
**Active Slice:** VS-9 (Safe Experimentation & Readout Loop)

---

## 1. Context & Problem Statement
In Vertical Slice 8 (Growth Spine), we implemented the North Star Metric (NSM), funnel analytics, and privacy-preserving growth taxonomy. However, enabling autonomous agent mutations on routing, pricing, or UX without an experiment safety boundary introduces critical failure modes:
1. **Sample Ratio Mismatch (SRM):** Engineering defects or bot-filtering discrepancies skew traffic allocation away from expected splits (e.g., 50/50), invalidating standard A/B hypotheses and yielding false positives.
2. **Peeking & Premature Shipping:** Agents evaluating metrics continuously suffer from $\alpha$-inflation unless always-valid sequential statistics are enforced.
3. **Severe Regressions During Trials:** An experiment might theoretically increase conversion while destroying Connection Success Rate (CSR) or latency.
4. **Survivorship Bias & Knowledge Loss:** Failed experiments are often quietly discarded, causing subsequent autonomous iterations to repeat identical failed hypotheses.

---

## 2. Decisions & Architecture

### D1: Chi-Square Sample Ratio Mismatch (SRM) Detection
- Readout evaluation performs a goodness-of-fit $\chi^2$ test with 1 degree of freedom:
  $$\chi^2 = \sum \frac{(O_i - E_i)^2}{E_i}$$
  $$p = \text{erfc}\left(\sqrt{\frac{\chi^2}{2}}\right)$$
- An SRM threshold of $\alpha = 0.001$ is strictly enforced.
- If $p < 0.001$, the experiment verdict is immediately set to `kill` with reason `SRM detected (p < 0.001); assignment bias invalidates experiment`.

### D2: Real-time Guardrail Auto-Stop
- Experiments declare secondary safety bounds (`guardrail_metrics`, e.g. `{"csr_floor": 0.98}`).
- On every readout evaluation, observed metrics are verified against guardrail bounds.
- Any breach immediately sets the verdict to `stopped`, records `is_negative_result=True`, and emits an audit event `guardrail.breached`.

### D3: Sequential Always-Valid P-Values & $n_{min}$ Enforcement
- Uses mixture sequential testing to compute valid p-values under continuous monitoring.
- Enforces $n_{min}$ calculation:
  $$n_{min} \approx 2 \cdot \left(\frac{Z_{\alpha/2} + Z_\beta}{\text{MDE}}\right)^2 \cdot p (1 - p)$$
- If total sample size $n < n_{min}$, the verdict remains strictly `inconclusive` ("insufficient sample size is never green").

### D4: Mandatory Negative Results Logging
- Under Invariant I21, any experiment resulting in `kill` or `stopped` persists an explicit post-mortem record in `state/experiments/` and emits `experiment.negative_result`.
- Prevents agents from endlessly cycling through previously refuted hypotheses.

### D5: Elevation to State Sense `Tick-D`
- In `scripts/lib/state.py`, `compute_sense_level` maps `VS-9+` to `Tick-D`.
- `scripts/compact.py` enriches `STATE.json` with an `experiments` block (`active`, `shipped`, `killed`, `total`).

---

## 3. Invariants & Guarantees Maintained
- **Invariant I1 (Append-Only Event Truth):** Experiments and decisions emit audit events (`experiment.created`, `experiment.readout`, `experiment.shipped`, `experiment.killed`, `experiment.stopped`, `experiment.negative_result`).
- **Invariant I12 (Fail-Closed Safety):** SRM skew or guardrail violations immediately halt mutation rollout.
- **Invariant I21 (Negative Result Memory):** All invalidations and regressions are recorded with structured evidence.
- **Rule G5 (Continuous Receipt Chains):** Receipt `T-0021` closes VS-9 with 100% verification and zero broken links.

---

## 4. Verification Evidence
- 249 unit tests pass with 100% green status (`pytest tests/test_experiment_engine.py`).
- 6 verify checks pass (`scripts/verify.py`).
- 51 simulation scenarios across 3 seeds pass with score 1.0.
- Cold-restore drill passes with score 1.0.
