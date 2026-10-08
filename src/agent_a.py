"""Architecture A: Single-Agent Baseline with iterative tool calling loop and guardrails.

Workflow:
1. Tool calling in an agent loop (up to 8 steps).
2. Record per-run telemetry: LLM calls, tool calls, tool names, latency, and full trace.
3. One structured-output synthesis call.
4. Deterministic guardrail layer enforcing policy, grounding, and human review.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.contracts import ProcurementDecision, RunTelemetry
from src.guardrails import apply_guardrails
from src.llm import LLMClient
from src.tools import (
    TOOL_MAP,
    check_budget,
    evaluate_policy,
    get_request_and_employee,
    get_vendor_status,
    search_software_catalog,
)

logger = logging.getLogger(__name__)


def run_agent_a(
    request_id_or_data: str | dict[str, Any],
    llm_client: LLMClient | None = None,
    simulate_vendor_down: bool = False,
) -> ProcurementDecision:
    """Executes Architecture A: Single-agent workflow with tool calling and guardrails."""
    start_time = time.perf_counter()
    llm = llm_client or LLMClient()

    llm_calls = 0
    tool_calls = 0
    tool_names: list[str] = []
    trace: list[dict[str, Any]] = []
    executed_tools: dict[str, dict[str, Any]] = {}

    # 1. Resolve initial request data
    raw_request: dict[str, Any] = {}
    if isinstance(request_id_or_data, dict):
        raw_request = dict(request_id_or_data)
        req_id = raw_request.get("request_id", "REQ-ADHOC")
    else:
        req_id = str(request_id_or_data)
        # Execute tool 1 immediately to resolve request and employee
        t1_start = time.perf_counter()
        t1_res = get_request_and_employee(req_id)
        t1_dur = (time.perf_counter() - t1_start) * 1000
        tool_calls += 1
        tool_names.append("get_request_and_employee")
        executed_tools["get_request_and_employee"] = t1_res
        trace.append({
            "step": 1,
            "tool": "get_request_and_employee",
            "duration_ms": round(t1_dur, 1),
            "status": "ok" if t1_res.get("ok") else "error",
            "summary": f"Loaded request {req_id}",
        })
        if t1_res.get("ok") and t1_res.get("data"):
            raw_request = t1_res["data"].get("request") or {"request_id": req_id}
            # Enrich with employee department if available
            requester = t1_res["data"].get("requester") or {}
            if "department" not in raw_request and requester.get("department"):
                raw_request["department"] = requester["department"]
        else:
            raw_request = {"request_id": req_id}

    # 2. Tool Calling Loop (Max 8 Steps)
    max_steps = 8
    step_num = len(trace)

    while step_num < max_steps:
        step_num += 1
        llm_calls += 1

        # Query LLM planner for next tool
        next_action = llm.plan_next_tool_call(raw_request, executed_tools, step_num)
        if not next_action:
            break

        tool_name = next_action.get("name")
        tool_args = next_action.get("args") or {}

        if not tool_name or tool_name not in TOOL_MAP:
            break

        # Prevent redundant loops
        if tool_name in executed_tools and len(executed_tools) >= 5:
            break

        # Execute selected tool
        t_func = TOOL_MAP[tool_name]
        t_start = time.perf_counter()

        # Handle simulation overrides
        if tool_name == "get_vendor_status" and simulate_vendor_down:
            tool_args["simulate_down"] = True

        try:
            res = t_func(**tool_args)
        except Exception as exc:
            logger.exception("Error executing tool %s", tool_name)
            res = {"ok": False, "source": tool_name, "error": str(exc), "data": None}

        t_dur = (time.perf_counter() - t_start) * 1000
        tool_calls += 1
        tool_names.append(tool_name)
        executed_tools[tool_name] = res

        trace.append({
            "step": step_num,
            "tool": tool_name,
            "duration_ms": round(t_dur, 1),
            "status": "ok" if res.get("ok") else "error",
            "summary": f"Executed {tool_name} with {tool_args}",
        })

    # 3. Ensure Deterministic Checks Are Completed
    # Under FDE design principles, evaluate_policy must run deterministically
    dept = raw_request.get("department")
    cost = raw_request.get("annual_cost_usd")
    vendor = raw_request.get("vendor_name")

    # If requester tool loaded employee department, use it
    if "get_request_and_employee" in executed_tools:
        req_tool = executed_tools["get_request_and_employee"]
        if req_tool.get("ok") and req_tool.get("data"):
            req_info = req_tool["data"].get("requester") or {}
            if not dept and req_info.get("department"):
                dept = req_info["department"]
                raw_request["department"] = dept

    # Fallback to defaults from dataset if not already executed
    if "search_software_catalog" not in executed_tools:
        executed_tools["search_software_catalog"] = search_software_catalog(
            query=raw_request.get("product_name"),
            category=raw_request.get("category"),
        )
        tool_calls += 1
        tool_names.append("search_software_catalog")

    if "check_budget" not in executed_tools and dept:
        executed_tools["check_budget"] = check_budget(department=dept, amount=cost)
        tool_calls += 1
        tool_names.append("check_budget")

    if "get_vendor_status" not in executed_tools and vendor:
        executed_tools["get_vendor_status"] = get_vendor_status(vendor, simulate_down=simulate_vendor_down)
        tool_calls += 1
        tool_names.append("get_vendor_status")

    if "evaluate_policy" not in executed_tools:
        pol_res = evaluate_policy(
            request=raw_request,
            budget_result=executed_tools.get("check_budget"),
            vendor_result=executed_tools.get("get_vendor_status"),
        )
        executed_tools["evaluate_policy"] = pol_res
        tool_calls += 1
        tool_names.append("evaluate_policy")
    else:
        pol_res = executed_tools["evaluate_policy"]

    # 4. Structured Synthesis LLM Call
    llm_calls += 1
    candidate_json = llm.generate_recommendation_json(
        request=raw_request,
        executed_tools=executed_tools,
        instructions="Architecture A: Single agent end-to-end evaluation.",
    )

    # 5. Guardrail Layer
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    telemetry = RunTelemetry(
        llm_calls=llm_calls,
        tool_calls=tool_calls,
        tool_names=tool_names,
        latency_ms=round(elapsed_ms, 1),
    )

    decision = apply_guardrails(
        candidate=candidate_json,
        request=raw_request,
        executed_tools=executed_tools,
        policy_eval_result=pol_res,
        telemetry=telemetry,
    )

    return decision
