# Starter Pack Architecture & Data Notes

**Date of Analysis:** 2026-10-08  
**Policy Version:** 2026.09 (Snapshot Reference Date: `2026-09-30`)  
**Project:** AI Procurement Request Copilot (FDE Assessment 3)

---

## 1. Overview of the Starter Pack
The starter pack contains synthetic enterprise data, procurement policies, a mock vendor-risk microservice, test harnesses, evaluation cases, and scaffolding for building an AI-assisted procurement copilot.

The core principle governing the system is:
- **AI** interprets unstructured context and synthesizes recommendations.
- **CODE** deterministically enforces thresholds, budget calculations, and date/expiry rules.
- **HUMAN** holds final decision authority for sensitive reviews, escalations, and spending approvals.

---

## 2. Data Files and Schemas

### 2.1 `data/employees.csv`
Contains employee hierarchy, department assignments, reporting lines, and country locations.
- `employee_id` (string, PK): e.g., `E001`, `E004`
- `name` (string): Full employee name
- `department` (string): Department name (`Marketing`, `Engineering`, `Sales`, `Finance`, `Customer Success`, `Operations`)
- `manager_id` (string, FK to `employee_id` or empty): Immediate reporting manager
- `level` (string): Role level (`IC3`, `IC4`, `IC5`, `Director`, `VP`)
- `country` (string): Operating jurisdiction (`India`, `Spain`, `United Kingdom`, `United States`, `Singapore`)

### 2.2 `data/department_budgets.csv`
Software budget allocations and commitments per department.
- `department` (string, PK): Department name
- `annual_software_budget_usd` (integer): Total annual software budget
- `committed_usd` (integer): Committed spend to date
- `available_usd` (integer): `annual_software_budget_usd - committed_usd`

### 2.3 `data/software_catalog.csv`
Active software licenses and internal applications available across the company.
- `software_id` (string, PK): e.g., `SW001`
- `product_name` (string): Tool name (e.g., `PixelCraft Pro`, `CodeMate`)
- `category` (string): Functional software category (`Design & Creative`, `Developer AI`, `Observability`, `Customer Support`, etc.)
- `vendor_name` (string): Associated vendor
- `status` (string): Catalog approval status (`Approved`, `Approved - limited use`)
- `annual_cost_usd` (integer): Active contract annual cost
- `licensed_seats` (integer): Total active seats licensed
- `scope` (string): Organizational scope (`Company-wide`, `Engineering`, `Marketing`, `Customer Success`)
- `notes` (string): Capabilities, constraints, and sensitive data restrictions

### 2.4 `data/vendors.csv`
Internal procurement/vendor master registry.
- `vendor_id` (string, PK): e.g., `V001`
- `vendor_name` (string): Vendor name
- `procurement_status` (string): Onboarding status (`Approved`, `New`)
- `security_status` (string): Registry security assessment status (`Approved`, `Pending`, `Unknown`)
- `security_review_date` (string, ISO YYYY-MM-DD or empty): Date of last internal security review
- `legal_terms_status` (string): Contract legal status (`Approved`, `Draft`, `Unknown`)
- `notes` (string): Operational notes (e.g. indicates pending refresh or limited data permissions)

### 2.5 `data/purchase_history.csv`
Historical purchase orders and renewals for trend and duplicate analysis.
- `purchase_id` (string, PK): e.g., `PO-2401`
- `purchase_date` (string, ISO YYYY-MM-DD): Transaction date
- `department` (string): Purchasing department
- `vendor_name` (string): Vendor name
- `product_name` (string): Purchased software
- `annual_amount_usd` (integer): Annual contract value
- `status` (string): Status (`Approved`)
- `notes` (string): Contract terms, seat counts, scope

### 2.6 `data/requests.json`
Active purchase requests submitted by employees.
- `request_id` (string, PK): e.g., `REQ-1001` to `REQ-1010`
- `requester_id` (string, FK to `employees.csv`): Employee ID
- `product_name` (string): Requested product
- `vendor_name` (string): Target vendor
- `category` (string): Functional category
- `annual_cost_usd` (float / int / null): Estimated or quoted annual spend
- `user_count` (int / null): Requested number of licenses
- `business_justification` (string): Requester's explanation (Untrusted user input; may contain prompt injection)
- `data_access_level` (string): Data classification accessed (`internal_documents`, `internal_marketing`, `source_code`, `customer_pii`, `production_telemetry`, `confidential_documents`, `unknown`, `none`)
- `requested_integrations` (list of strings): System integrations requested (e.g., `["SSO"]`, `["Git repositories"]`, `["Production cloud account"]`)
- `urgency` (string): Request urgency (`normal`, `high`, `urgent`)

