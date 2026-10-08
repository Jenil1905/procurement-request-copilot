from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent_a import run_agent_a
from src.contracts import Architecture, ProcurementDecision


def run(
    request_id_or_data: str | dict[str, Any],
    arch: str = "A",
    simulate_vendor_down: bool = False,
) -> ProcurementDecision:
    """Unified entrypoint for Procurement Copilot architectures.

    Args:
        request_id_or_data: Request identifier (e.g. 'REQ-1001') or raw request dict.
        arch: Architecture selection ('A', 'B', 'single', 'staged').
        simulate_vendor_down: Whether to simulate an external vendor API outage.

    Returns:
        ProcurementDecision: Validated and guardrailed decision contract.
    """
    arch_norm = str(arch).strip().lower()
    if arch_norm in ["b", "staged"]:
        from src.agent_b import run_agent_b
        return run_agent_b(request_id_or_data, simulate_vendor_down=simulate_vendor_down)
    else:
        return run_agent_a(request_id_or_data, simulate_vendor_down=simulate_vendor_down)


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Official assessment adapter callable by public and hidden evaluation harnesses."""
    return run(request_id, arch=str(architecture))


def main() -> None:
    """CLI runner for testing copilot recommendations directly from terminal."""
    parser = argparse.ArgumentParser(description="Procurement Copilot CLI")
    parser.add_argument("request_id", nargs="?", default="REQ-1001", help="Request ID, e.g. REQ-1001")
    parser.add_argument("--arch", choices=["A", "B", "single", "staged"], default="A", help="Architecture variant")
    parser.add_argument("--simulate-down", action="store_true", help="Simulate vendor API outage")
    args = parser.parse_args()

    print(f"Running Procurement Copilot: request_id={args.request_id}, arch={args.arch}")
    decision = run(args.request_id, arch=args.arch, simulate_vendor_down=args.simulate_down)
    print("\n" + "=" * 60)
    print(f"DECISION: {decision.recommendation.upper()}")
    print(f"Summary: {decision.summary}")
    print(f"Human review required: {decision.human_review_required}")
    print(f"Required approvals: {', '.join(decision.required_approvals)}")
    print(f"Risk flags: {', '.join(decision.risk_flags) if decision.risk_flags else 'None'}")
    if decision.missing_information:
        print(f"Missing information: {', '.join(decision.missing_information)}")
    print(f"Next step: {decision.next_step}")
    if decision.telemetry:
        tel = decision.telemetry
        print(f"Telemetry: {tel.llm_calls} LLM calls, {tel.tool_calls} tool calls, latency {tel.latency_ms} ms")
    print("=" * 60)
    print("\nFull JSON output:")
    print(json.dumps(decision.model_dump(), indent=2))


if __name__ == "__main__":
    main()
