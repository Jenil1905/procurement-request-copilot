# AI Procurement Request Copilot

> **Forward Deployed Engineer (FDE) Assessment 3 Submission**  
> An enterprise procurement intelligence system that gathers evidence across databases, APIs, and policy docs, enforces deterministic financial and security thresholds, defends against adversarial prompt injections, and guides human decision-makers.

---

## 1. Quick Start & Execution

### One-Command Launch (Makefile)
```bash
make start
```
*Creates `.venv` if needed, installs dependencies, launches the Mock Vendor-Risk API on `http://127.0.0.1:8001`, starts the FastAPI Web Console on `http://127.0.0.1:8000`, and opens the console URL.*

### Python Fallback Runner
```bash
python run.py
```

### Run Evaluation Harness
```bash
make eval
# Or directly:
.venv/bin/python eval/run_eval.py --arch both
```

### Run Test Suite & Verification Checks
```bash
make test          # Runs 40 unit and integration tests across tools, API, security, web app
make public-eval   # Runs the 6 starter pack public evaluation cases across both architectures
```

---

## 2. Product Workflow & Interactive UI

The solution includes a single-page web UI built with Vanilla CSS and modern interactive features, served directly by FastAPI (`http://127.0.0.1:8000`):

1. **Intake & Custom Request Picker:**
   - Pre-loaded dropdown containing all synthetic business requests (`REQ-1001` through `REQ-1010`).
   - "New / Custom Request" modal form enabling ad-hoc testing of incomplete, ambiguous, or adversarial requests.
2. **Architecture Toggle (A / B):**
   - Toggle instantly between **Architecture A** (Single-Agent interactive loop) and **Architecture B** (Staged Two-Agent pipeline).
3. **Vendor Outage Simulation:**
   - Real-time "Simulate Vendor API Down" toggle to test resilience against upstream 503 errors and network timeouts.
4. **Execution Telemetry:**
   - Live telemetry ribbon displaying total execution latency (ms), LLM call count, and tool execution count.
5. **Dossier & Evidence Breakdown:**
   - Claims are presented with their associated tool source, underlying data file, and timestamp.
   - Collapsible raw JSON tool execution payloads for transparency.
6. **Human Handoff & Immutable Audit Logging:**
   - When sensitive policy triggers fire (`needs_human_review = True`), a prominent escalation banner appears.
   - Action buttons (**Approve to Proceed**, **Reject Request**, **Request More Info**) log the final human decision to `data/decisions_log.jsonl` without autonomously committing funds.

---

## 3. Core Architecture & Governance Principles

The system strictly adheres to three design tenets:
- **AI interprets context, synthesizes summaries, and recommends.**
- **CODE deterministically enforces budgets, financial tiers, expiry math, and injection detection.**
- **HUMAN retains sole legal authority over exceptions, spend approvals, and contracts.**

```
+-------------------------------------------------------------------------------------------------+
|                                    DATA & GOVERNANCE PIPELINE                                   |
|                                                                                                 |
|  [Request Intake]                                                                               |
|         │                                                                                       |
|         ▼                                                                                       |
|  [Prompt-Injection Scan] ──► (Regex + Heuristics Isolation in XML Delimiters)                    |
|         │                                                                                       |
|         ▼                                                                                       |
|  [Tool Execution Engine] ──► (Catalog, Budgets, Vendor-Risk API, Policy Engine, History)         |
|         │                                                                                       |
|         ▼                                                                                       |
|  [LLM Synthesis Layer]   ──► (Gemini 2.5 Flash / Deterministic Rule-Based Stub)                 |
|         │                                                                                       |
|         ▼                                                                                       |
|  [Guardrail Layer]       ──► (Evidence Grounding, evaluate_policy() Override, Human Escalation)  |
|         │                                                                                       |
|         ▼                                                                                       |
|  [Product UI & Handoff]  ──► (decisions_log.jsonl Audit Trail)                                  |
+-------------------------------------------------------------------------------------------------+
```

