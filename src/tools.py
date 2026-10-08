"""Procurement Copilot Tools with Pydantic Models and JSON Tool Schemas.

All tools adhere to the standard envelope:
    {"ok": bool, "data": Any, "source": str, "error": str | None}
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from pydantic import BaseModel, Field

from src.policy_config import (
    FINANCIAL_THRESHOLDS,
    LEGAL_NEW_VENDOR_THRESHOLD,
    POLICY_REFERENCE_DATE,
    PRIVACY_DATA_TRIGGERS,
    SECURITY_DATA_LEVEL_TRIGGERS,
    SECURITY_INTEGRATION_TRIGGERS,
    VENDOR_ASSESSMENT_VALIDITY_DAYS,
)
from src.security import injection_scan

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


# ============================================================================
# Pydantic Envelope & Output Models
# ============================================================================

class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    source: str
    error: str | None = None


class ApprovalRequirement(BaseModel):
    approver: str
    reason: str
    rule_id: str


class RiskFlagItem(BaseModel):
    flag: str
    severity: str = "medium"
    detail: str


# ============================================================================
# Data Access Helpers with Caching
# ============================================================================

_CACHE: dict[str, Any] = {}


def _get_cached_csv(filename: str) -> list[dict[str, str]]:
    if filename not in _CACHE:
        path = DATA_DIR / filename
        if not path.is_file():
            return []
        with path.open(encoding="utf-8", newline="") as f:
            _CACHE[filename] = list(csv.DictReader(f))
    return _CACHE[filename]


def _get_cached_json(filename: str) -> Any:
    if filename not in _CACHE:
        path = DATA_DIR / filename
        if not path.is_file():
            return None
        _CACHE[filename] = json.loads(path.read_text(encoding="utf-8"))
    return _CACHE[filename]


# ============================================================================
# Tool 1: get_request_and_employee (DETERMINISTIC)
# ============================================================================

def get_request_and_employee(request_id: str) -> dict[str, Any]:
    """Reads purchase request, requester, department, and reporting manager."""
    try:
        requests_data = _get_cached_json("requests.json") or []
        req = next((r for r in requests_data if r.get("request_id") == request_id), None)
        if not req:
            return ToolResult(
                ok=False,
                source="get_request_and_employee",
                error=f"Request '{request_id}' not found in requests database",
            ).model_dump()

        employees = _get_cached_csv("employees.csv")
        requester_id = req.get("requester_id")
        requester = next((e for e in employees if e.get("employee_id") == requester_id), None)

        manager_info = None
        if requester and requester.get("manager_id"):
            mgr_id = requester["manager_id"]
            mgr = next((e for e in employees if e.get("employee_id") == mgr_id), None)
            if mgr:
                manager_info = {
                    "manager_id": mgr_id,
                    "manager_name": mgr.get("name"),
                    "manager_level": mgr.get("level"),
                }

        # Check for injection in justification
        inj_check = injection_scan(req.get("business_justification"), context="business_justification")

        data = {
            "request": req,
            "requester": requester,
            "manager": manager_info,
            "injection_scan": inj_check,
        }
        return ToolResult(ok=True, data=data, source="get_request_and_employee").model_dump()
    except Exception as exc:
        logger.exception("Error in get_request_and_employee")
        return ToolResult(
            ok=False,
            source="get_request_and_employee",
            error=f"Exception retrieving request and employee: {type(exc).__name__}: {exc}",
        ).model_dump()


# ============================================================================
# Tool 2: search_software_catalog
# ============================================================================

def search_software_catalog(
    query: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """Checks whether an existing approved tool covers the need (fuzzy/keyword match)."""
    try:
        catalog = _get_cached_csv("software_catalog.csv")
        query_norm = (query or "").strip().lower()
        cat_norm = (category or "").strip().lower()

        matches = []
        for item in catalog:
            score = 0
            item_cat = (item.get("category") or "").lower()
            item_name = (item.get("product_name") or "").lower()
            item_vendor = (item.get("vendor_name") or "").lower()
            item_notes = (item.get("notes") or "").lower()

            # Exact or partial category match
            if cat_norm and (cat_norm in item_cat or item_cat in cat_norm):
                score += 3

            # Query token matches
            if query_norm:
                tokens = [t for t in query_norm.split() if len(t) > 2]
                for t in tokens:
                    if t in item_name:
                        score += 4
                    if t in item_vendor:
                        score += 3
                    if t in item_cat:
                        score += 2
                    if t in item_notes:
                        score += 1

            if score > 0 or (not query_norm and not cat_norm):
                matches.append({
                    "software_id": item.get("software_id"),
                    "product_name": item.get("product_name"),
                    "category": item.get("category"),
                    "vendor_name": item.get("vendor_name"),
                    "status": item.get("status"),
                    "annual_cost_usd": int(item.get("annual_cost_usd", 0)),
                    "licensed_seats": int(item.get("licensed_seats", 0)),
                    "scope": item.get("scope"),
                    "notes": item.get("notes"),
                    "match_score": score,
                })

        matches.sort(key=lambda m: m["match_score"], reverse=True)
        category_matched = any(
            cat_norm and (cat_norm in (m.get("category") or "").lower() or (m.get("category") or "").lower() in cat_norm)
            for m in matches
        )
        name_matched = len(matches) > 0 and matches[0]["match_score"] >= 4
        
        # Non-software service categories (consulting, training, professional services)
        # do not conflict with software catalog tool licenses
        non_software_cats = {"professional services", "training", "services", "consulting", "hardware"}
        if cat_norm in non_software_cats:
            has_overlap = False
        else:
            has_overlap = category_matched or name_matched

        data = {
            "query": query,
            "category": category,
            "matches": matches[:5],
            "count": len(matches),
            "has_overlap": has_overlap,
            "primary_overlap": matches[0] if matches else None,
        }
        return ToolResult(ok=True, data=data, source="search_software_catalog").model_dump()
    except Exception as exc:
        logger.exception("Error in search_software_catalog")
        return ToolResult(
            ok=False,
            source="search_software_catalog",
            error=f"Exception searching software catalog: {type(exc).__name__}: {exc}",
        ).model_dump()


# ============================================================================
# Tool 3: check_budget (DETERMINISTIC)
# ============================================================================

def check_budget(department: str, amount: float | int | None) -> dict[str, Any]:
    """Calculates remaining budget, whether the request fits, and any shortfall."""
    try:
        budgets = _get_cached_csv("department_budgets.csv")
        dept_match = next((b for b in budgets if b.get("department", "").lower() == department.strip().lower()), None)
        if not dept_match:
            return ToolResult(
                ok=False,
                source="check_budget",
                error=f"Unknown department '{department}' not found in budget registry",
            ).model_dump()

        annual_budget = Decimal(dept_match.get("annual_software_budget_usd", 0))
        committed = Decimal(dept_match.get("committed_usd", 0))
        available = Decimal(dept_match.get("available_usd", 0))

        if amount is None:
            return ToolResult(
                ok=False,
                source="check_budget",
                error="Request amount is missing or null; cannot perform budget check",
                data={
                    "department": dept_match.get("department"),
                    "available_usd": float(available),
                    "fits_in_budget": False,
                    "missing_amount": True,
                },
            ).model_dump()

        amt_dec = Decimal(str(amount))
        fits = amt_dec <= available
        shortfall = max(Decimal("0.00"), amt_dec - available)
        remaining_after = available - amt_dec

        data = {
            "department": dept_match.get("department"),
            "annual_budget_usd": float(annual_budget),
            "committed_usd": float(committed),
            "available_usd": float(available),
            "request_amount_usd": float(amt_dec),
            "fits_in_budget": bool(fits),
            "shortfall_usd": float(shortfall),
            "remaining_after_purchase_usd": float(remaining_after),
            "risk_flag": "budget_insufficient" if not fits else None,
        }
        return ToolResult(ok=True, data=data, source="check_budget").model_dump()
    except Exception as exc:
        logger.exception("Error in check_budget")
        return ToolResult(
            ok=False,
            source="check_budget",
            error=f"Exception checking budget: {type(exc).__name__}: {exc}",
        ).model_dump()


# ============================================================================
# Tool 4: get_vendor_status
# ============================================================================

def get_vendor_status(vendor_name: str, simulate_down: bool = False) -> dict[str, Any]:
    """Calls the vendor/security service over HTTP with retry and checks registry."""
    clean_name = vendor_name.strip()
    source = "get_vendor_status"

    # 1. Read internal registry info from vendors.csv
    vendors = _get_cached_csv("vendors.csv")
    registry_entry = next((v for v in vendors if v.get("vendor_name", "").lower() == clean_name.lower()), None)

    # 2. Call external vendor-risk API with 1 retry and backoff
    base_url = os.getenv("VENDOR_RISK_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    api_url = f"{base_url}/vendor-risk/{quote(clean_name, safe='')}"

    api_data: dict[str, Any] | None = None
    api_error: str | None = None
    is_unavailable = False

    if simulate_down:
        api_error = "Simulated vendor API outage"
        is_unavailable = True
    else:
        # Retry loop: max 2 attempts (1 initial + 1 retry) with 0.3s backoff
        for attempt in range(2):
            try:
                resp = requests.get(api_url, timeout=2.5)
                if resp.status_code == 200:
                    api_data = resp.json()
                    api_error = None
                    break
                elif resp.status_code == 404:
                    api_error = f"Vendor '{clean_name}' not found in external assessment database (404)"
                    break
                elif resp.status_code >= 500:
                    err_msg = resp.json().get("detail", "Vendor-risk service unavailable") if resp.headers.get("content-type") == "application/json" else resp.text
                    api_error = f"External vendor-risk API returned error ({resp.status_code}): {err_msg}"
                    is_unavailable = True
                    if attempt == 0:
                        time.sleep(0.3)
                        continue
            except (requests.Timeout, requests.ConnectionError) as exc:
                api_error = f"External vendor-risk API connection failure: {type(exc).__name__}"
                is_unavailable = True
                if attempt == 0:
                    time.sleep(0.3)
                    continue
            except Exception as exc:
                api_error = f"Unexpected error contacting vendor-risk service: {exc}"
                is_unavailable = True
                break

    # 3. Analyze review freshness and consistency relative to reference date (2026-09-30)
    review_date_str = None
    if api_data and api_data.get("last_review_date"):
        review_date_str = api_data.get("last_review_date")
    elif registry_entry and registry_entry.get("security_review_date"):
        review_date_str = registry_entry.get("security_review_date")

    is_expired = False
    days_since_review = None
    if review_date_str:
        try:
            r_date = date.fromisoformat(review_date_str)
            days_since_review = (POLICY_REFERENCE_DATE - r_date).days
            if days_since_review > VENDOR_ASSESSMENT_VALIDITY_DAYS:
                is_expired = True
        except ValueError:
            pass

    # Status check
    api_status = (api_data.get("security_review_status") if api_data else "").lower()
    reg_status = (registry_entry.get("security_status") if registry_entry else "").lower()

    if api_status == "expired":
        is_expired = True

    # Conflict check: registry says Approved, but API says expired / not_completed / etc.
    has_conflict = False
    if reg_status == "approved" and api_status in ["expired", "not_completed"]:
        has_conflict = True

    # Is vendor new?
    is_new_vendor = False
    if registry_entry and registry_entry.get("procurement_status", "").lower() == "new":
        is_new_vendor = True
    elif not registry_entry and not api_data:
        is_new_vendor = True

    payload = {
        "vendor_name": clean_name,
        "is_unavailable": is_unavailable,
        "api_data": api_data,
        "registry_data": registry_entry,
        "security_review_status": api_status or reg_status or "unknown",
        "last_review_date": review_date_str,
        "days_since_review": days_since_review,
        "is_expired": is_expired,
        "has_conflict": has_conflict,
        "is_new_vendor": is_new_vendor,
        "procurement_status": registry_entry.get("procurement_status", "New") if registry_entry else "New",
        "legal_terms_status": registry_entry.get("legal_terms_status", "Unknown") if registry_entry else "Unknown",
        "processes_personal_data": api_data.get("processes_personal_data", False) if api_data else False,
        "stores_data_outside_region": api_data.get("stores_data_outside_region", False) if api_data else False,
    }

    if is_unavailable:
        return ToolResult(
            ok=False,
            data=payload,
            source=source,
            error=api_error or "Vendor-risk service is unavailable",
        ).model_dump()

    return ToolResult(ok=True, data=payload, source=source).model_dump()


# ============================================================================
# Tool 5: evaluate_policy (DETERMINISTIC)
# ============================================================================

def evaluate_policy(
    request: dict[str, Any],
    budget_result: dict[str, Any] | None = None,
    vendor_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Applies policy thresholds, triggers, and deterministically computes approvals."""
    approvals_required: list[ApprovalRequirement] = []
    risk_flags: list[RiskFlagItem] = []
    missing_information: list[str] = []

    # 1. Completeness Validation (Policy Section 1)
    if not request.get("requester_id"):
        missing_information.append("requester_id is missing")
    if not request.get("product_name"):
        missing_information.append("product_name is missing")
    if not request.get("vendor_name"):
        missing_information.append("vendor_name is missing")
    if request.get("annual_cost_usd") is None:
        missing_information.append("annual_cost_usd is missing")
    if request.get("user_count") is None:
        missing_information.append("user_count (licensed seats) is missing")
    if not request.get("business_justification"):
        missing_information.append("business_justification is missing")
    if not request.get("data_access_level") or request.get("data_access_level") == "unknown":
        missing_information.append("data_access_level is unknown or unstated")

    if missing_information:
        risk_flags.append(RiskFlagItem(
            flag="missing_information",
            severity="high",
            detail=f"Request lacks material required fields: {', '.join(missing_information)}",
        ))

    # 2. Financial Approvals (Policy Section 4)
    cost = request.get("annual_cost_usd")
    cost_dec = Decimal(str(cost)) if cost is not None else None

    if cost_dec is not None:
        matched_rule = None
        for threshold in FINANCIAL_THRESHOLDS:
            if threshold.max_amount is not None:
                if threshold.min_amount <= cost_dec <= threshold.max_amount:
                    matched_rule = threshold
                    break
            else:
                if cost_dec >= threshold.min_amount:
                    matched_rule = threshold
                    break

        if matched_rule:
            for approver in matched_rule.approvers:
                approvals_required.append(ApprovalRequirement(
                    approver=approver,
                    reason=f"Financial threshold check for ${cost_dec:,.2f} ({matched_rule.citation})",
                    rule_id=matched_rule.rule_id,
                ))

    # 3. Budget Check & Finance Exception (Policy Section 2)
    if budget_result:
        b_data = budget_result.get("data") or {}
        if not b_data.get("fits_in_budget", True) or b_data.get("risk_flag") == "budget_insufficient":
            shortfall = b_data.get("shortfall_usd", 0.0)
            risk_flags.append(RiskFlagItem(
                flag="budget_insufficient",
                severity="high",
                detail=f"Request exceeds available department budget by ${shortfall:,.2f}",
            ))
            if not any(a.approver == "Finance" for a in approvals_required):
                approvals_required.append(ApprovalRequirement(
                    approver="Finance",
                    reason="Budget exception approval required due to insufficient department funds",
                    rule_id="RULE-BUD-01",
                ))

    # 4. Security Triggers (Policy Section 5)
    data_access = (request.get("data_access_level") or "").lower()
    integrations = [str(i).lower() for i in request.get("requested_integrations") or []]

    security_triggers: list[str] = []

    if data_access in SECURITY_DATA_LEVEL_TRIGGERS:
        security_triggers.append(f"Sensitive data access level '{data_access}'")

    for trig in SECURITY_INTEGRATION_TRIGGERS:
        if any(trig in item for item in integrations):
            security_triggers.append(f"Integration touching sensitive environment matching '{trig}'")
            break

    # Vendor status security checks
    if vendor_result:
        v_data = vendor_result.get("data") or {}
        is_unavail = not vendor_result.get("ok") or v_data.get("is_unavailable")
        if is_unavail:
            risk_flags.append(RiskFlagItem(
                flag="vendor_risk_unavailable",
                severity="high",
                detail=vendor_result.get("error") or "Vendor risk assessment API is unavailable",
            ))
            security_triggers.append("External vendor risk API unavailable")

        if v_data.get("is_expired"):
            risk_flags.append(RiskFlagItem(
                flag="vendor_review_expired",
                severity="medium",
                detail=f"Vendor security review is expired (> {VENDOR_ASSESSMENT_VALIDITY_DAYS} days from {POLICY_REFERENCE_DATE})",
            ))
            security_triggers.append("Vendor security review expired")

        if v_data.get("has_conflict"):
            risk_flags.append(RiskFlagItem(
                flag="conflicting_vendor_evidence",
                severity="high",
                detail="Discrepancy detected between internal vendor registry and external vendor-risk API",
            ))
            security_triggers.append("Vendor assessment conflicting evidence")

        sec_status = v_data.get("security_review_status", "").lower()
        if sec_status in ["not_completed", "pending", "unknown"]:
            security_triggers.append(f"Vendor security assessment status is '{sec_status}'")

    if security_triggers:
        risk_flags.append(RiskFlagItem(
            flag="security_review_required",
            severity="high",
            detail="; ".join(security_triggers),
        ))
        if not any(a.approver == "Security" for a in approvals_required):
            approvals_required.append(ApprovalRequirement(
                approver="Security",
                reason=f"Mandatory security assessment required: {'; '.join(security_triggers)}",
                rule_id="RULE-SEC-01",
            ))

    # 5. Privacy Review Triggers (Policy Section 6)
    privacy_triggers: list[str] = []
    if data_access in PRIVACY_DATA_TRIGGERS:
        privacy_triggers.append(f"Request involves personal data: '{data_access}'")

    if vendor_result:
        v_data = vendor_result.get("data") or {}
        if v_data.get("stores_data_outside_region") and (data_access in PRIVACY_DATA_TRIGGERS or "confidential" in data_access):
            privacy_triggers.append("Vendor stores sensitive data outside operating jurisdiction")

    if privacy_triggers:
        risk_flags.append(RiskFlagItem(
            flag="privacy_review_required",
            severity="medium",
            detail="; ".join(privacy_triggers),
        ))
        if not any(a.approver == "Privacy" for a in approvals_required):
            approvals_required.append(ApprovalRequirement(
                approver="Privacy",
                reason=f"Privacy review triggered: {'; '.join(privacy_triggers)}",
                rule_id="RULE-PRIV-01",
            ))

    # 6. Legal Review Triggers (Policy Section 7)
    legal_triggers: list[str] = []
    if vendor_result:
        v_data = vendor_result.get("data") or {}
        is_new = v_data.get("is_new_vendor") or (v_data.get("procurement_status", "").lower() == "new")
        if is_new and cost_dec is not None and cost_dec >= LEGAL_NEW_VENDOR_THRESHOLD:
            legal_triggers.append(f"New vendor with annual spend ${cost_dec:,.2f} >= ${LEGAL_NEW_VENDOR_THRESHOLD:,.2f}")

        legal_status = v_data.get("legal_terms_status", "").lower()
        if legal_status in ["draft", "unknown"]:
            legal_triggers.append(f"Vendor legal terms status is '{legal_status}' (non-standard)")

        if v_data.get("stores_data_outside_region"):
            legal_triggers.append("Cross-region data transfer requires standard contractual clauses review")

    if legal_triggers:
        risk_flags.append(RiskFlagItem(
            flag="legal_review_required",
            severity="medium",
            detail="; ".join(legal_triggers),
        ))
        if not any(a.approver == "Legal" for a in approvals_required):
            approvals_required.append(ApprovalRequirement(
                approver="Legal",
                reason=f"Legal review required: {'; '.join(legal_triggers)}",
                rule_id="RULE-LEG-01",
            ))

    # 7. Prompt Injection Scan
    inj = injection_scan(request.get("business_justification"), context="business_justification")
    if inj.get("detected"):
        risk_flags.append(RiskFlagItem(
            flag="prompt_injection_detected",
            severity="high",
            detail=inj.get("flag_detail") or "Adversarial prompt injection pattern detected in business justification",
        ))

    # Deduplicate required approvals by name while maintaining order
    seen_approvers = set()
    deduped_approvals: list[ApprovalRequirement] = []
    for app in approvals_required:
        if app.approver not in seen_approvers:
            seen_approvers.add(app.approver)
            deduped_approvals.append(app)

    # Deterministic human review required if ANY risk flags or approvals beyond manager
    needs_human = len(risk_flags) > 0 or len(deduped_approvals) > 0 or (cost_dec is not None and cost_dec > Decimal("1000.00"))

    # Convert flag items to simple string tokens for evaluation compatibility
    string_flags = [f.flag for f in risk_flags]

    data = {
        "approvals_required": [a.model_dump() for a in deduped_approvals],
        "required_approvals": [a.approver for a in deduped_approvals],
        "risk_flags": string_flags,
        "risk_flag_details": [f.model_dump() for f in risk_flags],
        "missing_information": missing_information,
        "needs_human_review": bool(needs_human),
    }
    return ToolResult(ok=True, data=data, source="evaluate_policy").model_dump()


