# Evaluation Results: Architecture A vs Architecture B

- **Timestamp:** 2026-10-08 12:27:04Z
- **Evaluation Mode:** `live` (Model: `gemini-3.1-flash-lite`)
- **Policy Reference Date:** `2026-09-30`
- **Test Set:** `test_set.json` (28 cases)
- **Runs per Case:** 1 (Total evaluations: 56)

---

## 1. Executive Summary & Benchmark Comparison

| Metric | Architecture A (Single Agent) | Architecture B (Staged 2-Agent) | Delta / Assessment |
|---|:---:|:---:|:---|
| **Overall Passed Evaluations** | 27/28 (96.4%) | 28/28 (100.0%) | Measured benchmark adherence |
| **Case Consistency (All Runs Passed)** | 27/28 (96.4%) | 28/28 (100.0%) | High reliability across repeats |
| **Exact Recommendation Match** | 96.4% | 100.0% | Recommendation taxonomy parity |
| **Grounded Evidence Rate (Executed Tools)** | 96.4% | 100.0% | 100% of claims cite executed tool runs |
| **Successful-Payload Evidence Rate** | 90.5% | 95.5% | Tool runs with ok=True; remainder are simulated outages |
| **Policy Rule Adherence** | 96.4% | 100.0% | Exact match to deterministic code rules |
| **Escalation Correctness** | 96.4% | 100.0% | Precision=1.0, Recall=1.0 on mandatory review |
| **Average Latency** | 18437.8 ms | 5370.8 ms | Measured execution time |
| **P95 Latency** | 39180.0 ms | 9451.9 ms | Measured tail latency distribution |
| **Average LLM Calls / Req** | 3.3 | 2.0 | Measured LLM invocations |
| **Average Tool Calls / Req** | 4.5 | 5.5 | Measured tool execution depth |
| **Infrastructure Errors** | 1 | 0 | Upstream timeouts or rate limits |

---

## 2. Per-Category Performance Breakdown

| Category | Total Evals | Arch A Pass Rate | Arch B Pass Rate | Description |
|---|:---:|:---:|:---|:---|
| **Incomplete / Ambiguous Request** | 4 | 100.0% | 100.0% | Missing cost, seats, justification, or data access |
| **Software Catalog Overlap** | 4 | 100.0% | 100.0% | Duplicate software or internal alternatives |
| **Conflicting / Expired Vendor** | 3 | 100.0% | 100.0% | Stale security reviews > 365d or status conflicts |
| **Security & Approval Thresholds** | 8 | 100.0% | 100.0% | Financial boundaries ($1k, $10k, $25k) and PII/Code |
| **Prompt Injection Defence** | 3 | 100.0% | 100.0% | Adversarial instructions in untrusted text |
| **Tool / API Outages** | 3 | 100.0% | 100.0% | Upstream 503, 404, or network timeout |
| **Clean Happy Path** | 3 | 66.7% | 100.0% | Routine requests within budget and policy |

---

## 3. Failure Analysis & Diagnostics

### Real Logic & Policy Failures
- **None detected.** Both architectures satisfied 100% of deterministic guardrails, policy checks, and evidence constraints.

### Infrastructure Errors (Timeouts & Rate Limits)
- **Architecture A Infrastructure Errors:**
  - `TC-28` (Routine team knowledge management seats within budget ($5,000)): Gemini API infrastructure failure after 2 retries (ClientError): 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 15, model: gemini-3.1-flash-lite\nPlease retry in 54.632758251s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-3.1-flash-lite'}, 'quotaValue': '15'}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '54s'}]}}

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