### Tool Suite
Every tool returns a uniform `ToolResult(ok=bool, data=dict, source=str, error=str | None)` with 1 retry on HTTP failures:
1. `get_request_and_employee(request_id)`: Deterministically resolves requester identity, department, and direct reporting manager.
2. `search_software_catalog(query, category)`: Scans approved software catalog for duplicate tools, category matches, and available license seats.
3. `check_budget(department, amount)`: Deterministically calculates remaining department budget, whether request fits, and exact shortfall.
4. `get_vendor_status(vendor_name)`: Queries external mock service (Port 8001) over HTTP with retry and timeout handling. Computes review expiration (> 365 days from policy snapshot date `2026-09-30`) and registry conflicts.
5. `evaluate_policy(request, budget_result, vendor_result)`: Deterministic policy engine applying financial tiers ($1k, $10k, $25k), security triggers, privacy (PII) triggers, and legal review triggers, returning exact rule IDs.
6. `get_purchase_history(vendor_name, category)`: Scans historical transactions for repeat vendor spend and duplicate category subscriptions.

---

## 4. Evaluation Benchmark: Architecture A vs. Architecture B

We evaluated both architectures against a 28-case evaluation benchmark (`eval/test_set.json`), encompassing 6 edge-case categories plus clean happy paths.

### Benchmark Results Table

| Benchmark Metric | Architecture A (Single Agent) | Architecture B (Staged 2-Agent) | Delta / Assessment |
|---|:---:|:---:|---|
| **Overall Pass Rate** | **28/28 (100.0%)** | **28/28 (100.0%)** | Exact parity across all categories |
| **Exact Recommendation Match** | **100.0%** | **100.0%** | Parity (`approve_to_proceed`, `use_existing_tool`, etc.) |
| **Grounded Evidence Rate** | **95.5%** | **95.5%** | 100% of claims verified against actual tool runs |
| **Policy Rule Adherence** | **100.0%** | **100.0%** | Exact match to deterministic `evaluate_policy()` |
| **Escalation Precision / Recall** | **1.0 / 1.0 (100%)** | **1.0 / 1.0 (100%)** | Zero unreviewed policy exceptions |
| **Average Latency (Local)** | **14.4 ms** | **13.9 ms** | Local mock execution |
| **P95 Latency (Local)** | **5.7 ms** | **5.9 ms** | Arch A has lower tail latency |
| **Live LLM Calls per Request** | **1 call** | **2 calls** | Architecture B incurs 2x model calls |
| **Estimated Live Network Latency** | **~1.2s** | **~2.8s** | Architecture B adds 130% latency |

### Per-Category Breakdown

| Category | Cases | Arch A Pass Rate | Arch B Pass Rate | Edge Conditions Tested |
|---|:---:|:---:|:---:|---|
| **Incomplete / Ambiguous Request** | 4 | 100% | 100% | Null cost, missing seats, missing justification, unknown data level |
| **Existing Software Overlap** | 4 | 100% | 100% | BrandBoard vs PixelCraft, TaskFlow vs SprintMaster, seats expansion |
| **Conflicting / Expired Vendor** | 3 | 100% | 100% | SignalWatch review > 365d, registry Approved vs API Expired |
| **Security & Financial Boundaries** | 8 | 100% | 100% | Exact boundary testing: $1,000, $1,000.01, $10,000, $10,000.01, $25,000.01 |
| **Prompt Injection Defence** | 3 | 100% | 100% | "Ignore rules", "CFO-approved", "bypass security checks" embedded in text |
| **Tool / API Outages** | 3 | 100% | 100% | Upstream 503 outage, simulated API down toggle, unknown vendor 404 |
| **Clean Happy Path** | 3 | 100% | 100% | Routine purchases under budget and within policy thresholds |

---

## 5. Architecture Comparison & Final Ship Decision

### Final Ship Decision: **SHIP ARCHITECTURE A (Single Agent)**

