# Starter Pack Bugs & Defect Log

**Project:** AI Procurement Request Copilot  
**Author:** Forward Deployed Engineer (Candidate)  
**Date:** 2026-10-08  

This document logs all bugs, fragility issues, and architectural defects identified in the starter pack scaffold, along with symptoms, root causes, and applied fixes.

---

### Bug 1: Test Collection Failure in `tests/test_mock_api.py`
- **Symptom:** Running `pytest tests/` fails immediately with:
  ```text
  ModuleNotFoundError: No module named 'mock_api'
  ```
- **Root Cause:** Unlike `tests/test_data_integrity.py` and `evals/run_public_evals.py`, `tests/test_mock_api.py` did not insert the repository root directory into `sys.path`. When pytest executes without an explicit `PYTHONPATH=.`, `mock_api` cannot be located.
- **Fix:** Added `ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))` to `tests/test_mock_api.py` and added a `pytest.ini` with `pythonpath = .` for clean execution.

---

### Bug 2: Unhandled Exceptions & Missing Retries in `src/vendor_client.py`
- **Symptom:** When calling `get_vendor_risk()` on an unavailable vendor (e.g. `NimbusAI`, which returns HTTP 503) or an unknown vendor (HTTP 404), an unhandled `requests.exceptions.HTTPError` is raised, crashing the agent run.
- **Root Cause:** `response.raise_for_status()` was called without exception handling, timeout protection, retry with backoff, or structured error output.
- **Fix:** Replaced naive calls with robust retry logic (1 retry with exponential backoff), graceful exception handling, and standard `{ok, data, source, error}` payload contract.

---

### Bug 3: Case-Sensitive Vendor Matching in `mock_api/app.py`
- **Symptom:** Querying `/vendor-risk/brandboard` (lowercase) or with whitespace returned HTTP 404 `No vendor-risk record for 'brandboard'`, despite `BrandBoard` existing in `vendor_risk.json`.
- **Root Cause:** `DATA.get(name)` performed strict case-sensitive key lookup without normalization.
- **Fix:** Added case-insensitive normalized lookup fallback in `mock_api/app.py`.

---

### Bug 4: Streamlit Dependency & Port Conflicts in UI Scaffold
- **Symptom:** The starter pack included Streamlit (`app.py`), which is a heavy framework that violates the prompt specification:
  > *"Use Python 3.11+, FastAPI, pydantic v2, and a simple HTML/JS front end served by FastAPI. No heavy frameworks."*
- **Root Cause:** Starter pack provided a generic Streamlit template that also required multiple running ports and heavy client-side websocket state.
- **Fix:** Implemented a single FastAPI application serving both the REST APIs (`/api/...`) and a clean, responsive single-page HTML/JS frontend with real-time analysis, tool execution trace, evidence review, and human handoff logging.

---

### Bug 5: Fragile Data Access in `src/data_access.py`
- **Symptom:** Calling `get_request(unknown_id)` threw an unhandled `KeyError` rather than returning a clean error, crashing downstream tool evaluation. Files were also re-read from disk on every invocation.
- **Root Cause:** Naive linear file scanning on each function call with no exception encapsulation or caching.
- **Fix:** Implemented cached data structures and defensive getters with clear status responses.