# ============================================================================
# Tool 6: get_purchase_history
# ============================================================================

def get_purchase_history(
    vendor_name: str | None = None,
    category: str | None = None,
    department: str | None = None,
) -> dict[str, Any]:
    """Retrieves previous purchase history to identify duplicates and recent spend."""
    try:
        history = _get_cached_csv("purchase_history.csv")
        results = []
        for h in history:
            match = True
            if vendor_name and vendor_name.strip().lower() not in h.get("vendor_name", "").lower():
                match = False
            if department and department.strip().lower() not in h.get("department", "").lower():
                match = False
            if match:
                results.append({
                    "purchase_id": h.get("purchase_id"),
                    "purchase_date": h.get("purchase_date"),
                    "department": h.get("department"),
                    "vendor_name": h.get("vendor_name"),
                    "product_name": h.get("product_name"),
                    "annual_amount_usd": int(h.get("annual_amount_usd", 0)),
                    "status": h.get("status"),
                    "notes": h.get("notes"),
                })

        data = {
            "query_vendor": vendor_name,
            "query_department": department,
            "results": results,
            "count": len(results),
        }
        return ToolResult(ok=True, data=data, source="get_purchase_history").model_dump()
    except Exception as exc:
        logger.exception("Error in get_purchase_history")
        return ToolResult(
            ok=False,
            source="get_purchase_history",
            error=f"Exception retrieving purchase history: {type(exc).__name__}: {exc}",
        ).model_dump()