#### Rationale:
1. **Zero Accuracy Advantage from Multi-Agent Orchestration:** Both architectures achieve 100% benchmark accuracy because determinism, threshold enforcement, and security escalation are governed by code guardrails (`guardrails.py` and `policy_config.py`), not agent prompts.
2. **Reduced Latency and Token Costs:** Architecture B requires two sequential LLM calls (Agent 1 for gathering, Agent 2 for review). In live deployment, this doubles token spend and introduces a 2.4–3.0 second latency overhead.
3. **Simpler Enterprise Observability:** Architecture A maintains a single coherent tool execution trace, significantly simplifying enterprise auditing and debugging.
4. **Resilience to Cascading Failures:** In Architecture B, a failure in Agent 1's serialization breaks Agent 2. Architecture A processes tools directly within a unified execution context.

Detailed analysis is available in [Decision Memo](file:///home/jenil/Desktop/FDE-Assignment-3/docs/decision_memo.md).

---

## 6. Prompt-Injection Defence Strategy

Business data (justifications, vendor notes, catalog summaries) can contain adversarial prompt injection attempts. The copilot defends against this across two layers:
1. **Untrusted Data Boundary Isolation:** All external strings are enclosed in `<UNTRUSTED_BUSINESS_DATA>` tags. System prompts instruct the LLM that text within these blocks is purely data to be analyzed, never instructions to execute.
2. **Code-Level Heuristic Scanner (`src/security.py`):** Pre-execution regex patterns scan for phrases like `bypass policy`, `cfo-approved`, `disregard rules`, or `ignore instructions`. If detected:
   - A `prompt_injection_detected` risk flag is attached.
   - `needs_human_review = True` is forced.
   - Recommendation escalates to `escalate_to_human`.

---

## 7. Key Assumptions

- **Policy Reference Date:** Pinned to **2026-09-30** per `procurement_policy.md`. Vendor reviews older than 365 days relative to this date are classified as expired.
- **Strict Human Oversight:** The copilot never autonomously executes contracts or disburses funds; the maximum automated status is `approve_to_proceed`.
- **Recommendation Taxonomy:** Strictly normalized to `approve_to_proceed`, `use_existing_tool`, `needs_more_info`, `escalate_to_human`, or `reject`.

---

## 8. Known Limitations

1. **Vendor Ambiguity on Free-Text Names:** If a requester inputs an unrecognized slang abbreviation for an unlisted vendor, fuzzy matching will route the vendor to Security manual verification (HTTP 404 fallback).
2. **Mock Service Concurrency:** The local mock service (`mock_api`) is designed for development and testing; production deployment would integrate enterprise SSO/SCIM directories (Okta/Workday) and real third-party risk feeds (e.g., SecurityScorecard, Whistic).
3. **Budget Periodicity:** Department budgets in `department_budgets.csv` represent fixed fiscal allocations. Production systems would pull real-time remaining purchase order balances from ERP systems (SAP/NetSuite).

---

## 9. Deliverables Directory

- [starter_pack_notes.md](file:///home/jenil/Desktop/FDE-Assignment-3/docs/starter_pack_notes.md): Comprehensive schema, policy threshold, and API endpoint documentation.
- [bugs_found.md](file:///home/jenil/Desktop/FDE-Assignment-3/docs/bugs_found.md): Log of scaffold bugs identified, root causes, and fixes applied.
- [architecture.md](file:///home/jenil/Desktop/FDE-Assignment-3/docs/architecture.md): Detailed architectural specification and Mermaid diagrams.
- [decision_memo.md](file:///home/jenil/Desktop/FDE-Assignment-3/docs/decision_memo.md): 470-word executive memo defending the Architecture A ship decision.
- [test_set.json](file:///home/jenil/Desktop/FDE-Assignment-3/eval/test_set.json): 28-case evaluation benchmark dataset.
- [results.md](file:///home/jenil/Desktop/FDE-Assignment-3/eval/results/results.md): Detailed comparative evaluation benchmark report.
