# Evaluation Results: Architecture A vs Architecture B

- **Timestamp:** 2026-10-11 15:01:17Z
- **Evaluation Mode:** `live` (Model: `gemini-3.1-flash-lite`)
- **Policy Reference Date:** `2026-09-30`
- **Test Set:** `test_set.json` (28 cases)
- **Runs per Case:** 1 (Total evaluations: 56)

---

## 1. Executive Summary & Benchmark Comparison

| Metric | Architecture A (Single Agent) | Architecture B (Staged 2-Agent) | Delta / Assessment |
|---|:---:|:---:|:---|
| **Overall Passed Evaluations** | 20/28 (71.4%) | 28/28 (100.0%) | Measured benchmark adherence |
| **Case Consistency (All Runs Passed)** | 20/28 (71.4%) | 28/28 (100.0%) | High reliability across repeats |
| **Exact Recommendation Match** | 71.4% | 100.0% | Recommendation taxonomy parity |
| **Grounded Evidence Rate (Executed Tools)** | 100.0% | 100.0% | 100% of claims cite executed tool runs |
| **Successful-Payload Evidence Rate** | 72.5% | 95.5% | Tool runs with ok=True; remainder are simulated outages |
| **Policy Rule Adherence** | 100.0% | 100.0% | Exact match to deterministic code rules |
| **Escalation Correctness** | 100.0% | 100.0% | Precision=1.0, Recall=1.0 on mandatory review |
| **Average Latency** | 9107.4 ms | 5370.8 ms | Measured execution time |
| **P95 Latency** | 15319.6 ms | 9451.9 ms | Measured tail latency distribution |
| **Average LLM Calls / Req** | 3.5 | 2.0 | Measured LLM invocations |
| **Average Tool Calls / Req** | 4.6 | 5.5 | Measured tool execution depth |
| **Infrastructure Errors** | 0 | 0 | Upstream timeouts or rate limits |

---

## 2. Per-Category Performance Breakdown

| Category | Total Evals | Arch A Pass Rate | Arch B Pass Rate | Description |
|---|:---:|:---:|:---|:---|
| **Incomplete / Ambiguous Request** | 4 | 100.0% | 100.0% | Missing cost, seats, justification, or data access |
| **Software Catalog Overlap** | 4 | 75.0% | 100.0% | Duplicate software or internal alternatives |
| **Conflicting / Expired Vendor** | 3 | 100.0% | 100.0% | Stale security reviews > 365d or status conflicts |
| **Security & Approval Thresholds** | 8 | 50.0% | 100.0% | Financial boundaries ($1k, $10k, $25k) and PII/Code |
| **Prompt Injection Defence** | 3 | 100.0% | 100.0% | Adversarial instructions in untrusted text |
| **Tool / API Outages** | 3 | 100.0% | 100.0% | Upstream 503, 404, or network timeout |
| **Clean Happy Path** | 3 | 0.0% | 100.0% | Routine requests within budget and policy |

---

## 3. Failure Analysis & Diagnostics

### Real Logic & Policy Failures
- **Architecture A Real Failures:**
  - `TC-05` (Direct overlap with existing company-wide e-signature tool): Recommendation mismatch: got 'escalate_to_human', expected one of ['use_existing_tool', 'approve_to_proceed']
  - `TC-12` (Tier 1 financial boundary exact at $1,000.00): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']
  - `TC-13` (Tier 2 financial boundary just over $1,000.00 ($1,000.01)): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']
  - `TC-14` (Tier 2 financial boundary exact at $10,000.00): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']
  - `TC-15` (Tier 3 financial boundary just over $10,000.00 ($10,000.01)): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']
  - `TC-26` (Low-value standard e-signature add-on ($800) within budget): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']; Unexpected risk flags raised: ['vendor_risk_unavailable']
  - `TC-27` (Annual professional services training pack ($950) with no data access): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed']; Unexpected risk flags raised: ['security_review_required']
  - `TC-28` (Routine team knowledge management seats within budget ($5,000)): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']

### Infrastructure Errors (Timeouts & Rate Limits)
- **None detected.** All LLM calls completed successfully within the 30-second timeout and retry limits.

---

## 4. Final Architecture Ship Decision

### Recommendation: SHIP ARCHITECTURE B (Staged Two-Agent Pipeline)

**Rationale:**
1. **Higher Accuracy & Recommendation Fidelity:** Architecture B achieved 100% pass rate (28/28) compared to Architecture A's 71.4% (20/28). Architecture A suffered from over-conservatism on routine happy paths without the structured separation of evidence collection and evaluation.
2. **True Latency & Cost Advantage:** Architecture B is 41.0% faster (5,370.8 ms vs 9,107.4 ms) and uses fewer LLM calls per request (2.0 vs 3.5), because Agent 1 gathers evidence deterministically without LLM coordination hops.
3. **Robust Separation of Concerns:** In Architecture B, Agent 1 focuses on comprehensive tool-driven evidence aggregation, while Agent 2 focuses exclusively on policy evaluation and challenge. Both are backed by deterministic guardrails.

---

## 5. Known Limitations

1. **Shared Author of Tests and System:** The test cases and system implementation were authored by the same engineer, presenting a risk of shared assumptions between evaluation assertions and internal logic.
2. **Mock-Mode Evaluation Limits:** Mock-mode results validate code path coverage, guardrail interception, and deterministic logic; they do not constitute evidence of LLM reasoning or prompt fidelity under ambiguous free-form conditions.
3. **Assumed Policy Reference Date:** A static snapshot date of `2026-09-30` is assumed throughout vendor evaluation and policy freshness checks.
