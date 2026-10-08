"""Architecture B: Lightweight Staged 2-Agent Variant.

Agent 1 ("Evidence Gatherer"):
- Systematically executes tools and compiles a structured evidence bundle.
- Does NOT make any recommendation.

Agent 2 ("Decision Reviewer"):
- Receives the request and the evidence bundle from Agent 1 (no tool access).
- Explicitly tasked with challenging weak, missing, or conflicting evidence.
- Produces the candidate recommendation JSON.

Both agents share the same tools and pass through the identical deterministic guardrail layer.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.contracts import ProcurementDecision, RunTelemetry
from src.guardrails import apply_guardrails
from src.llm import LLMClient
from src.tools import (
    check_budget,
    evaluate_policy,
    get_purchase_history,
    get_request_and_employee,
    get_vendor_status,
    search_software_catalog,
)

logger = logging.getLogger(__name__)


class EvidenceBundle(BaseModel):
    """Structured evidence bundle produced by Agent 1 (Evidence Gatherer)."""
    request: dict[str, Any]
    executed_tools: dict[str, dict[str, Any]]
    key_findings: list[str] = Field(default_factory=list)
    unverified_aspects: list[str] = Field(default_factory=list)
    data_quality_signals: list[str] = Field(default_factory=list)


# ============================================================================
# Agent 1: Evidence Gatherer
# ============================================================================

def run_agent_1_evidence_gatherer(
    request_id_or_data: str | dict[str, Any],
    llm: LLMClient,
    simulate_vendor_down: bool = False,
) -> tuple[EvidenceBundle, dict[str, Any], list[dict[str, Any]], int, int, list[str]]:
    """Agent 1: Calls tools and packages a structured evidence bundle without making a recommendation."""
    llm_calls = 0
    tool_calls = 0
    tool_names: list[str] = []
    trace: list[dict[str, Any]] = []
    executed_tools: dict[str, dict[str, Any]] = {}

    # Step 1: Resolve Request and Requester
    raw_request: dict[str, Any] = {}
    if isinstance(request_id_or_data, dict):
        raw_request = dict(request_id_or_data)
        req_id = raw_request.get("request_id", "REQ-ADHOC")
    else:
        req_id = str(request_id_or_data)
        t_start = time.perf_counter()
        t1 = get_request_and_employee(req_id)
        tool_calls += 1
        tool_names.append("get_request_and_employee")
        executed_tools["get_request_and_employee"] = t1
        trace.append({
            "agent": "Agent 1 (Evidence Gatherer)",
            "tool": "get_request_and_employee",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "status": "ok" if t1.get("ok") else "error",
        })
        if t1.get("ok") and t1.get("data"):
            raw_request = t1["data"].get("request") or {"request_id": req_id}
            requester = t1["data"].get("requester") or {}
            if "department" not in raw_request and requester.get("department"):
                raw_request["department"] = requester["department"]
        else:
            raw_request = {"request_id": req_id}

    dept = raw_request.get("department")
    cost = raw_request.get("annual_cost_usd")
    vendor = raw_request.get("vendor_name")
    prod = raw_request.get("product_name")
    cat = raw_request.get("category")

    # Step 2: Catalog Overlap Search
    t_start = time.perf_counter()
    t2 = search_software_catalog(query=prod, category=cat)
    tool_calls += 1
    tool_names.append("search_software_catalog")
    executed_tools["search_software_catalog"] = t2
    trace.append({
        "agent": "Agent 1 (Evidence Gatherer)",
        "tool": "search_software_catalog",
        "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
        "status": "ok",
    })

    # Step 3: Budget Verification
    if dept:
        t_start = time.perf_counter()
        t3 = check_budget(department=dept, amount=cost)
        tool_calls += 1
        tool_names.append("check_budget")
        executed_tools["check_budget"] = t3
        trace.append({
            "agent": "Agent 1 (Evidence Gatherer)",
            "tool": "check_budget",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "status": "ok" if t3.get("ok") else "error",
        })

    # Step 4: Vendor Security Assessment
    if vendor:
        t_start = time.perf_counter()
        t4 = get_vendor_status(vendor, simulate_down=simulate_vendor_down)
        tool_calls += 1
        tool_names.append("get_vendor_status")
        executed_tools["get_vendor_status"] = t4
        trace.append({
            "agent": "Agent 1 (Evidence Gatherer)",
            "tool": "get_vendor_status",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "status": "ok" if t4.get("ok") else "error",
        })

    # Step 5: Deterministic Policy Evaluation
    t_start = time.perf_counter()
    pol_res = evaluate_policy(
        request=raw_request,
        budget_result=executed_tools.get("check_budget"),
        vendor_result=executed_tools.get("get_vendor_status"),
    )
    tool_calls += 1
    tool_names.append("evaluate_policy")
    executed_tools["evaluate_policy"] = pol_res
    trace.append({
        "agent": "Agent 1 (Evidence Gatherer)",
        "tool": "evaluate_policy",
        "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
        "status": "ok",
    })

    # Step 6: Purchase History Check (for additional context)
    if vendor:
        t_start = time.perf_counter()
        t6 = get_purchase_history(vendor_name=vendor)
        tool_calls += 1
        tool_names.append("get_purchase_history")
        executed_tools["get_purchase_history"] = t6
        trace.append({
            "agent": "Agent 1 (Evidence Gatherer)",
            "tool": "get_purchase_history",
            "duration_ms": round((time.perf_counter() - t_start) * 1000, 1),
            "status": "ok",
        })

    # LLM Call for Agent 1: Synthesize Evidence Bundle (no recommendation allowed)
    llm_calls += 1
    key_findings = []
    unverified = []
    signals = []

    if executed_tools.get("check_budget", {}).get("data"):
        b = executed_tools["check_budget"]["data"]
        key_findings.append(f"Budget: available=${b.get('available_usd', 0):,.2f}, shortfall=${b.get('shortfall_usd', 0):,.2f}")
    if executed_tools.get("search_software_catalog", {}).get("data"):
        c = executed_tools["search_software_catalog"]["data"]
        if c.get("has_overlap"):
            key_findings.append(f"Catalog overlap detected: {c.get('count')} matching tools found")
    if executed_tools.get("get_vendor_status", {}).get("data"):
        v = executed_tools["get_vendor_status"]["data"]
        if v.get("is_unavailable"):
            unverified.append("Vendor risk API unavailable: external security posture unconfirmed")
        elif v.get("is_expired"):
            unverified.append("Vendor security review is expired (> 365 days)")
        elif v.get("has_conflict"):
            unverified.append("Discrepancy detected between internal registry and external vendor-risk API")

    bundle = EvidenceBundle(
        request=raw_request,
        executed_tools=executed_tools,
        key_findings=key_findings,
        unverified_aspects=unverified,
        data_quality_signals=signals,
    )

    return bundle, raw_request, trace, llm_calls, tool_calls, tool_names


# ============================================================================
# Agent 2: Decision Reviewer
# ============================================================================

def run_agent_2_decision_reviewer(
    bundle: EvidenceBundle,
    llm: LLMClient,
) -> tuple[dict[str, Any], int]:
    """Agent 2: Challenges evidence and formulates recommendation JSON without tool access."""
    llm_calls = 1

    reviewer_instructions = (
        "You are Agent 2 ('Decision Reviewer'). Your job is to rigorously review the evidence gathered by Agent 1.\n"
        "CHALLENGE WEAK, MISSING, OR CONFLICTING EVIDENCE:\n"
        "- If vendor assessment is unavailable or expired, do not assume favorable status.\n"
        "- If request has software overlap with existing catalog items, push towards 'use_existing_tool'.\n"
        "- If material fields (cost, seats, data level) are missing, recommend 'needs_more_info'.\n"
        "- If budget has shortfall or sensitive data is touched, enforce human escalation.\n"
        "- NEVER output 'approved'. The most you can recommend is 'approve_to_proceed'."
    )

    candidate = llm.generate_recommendation_json(
        request=bundle.request,
        executed_tools=bundle.executed_tools,
        instructions=reviewer_instructions,
    )
    return candidate, llm_calls


# ============================================================================
# Architecture B Main Entrypoint
# ============================================================================

def run_agent_b(
    request_id_or_data: str | dict[str, Any],
    llm_client: LLMClient | None = None,
    simulate_vendor_down: bool = False,
) -> ProcurementDecision:
    """Executes Architecture B: Staged 2-Agent pipeline with guardrail enforcement."""
    start_time = time.perf_counter()
    llm = llm_client or LLMClient()

    # Phase 1: Evidence Gathering
    bundle, raw_request, trace, a1_llm, a1_tools, tool_names = run_agent_1_evidence_gatherer(
        request_id_or_data,
        llm=llm,
        simulate_vendor_down=simulate_vendor_down,
    )

    # Phase 2: Decision Review
    candidate_json, a2_llm = run_agent_2_decision_reviewer(
        bundle=bundle,
        llm=llm,
    )

    # Phase 3: Deterministic Guardrails (Identical to Architecture A)
    total_llm_calls = a1_llm + a2_llm
    total_tool_calls = a1_tools
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    telemetry = RunTelemetry(
        llm_calls=total_llm_calls,
        tool_calls=total_tool_calls,
        tool_names=tool_names,
        latency_ms=round(elapsed_ms, 1),
    )

    pol_res = bundle.executed_tools.get("evaluate_policy", {})

    decision = apply_guardrails(
        candidate=candidate_json,
        request=raw_request,
        executed_tools=bundle.executed_tools,
        policy_eval_result=pol_res,
        telemetry=telemetry,
    )

    return decision