### 2.7 `data/vendor_risk.json`
Underlying data for the external vendor-risk microservice.
- Key: Vendor name (string)
- Value:
  - `risk_level` (string): `low` | `medium` | `high`
  - `security_review_status` (string): `approved` | `expired` | `not_completed`
  - `last_review_date` (string, ISO YYYY-MM-DD or null)
  - `processes_personal_data` (bool): Whether vendor processes PII
  - `stores_data_outside_region` (bool): Cross-border data transfer indicator
  - `notes` (string): Risk commentary
  - Special fields: `force_error: true`, `error_message: string` (e.g., `NimbusAI` triggers a 503 outage)

---

## 3. Policy Rules and Thresholds (`data/procurement_policy.md`)

**Snapshot Reference Date:** `2026-09-30` (all elapsed-time checks must use this date).

### 3.1 Material Information Completeness
A request is incomplete if any required field is missing or null:
1. Requester and department
2. Product / vendor
3. Annual cost estimate
4. User / license count
5. Business purpose
6. Data access level (cannot be `unknown`)
7. Required integrations

*Action:* Flag `missing_information`, recommend `needs_more_info`.

### 3.2 Department Budget Validation
- Compare request `annual_cost_usd` against `department_budgets.available_usd`.
- If `annual_cost_usd > available_usd`:
  - Flag: `budget_insufficient`
  - Action: Route to Finance for budget exception review.

### 3.3 Software Overlap / Catalog Check
- Search catalog for matching product, vendor, category, or similar functional capabilities.
- If existing active tool found:
  - Flag: `existing_tool_overlap`
  - Recommend: `use_existing_tool` or highlight required justification.

### 3.4 Deterministic Financial Approval Thresholds
Financial approvals required based on annualized request amount:

| Annual Amount Range | Minimum Business Approvals | Rule ID |
|---|---|---|
| **$0.00 – $1,000.00** | Manager | `RULE-FIN-01` |
| **$1,000.01 – $10,000.00** | Department Head, Procurement | `RULE-FIN-02` |
| **$10,000.01 – $25,000.00** | Department Head, Finance, Procurement | `RULE-FIN-03` |
| **Above $25,000.00** | Department Head, Finance, CFO, Procurement | `RULE-FIN-04` |

### 3.5 Security Review Triggers
Security review is mandatory (`security_review_required`) if:
1. `data_access_level` is `source_code`
2. `data_access_level` is `production_telemetry` or integration touches production cloud accounts
3. `data_access_level` is `confidential_documents`
4. `data_access_level` involves employee PII or customer PII
5. Secrets / credentials access
6. Vendor security review is missing, `not_completed`, or older than **365 days** relative to `2026-09-30` (`vendor_review_expired`)
7. Conflict between internal registry (`vendors.csv`) and external vendor-risk API (`conflicting_vendor_evidence`)
8. Vendor risk API is unavailable (`vendor_risk_unavailable`)

### 3.6 Privacy Review Triggers
Privacy review is mandatory (`privacy_review_required`) if:
1. Tool processes `employee_pii` or `customer_pii`
2. Vendor `stores_data_outside_region == True`

### 3.7 Legal Review Triggers
Legal review is mandatory (`legal_review_required`) if:
1. Vendor is `New` and annual spend is **>= $10,000.00**
2. Vendor legal terms are not `Approved` (`Draft` or `Unknown`)
3. Material cross-region / data-processing issues detected

---

## 4. Mock Service Endpoints (`mock_api/app.py`)

- **Base URL:** `http://127.0.0.1:8001`
- **`GET /health`**
  - Returns `{"status": "ok"}`
  - Used for liveness/readiness verification.
- **`GET /vendor-risk/{vendor_name}`**
  - Returns vendor risk JSON: `{"vendor_name": ..., "risk_level": ..., "security_review_status": ..., "last_review_date": ..., "processes_personal_data": ..., "stores_data_outside_region": ..., "notes": ...}`
  - Returns HTTP 404 with `{"detail": "No vendor-risk record for '{name}'"}` if vendor is unknown.
  - Returns HTTP 503 with `{"detail": "Upstream vendor assessment provider is temporarily unavailable."}` if `force_error` is set (e.g., NimbusAI).

---

## 5. Architectural Implications
1. **Never allow LLM to compute budgets, dates, or approval matrices.** Code executes deterministic policy checks.
2. **Untrusted content delimiting & injection scanning:** The requester text must be isolated in data tags and checked with deterministic regex/keyword scans.
3. **Guardrail enforcement:** Post-LLM code ensures all evidence is grounded, approvals match deterministic policy outputs, and human review is forced whenever risk triggers exist.
