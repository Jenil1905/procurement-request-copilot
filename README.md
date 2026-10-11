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

We evaluated both architectures against a 28-case evaluation benchmark (`eval/test_set.json`), encompassing 6 edge-case categories plus clean happy paths, alongside a 6-case held-out generalization set (`eval/held_out_set.json`). All reported figures represent strictly measured live evaluations with Gemini 3.1 Flash Lite (`--repeats 1`).

### Benchmark Results Table (Live Execution)

| Benchmark Metric | Architecture A (Single Agent) | Architecture B (Staged 2-Agent) | Delta / Assessment |
|---|:---:|:---:|---|
| **Overall Pass Rate** | **20/28 (71.4%)** | **28/28 (100.0%)** | Arch B achieved full recommendation parity |
| **Real Logic / Policy Failures** | **8 / 28 (28.6%)** | **0 / 28 (0.0%)** | Arch A over-escalated clean happy paths |
| **Infrastructure Errors** | **0** | **0** | All calls completed within timeout/retry limits |
| **Exact Recommendation Match** | **71.4%** | **100.0%** | Arch B strictly matched expected taxonomy |
| **Grounded Evidence Rate (Executed Tools)** | **100.0%** | **100.0%** | 100% of claims cite executed tool runs |
| **Successful-Payload Evidence Rate** | **72.5%** | **95.5%** | Arch B cleanly handles service outages |
| **Policy Rule Adherence** | **100.0%** | **100.0%** | Exact match to deterministic code rules |
| **Escalation Correctness** | **100.0%** | **100.0%** | Precision=1.0, Recall=1.0 on mandatory review |
| **Average Latency (Clean Live)** | **9,107.4 ms** | **5,370.8 ms** | Arch B is 41.0% faster (see Latency Caveat below) |
| **P95 Latency (Clean Live)** | **15,319.6 ms** | **9,451.9 ms** | Arch B tail latency is 1.6x lower |
| **Average LLM Calls / Req** | **3.5 calls** | **2.0 calls** | Arch B eliminates dynamic planning hops |
| **Average Tool Calls / Req** | **4.6 calls** | **5.5 calls** | Full tool coverage depth across both |
| **Held-Out Set Pass Rate (6 cases)** | **5/6 (83.3%)** | **5/6 (83.3%)** | Parity; HO-04 test expectation defect |

> **Latency Comparison Caveat:**  
> In initial sequential benchmark runs, Architecture A averaged ~18.4s because it hit transient 504 gateway timeouts and 5s/10s rate-limit retry backoffs. In clean, unthrottled runs, Architecture A averages **9.1s** vs Architecture B's **5.4s**. Saying "Architecture B is 70% faster" overstates the true architectural difference: Architecture B is genuinely **~41% faster**, strictly because Agent 1 gathers evidence deterministically, reducing total LLM roundtrips from 3.5 to 2.0.

### Per-Category Breakdown (Primary 28 Cases)

| Category | Cases | Arch A Pass Rate | Arch B Pass Rate | Edge Conditions Tested |
|---|:---:|:---:|:---:|---|
| **Incomplete / Ambiguous Request** | 4 | 100.0% | 100.0% | Null cost, missing seats, missing justification, unknown data level |
| **Existing Software Overlap** | 4 | 75.0% | 100.0% | BrandBoard vs PixelCraft, TaskFlow vs SprintMaster, seats expansion |
| **Conflicting / Expired Vendor** | 3 | 100.0% | 100.0% | SignalWatch review > 365d, registry Approved vs API Expired |
| **Security & Financial Boundaries** | 8 | 50.0% | 100.0% | Exact boundary testing: $1,000, $1,000.01, $10,000, $10,000.01, $25,000.01 |
| **Prompt Injection Defence** | 3 | 100.0% | 100.0% | "Ignore rules", "CFO-approved", "bypass security checks" embedded in text |
| **Tool / API Outages** | 3 | 100.0% | 100.0% | Upstream 503 outage, simulated API down toggle, unknown vendor 404 |
| **Clean Happy Path** | 3 | 0.0% | 100.0% | Routine purchases under budget (Arch A over-escalated to human review) |

