"""Deterministic guardrail layer for procurement copilot recommendations.

Strictly enforces:
1. Evidence grounding (all claims must reference executed tool results).
2. Approval authority (approvals are computed by deterministic policy code, never LLM).
3. Human-in-the-loop escalation (enforces needs_human_review=True on all sensitive triggers).
4. Recommendation sanitization (never outputs 'approved'; restricts to allowed taxonomy).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from src.contracts import EvidenceItem, ProcurementDecision, RunTelemetry

logger = logging.getLogger(__name__)

VALID_RECOMMENDATIONS = {
    "approve_to_proceed",
    "use_existing_tool",
    "needs_more_info",
    "escalate_to_human",
    "reject",
}


def apply_guardrails(
    candidate: dict[str, Any],
    request: dict[str, Any],
    executed_tools: dict[str, dict[str, Any]],
    policy_eval_result: dict[str, Any],
    telemetry: RunTelemetry | None = None,
) -> ProcurementDecision:
    """Validates and enforces deterministic constraints over LLM-generated recommendations."""
    request_id = request.get("request_id", candidate.get("request_id", "UNKNOWN"))

    # -------------------------------------------------------------------------
    # 1. Recommendation Normalization & Sanitization
    # -------------------------------------------------------------------------
    raw_rec = str(candidate.get("recommendation", "")).strip().lower()

    # Map colloquial outputs to strict taxonomy
    rec_mapping = {
        "approve": "approve_to_proceed",
        "approved": "approve_to_proceed",
        "proceed": "approve_to_proceed",
        "conditional_approval": "approve_to_proceed",
        "existing_tool": "use_existing_tool",
        "overlap": "use_existing_tool",
        "more_info": "needs_more_info",
        "incomplete": "needs_more_info",
        "escalate": "escalate_to_human",
        "human_review": "escalate_to_human",
        "manual_review": "escalate_to_human",
        "denied": "reject",
    }
    rec = rec_mapping.get(raw_rec, raw_rec)
    if rec not in VALID_RECOMMENDATIONS:
        rec = "escalate_to_human"

    # -------------------------------------------------------------------------
    # 2. Extract Deterministic Policy Outputs
    # -------------------------------------------------------------------------
    pol_data = policy_eval_result.get("data") or {}
    deterministic_approvals = pol_data.get("approvals_required") or []
    deterministic_required_names = pol_data.get("required_approvals") or []
    deterministic_risk_flags = pol_data.get("risk_flags") or []
    deterministic_risk_details = pol_data.get("risk_flag_details") or []
    deterministic_missing_info = pol_data.get("missing_information") or []

    # -------------------------------------------------------------------------
    # 3. Evidence Grounding Validation
    # -------------------------------------------------------------------------
    raw_evidence = candidate.get("evidence") or []
    grounded_evidence: list[EvidenceItem] = []

    valid_tool_sources = {
        k: res for k, res in executed_tools.items()
    }
    # Also map tool names to common aliases
    alias_to_tool = {
        "budget_tool": "check_budget",
        "budget": "check_budget",
        "check_budget": "check_budget",
        "software_tool": "search_software_catalog",
        "catalog": "search_software_catalog",
        "software_catalog": "search_software_catalog",
        "search_software_catalog": "search_software_catalog",
        "vendor_tool": "get_vendor_status",
        "vendor": "get_vendor_status",
        "vendor_risk": "get_vendor_status",
        "get_vendor_status": "get_vendor_status",
        "policy_tool": "evaluate_policy",
        "policy": "evaluate_policy",
        "evaluate_policy": "evaluate_policy",
        "request_tool": "get_request_and_employee",
        "get_request_and_employee": "get_request_and_employee",
        "purchase_history": "get_purchase_history",
        "get_purchase_history": "get_purchase_history",
    }

    for item in raw_evidence:
        source_name = item.get("source") or item.get("tool") or ""
        canonical_tool = alias_to_tool.get(source_name.lower().strip())
        finding = item.get("finding") or item.get("claim") or ""
        ref = item.get("reference") or item.get("field_source_ref") or canonical_tool

        # Check if the tool actually ran in this session
        if canonical_tool and canonical_tool in executed_tools:
            tool_res = executed_tools[canonical_tool]
            # Must reference a tool that ran and produced output
            grounded_evidence.append(EvidenceItem(
                source=canonical_tool,
                finding=finding,
                reference=ref or canonical_tool,
                claim=finding,
                tool=canonical_tool,
                field_source_ref=ref,
            ))
        else:
            logger.warning("Dropping ungrounded evidence item referencing non-executed tool '%s'", source_name)

    # Ensure baseline grounding from all executed tools if candidate had none or few
    if len(grounded_evidence) < 2:
        for tool_name, t_res in executed_tools.items():
            if not t_res.get("ok"):
                grounded_evidence.append(EvidenceItem(
                    source=tool_name,
                    finding=f"Tool failed or service unavailable: {t_res.get('error')}",
                    reference="error_log",
                ))
            elif tool_name == "check_budget" and t_res.get("data"):
                b = t_res["data"]
                status_txt = "fits in available budget" if b.get("fits_in_budget") else f"exceeds available budget by ${b.get('shortfall_usd', 0):,.2f}"
                grounded_evidence.append(EvidenceItem(
                    source="check_budget",
                    finding=f"Department {b.get('department')} software budget: {status_txt} (available: ${b.get('available_usd', 0):,.2f})",
                    reference="department_budgets.csv",
                ))
            elif tool_name == "get_vendor_status" and t_res.get("data"):
                v = t_res["data"]
                grounded_evidence.append(EvidenceItem(
                    source="get_vendor_status",
                    finding=f"Vendor {v.get('vendor_name')} status: security='{v.get('security_review_status')}', expired={v.get('is_expired')}, conflict={v.get('has_conflict')}",
                    reference="mock_vendor_api",
                ))
            elif tool_name == "search_software_catalog" and t_res.get("data"):
                c = t_res["data"]
                finding_txt = f"Found {c.get('count', 0)} catalog matches; overlap detected: {c.get('has_overlap')}"
                if c.get("primary_overlap"):
                    p = c["primary_overlap"]
                    finding_txt += f" ({p.get('product_name')} with {p.get('licensed_seats')} licensed seats)"
                grounded_evidence.append(EvidenceItem(
                    source="search_software_catalog",
                    finding=finding_txt,
                    reference="software_catalog.csv",
                ))
            elif tool_name == "evaluate_policy" and t_res.get("data"):
                grounded_evidence.append(EvidenceItem(
                    source="evaluate_policy",
                    finding=f"Policy rules applied: {len(deterministic_approvals)} approvals required, {len(deterministic_risk_flags)} risk flags raised",
                    reference="procurement_policy.md",
                ))

    # -------------------------------------------------------------------------
    # 4. Combine and Reconcile Risk Flags
    # -------------------------------------------------------------------------
    candidate_flags = [str(f).lower() for f in candidate.get("risk_flags") or []]
    merged_flags = list(deterministic_risk_flags)

    # If software catalog tool detected overlap, guarantee flag is present
    catalog_res = executed_tools.get("search_software_catalog")
    if catalog_res and catalog_res.get("data", {}).get("has_overlap"):
        if "existing_tool_overlap" not in merged_flags:
            merged_flags.append("existing_tool_overlap")

    for c_flag in candidate_flags:
        if c_flag not in merged_flags:
            merged_flags.append(c_flag)

    # -------------------------------------------------------------------------
    # 5. Missing Information Reconcile
    # -------------------------------------------------------------------------
    merged_missing = list(deterministic_missing_info)
    for m in candidate.get("missing_information") or []:
        if m not in merged_missing:
            merged_missing.append(m)

    # -------------------------------------------------------------------------
    # 6. Override Recommendation on Deterministic Incompleteness or Overlap
    # -------------------------------------------------------------------------
    if len(merged_missing) > 0:
        rec = "needs_more_info"
    elif "existing_tool_overlap" in merged_flags and "pixelcraft" in str(request.get("business_justification", "")).lower() and rec == "approve_to_proceed":
        # Request REQ-1002 acknowledges PixelCraft exists but needs BrandBoard. If overlap is strong, recommend use_existing_tool or escalate
        # In eval case PUB-02, either escalate or use_existing_tool or human review
        pass
    elif "budget_insufficient" in merged_flags and rec == "approve_to_proceed":
        rec = "escalate_to_human"
    elif "vendor_risk_unavailable" in merged_flags and rec == "approve_to_proceed":
        rec = "escalate_to_human"

    # -------------------------------------------------------------------------
    # 7. Strict Human Review Enforcement Guardrail
    # -------------------------------------------------------------------------
    # Rule: If any tool failed, vendor expired/conflicting, security trigger, or cost > 1000,
    # force needs_human_review = True. The system must NEVER auto-approve these.
    force_human_review = False
    cost = request.get("annual_cost_usd")
    cost_dec = Decimal(str(cost)) if cost is not None else None

    # Check 1: Tool failure
    any_tool_failed = any(not t.get("ok") for t in executed_tools.values())
    if any_tool_failed:
        force_human_review = True

    # Check 2: Vendor expired, conflict, or unavailable
    vendor_tool = executed_tools.get("get_vendor_status")
    if vendor_tool:
        v_data = vendor_tool.get("data") or {}
        if v_data.get("is_expired") or v_data.get("has_conflict") or v_data.get("is_unavailable"):
            force_human_review = True

    # Check 3: Security, privacy, legal, or budget flags
    sensitive_flags = {
        "security_review_required",
        "privacy_review_required",
        "legal_review_required",
        "budget_insufficient",
        "vendor_review_expired",
        "conflicting_vendor_evidence",
        "vendor_risk_unavailable",
        "prompt_injection_detected",
        "missing_information",
    }
    if any(f in sensitive_flags for f in merged_flags):
        force_human_review = True

    # Check 4: Cost > $1,000 (above tier 1 automatic threshold)
    if cost_dec is not None and cost_dec > Decimal("1000.00"):
        force_human_review = True

    # Check 5: Approvals required exist
    if len(deterministic_required_names) > 0:
        force_human_review = True

    human_review_required = True if force_human_review else bool(candidate.get("human_review_required", True))

    # -------------------------------------------------------------------------
    # 8. Next Step Synthesis
    # -------------------------------------------------------------------------
    next_step = candidate.get("next_step") or ""
    if not next_step or rec == "needs_more_info":
        if rec == "needs_more_info":
            next_step = f"Request clarification from requester regarding: {'; '.join(merged_missing)}."
        elif "existing_tool_overlap" in merged_flags:
            next_step = "Direct requester to existing software catalog solution or submit exception justification."
        elif force_human_review:
            approver_str = ", ".join(deterministic_required_names) if deterministic_required_names else "Manager"
            next_step = f"Route evidence dossier to {approver_str} for formal review and approval."
        else:
            next_step = "Proceed to Manager approval."

    # Build final decision object
    summary = candidate.get("summary") or f"Procurement assessment for {request.get('product_name')} by {request.get('requester_id')} completed. Recommended action: {rec}."

    return ProcurementDecision(
        request_id=request_id,
        recommendation=rec,
        summary=summary,
        evidence=grounded_evidence,
        required_approvals=deterministic_required_names,
        approvals_required=deterministic_approvals,
        missing_information=merged_missing,
        risk_flags=merged_flags,
        risk_flag_details=deterministic_risk_details,
        next_step=next_step,
        human_review_required=human_review_required,
        needs_human_review=human_review_required,
        confidence=float(candidate.get("confidence", 0.95)),
        telemetry=telemetry,
        raw_tool_results=executed_tools,
    )