# ============================================================================
# Tool Registry and JSON Schemas for LLM Tool-Calling
# ============================================================================

TOOL_MAP = {
    "get_request_and_employee": get_request_and_employee,
    "search_software_catalog": search_software_catalog,
    "check_budget": check_budget,
    "get_vendor_status": get_vendor_status,
    "evaluate_policy": evaluate_policy,
    "get_purchase_history": get_purchase_history,
}

TOOL_SCHEMAS = [
    {
        "name": "get_request_and_employee",
        "description": "Deterministic tool that retrieves purchase request details, requester profile, department, and direct reporting manager.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "The unique request ID, e.g. REQ-1001"}
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "search_software_catalog",
        "description": "Searches the internal approved software catalog for existing tools by name, category, or capability.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or tool name"},
                "category": {"type": "string", "description": "Software category to match"}
            },
        },
    },
    {
        "name": "check_budget",
        "description": "Deterministic tool that checks remaining department software budget and computes any shortfall.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {"type": "string", "description": "Department name, e.g. Marketing, Engineering"},
                "amount": {"type": "number", "description": "Annualized request amount in USD"}
            },
            "required": ["department", "amount"],
        },
    },
    {
        "name": "get_vendor_status",
        "description": "Retrieves vendor security review status, expiration date, and risk signals from the external service and internal registry.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "Vendor name, e.g. BrandBoard, NimbusAI"}
            },
            "required": ["vendor_name"],
        },
    },
    {
        "name": "evaluate_policy",
        "description": "Deterministic tool that applies policy rules, financial approval thresholds, and security/privacy triggers.",
        "parameters": {
            "type": "object",
            "properties": {
                "request": {"type": "object", "description": "The raw purchase request dictionary"},
                "budget_result": {"type": "object", "description": "Output from check_budget tool"},
                "vendor_result": {"type": "object", "description": "Output from get_vendor_status tool"}
            },
            "required": ["request"],
        },
    },
    {
        "name": "get_purchase_history",
        "description": "Retrieves historical purchase orders and agreements to check for existing vendor contracts or duplicate purchases.",
        "parameters": {
            "type": "object",
            "properties": {
                "vendor_name": {"type": "string", "description": "Filter by vendor name"},
                "category": {"type": "string", "description": "Filter by category"},
                "department": {"type": "string", "description": "Filter by department"}
            },
        },
    },
]