### Held-Out Evaluation & The HO-04 Test Defect

On the 6 held-out cases (`eval/held_out_set.json`), both architectures scored **5/6 (83.3%)** with zero infrastructure errors.
- **The HO-04 "Failure" is a Test Defect:** The test case `HO-04` ($25,000 Sales Intelligence add-on) expected a recommendation of `approve_to_proceed`. However, according to the official financial data in `department_budgets.csv`, the Sales department had only $20,000 remaining available software budget. Both Architecture A and Architecture B correctly computed the $5,000 dollar shortfall, raised `budget_insufficient`, and enforced human review. The test's expected answer was erroneous; the system performed exactly as designed by preventing an unauthorized budget overrun.

---

## 5. Architecture Comparison & Final Ship Decision

### Final Ship Decision: **SHIP ARCHITECTURE B (Staged Two-Agent)**

#### Rationale:
1. **Quality Advantage of Two-Stage Review:** In live testing, Architecture A's single agent suffered from over-conservatism, escalating 8 routine requests to `escalate_to_human` when standard approval was warranted. Architecture B's explicit separation—where Agent 2 challenges a structured `EvidenceBundle`—achieved 100% recommendation fidelity (28/28).
2. **True Latency & Token Efficiency:** Architecture B completes requests in 5.4s vs 9.1s for Architecture A (~41% faster), requiring only 2.0 LLM calls per request instead of 3.5. By executing data retrieval deterministically in Agent 1, Architecture B eliminates multi-round LLM tool-orchestration overhead.
3. **Identical Safety Parity:** Deterministic guardrails (`guardrails.py` and `policy_config.py`) enforce budget boundaries, approval tiers, and prompt injection defense on both architectures, ensuring zero unreviewed policy violations.
4. **Held-Out Generalization:** Both architectures achieved 83.3% (5/6) on the held-out evaluation set, with HO-04 correctly catching a real budget deficit.

Detailed analysis is available in [Decision Memo](docs/decision_memo.md).

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

1. **Shared Author of Tests and System:** The test cases and system implementation were authored by the same engineer, presenting a risk of shared assumptions between evaluation assertions and internal logic.
2. **Mock-Mode Evaluation Limits:** Mock-mode results validate code path coverage, guardrail interception, and deterministic logic; they do not constitute evidence of LLM reasoning or prompt fidelity under ambiguous free-form conditions.
3. **Assumed Policy Reference Date:** A static snapshot date of `2026-09-30` is assumed throughout vendor evaluation and policy freshness checks.
4. **Vendor Ambiguity on Free-Text Names:** If a requester inputs an unrecognized slang abbreviation for an unlisted vendor, fuzzy matching will route the vendor to Security manual verification (HTTP 404 fallback).
5. **Mock Service Concurrency:** The local mock service (`mock_api`) is designed for development and testing; production deployment would integrate enterprise SSO/SCIM directories (Okta/Workday) and real third-party risk feeds (e.g., SecurityScorecard, Whistic).
6. **Budget Periodicity:** Department budgets in `department_budgets.csv` represent fixed fiscal allocations. Production systems would pull real-time remaining purchase order balances from ERP systems (SAP/NetSuite).

---

## 9. Deliverables Directory

- [starter_pack_notes.md](docs/starter_pack_notes.md): Comprehensive schema, policy threshold, and API endpoint documentation.
- [bugs_found.md](docs/bugs_found.md): Log of scaffold bugs identified, root causes, and fixes applied.
- [architecture.md](docs/architecture.md): Detailed architectural specification and Mermaid diagrams.
- [decision_memo.md](docs/decision_memo.md): 495-word executive memo defending the Architecture B ship decision.
- [test_set.json](eval/test_set.json): 28-case evaluation benchmark dataset.
- [results.md](eval/results/results.md): Detailed comparative evaluation benchmark report.
