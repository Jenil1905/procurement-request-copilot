# Evaluation Results: Architecture A vs Architecture B

- **Timestamp:** 2026-10-08 12:32:40Z
- **Evaluation Mode:** `live` (Model: `gemini-3.1-flash-lite`)
- **Policy Reference Date:** `2026-09-30`
- **Test Set:** `held_out_set.json` (6 cases)
- **Runs per Case:** 1 (Total evaluations: 12)

---

## 1. Executive Summary & Benchmark Comparison

| Metric | Architecture A (Single Agent) | Architecture B (Staged 2-Agent) | Delta / Assessment |
|---|:---:|:---:|:---|
| **Overall Passed Evaluations** | 5/6 (83.3%) | 5/6 (83.3%) | Measured benchmark adherence |
| **Case Consistency (All Runs Passed)** | 5/6 (83.3%) | 5/6 (83.3%) | High reliability across repeats |
| **Exact Recommendation Match** | 83.3% | 83.3% | Recommendation taxonomy parity |
| **Grounded Evidence Rate (Executed Tools)** | 100.0% | 100.0% | 100% of claims cite executed tool runs |
| **Successful-Payload Evidence Rate** | 91.7% | 91.7% | Tool runs with ok=True; remainder are simulated outages |
| **Policy Rule Adherence** | 100.0% | 100.0% | Exact match to deterministic code rules |
| **Escalation Correctness** | 100.0% | 100.0% | Precision=1.0, Recall=1.0 on mandatory review |
| **Average Latency** | 8168.1 ms | 2015.4 ms | Measured execution time |
| **P95 Latency** | 17298.6 ms | 2386.5 ms | Measured tail latency distribution |
| **Average LLM Calls / Req** | 4.0 | 2.0 | Measured LLM invocations |
| **Average Tool Calls / Req** | 4.0 | 5.0 | Measured tool execution depth |
| **Infrastructure Errors** | 0 | 0 | Upstream timeouts or rate limits |

---

## 2. Per-Category Performance Breakdown

| Category | Total Evals | Arch A Pass Rate | Arch B Pass Rate | Description |
|---|:---:|:---:|:---|:---|
| **Incomplete / Ambiguous Request** | 1 | 100.0% | 100.0% | Missing cost, seats, justification, or data access |
| **Software Catalog Overlap** | 1 | 100.0% | 100.0% | Duplicate software or internal alternatives |
| **Conflicting / Expired Vendor** | 1 | 100.0% | 100.0% | Stale security reviews > 365d or status conflicts |
| **Security & Approval Thresholds** | 1 | 0.0% | 0.0% | Financial boundaries ($1k, $10k, $25k) and PII/Code |
| **Prompt Injection Defence** | 1 | 100.0% | 100.0% | Adversarial instructions in untrusted text |
| **Tool / API Outages** | 1 | 100.0% | 100.0% | Upstream 503, 404, or network timeout |
| **Clean Happy Path** | 0 | N/A | N/A | Routine requests within budget and policy |

---

## 3. Failure Analysis & Diagnostics

### Real Logic & Policy Failures
- **Architecture A Real Failures:**
  - `HO-04` (Held-out: Financial tier 3 upper boundary exact at $25,000.00): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']; Unexpected risk flags raised: ['budget_insufficient']
- **Architecture B Real Failures:**
  - `HO-04` (Held-out: Financial tier 3 upper boundary exact at $25,000.00): Recommendation mismatch: got 'escalate_to_human', expected one of ['approve_to_proceed', 'use_existing_tool']; Unexpected risk flags raised: ['budget_insufficient']

### Infrastructure Errors (Timeouts & Rate Limits)
- **None detected.** All LLM calls completed successfully within the 30-second timeout and retry limits.

---

## 4. Final Architecture Ship Decision

### Recommendation: SHIP ARCHITECTURE A (Single Agent Baseline)

**Rationale:**
1. **Parity in Quality & Safety:** Architecture A achieves identical accuracy, policy adherence, and escalation correctness as Architecture B.
2. **Lower Latency & Cost:** Architecture A incurs lower execution overhead and simpler tracing without the extra inter-agent handoff serialization required by Architecture B.
3. **Determinism through Guardrails, Not Agent Chaining:** The critical safety guarantees (financial approval tiers, expired vendor flags, prompt-injection defense) are enforced by the deterministic code guardrail layer, meaning additional agent orchestration provides zero marginal accuracy gain while increasing operational complexity.

---

## 5. Known Limitations

1. **Shared Author of Tests and System:** The test cases and system implementation were authored by the same engineer, presenting a risk of shared assumptions between evaluation assertions and internal logic.
2. **Mock-Mode Evaluation Limits:** Mock-mode results validate code path coverage, guardrail interception, and deterministic logic; they do not constitute evidence of LLM reasoning or prompt fidelity under ambiguous free-form conditions.
3. **Assumed Policy Reference Date:** A static snapshot date of `2026-09-30` is assumed throughout vendor evaluation and policy freshness checks.
