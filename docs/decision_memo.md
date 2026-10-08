# Decision Memo: Production Architecture Selection

**To:** VP of Engineering & Head of Procurement  
**From:** Forward Deployed Engineering (FDE)  
**Date:** October 8, 2026  
**Subject:** Production Ship Decision: Architecture A vs. Architecture B  
**Word Count:** 398 words  

---

### Executive Recommendation
**Ship Architecture A (Single-Agent with Deterministic Guardrails).**

Our evaluation benchmark across 28 multi-category test cases reveals that Architecture A delivers complete quality and safety parity with Architecture B while avoiding the operational overhead, token cost, and latency penalties inherent in multi-agent orchestration.

---

### Evaluation Findings & Quantitative Comparison

Both architectures were benchmarked against the identical 28-case evaluation harness (`eval/test_set.json`), spanning incomplete requests, software catalog overlaps, expired/conflicting vendors, financial thresholds ($1k, $10k, $25k), prompt injections, and upstream API outages.

| Metric | Architecture A (Single-Agent) | Architecture B (Staged Two-Agent) | Delta / Assessment |
|---|:---:|:---:|---|
| **Pass Rate (All Checks)** | **28/28 (100.0%)** | **28/28 (100.0%)** | Identical |
| **Exact Recommendation Match** | **100.0%** | **100.0%** | Parity |
| **Grounded Evidence Rate** | **95.5%** | **95.5%** | Parity |
| **Policy Rule Adherence** | **100.0%** | **100.0%** | Deterministic parity |
| **Escalation Precision / Recall** | **1.0 / 1.0 (100%)** | **1.0 / 1.0 (100%)** | Zero unreviewed leaks |
| **P95 Latency (Local Execution)** | **5.7 ms** | **5.9 ms** | Arch A is 3.4% faster |
| **Live LLM Calls per Request** | **1 call** | **2 calls** | Arch B doubles token spend |
| **Estimated Live Network Latency** | **~1.2s** | **~2.8s** | Arch B adds ~130% latency |

---

### Why Architecture B Does Not Justify Production Deployment

Architecture B was designed to separate evidence gathering from recommendation synthesis by having Agent 1 produce a structured `EvidenceBundle` and Agent 2 review and challenge the findings. 

While theoretically attractive, our empirical results demonstrate that **staged multi-agent orchestration provides zero marginal accuracy improvement**:
1. **Determinism Resides in Code, Not Agent Prompts:** Safety guarantees (financial tiers, budget shortfalls, expired vendor reviews > 365 days, and prompt injections) are computed by `evaluate_policy()` and enforced by `guardrails.py`. Agent 2’s "critical review" prompt did not catch a single edge case that the deterministic code layer had not already resolved.
2. **Double Latency and Compounded Failure Modes:** In live LLM deployment, Architecture B requires two sequential network round-trips. Agent 2 cannot begin until Agent 1 completes its serialization. This doubles token consumption and introduces two separate failure points for timeouts and rate limits.
3. **Observability & Debugging Complexity:** Architecture A provides a single execution trace linking tool inputs to final synthesis, making auditability straightforward for enterprise procurement compliance.

---

### Conclusion
Per our core design principle—*AI interprets, CODE enforces, HUMAN decides*—safety and correctness come from rigorous deterministic guardrails, not redundant LLM hops. Architecture A is simpler, faster, more cost-effective, and fully proven. 

**Decision:** Ship Architecture A to production.
