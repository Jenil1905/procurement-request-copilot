from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class EvidenceItem(BaseModel):
    source: str = Field(default="", description="Tool/data source name")
    finding: str = Field(default="", description="Concise factual finding")
    reference: str | None = Field(default=None, description="Optional record ID / policy section / endpoint")
    claim: str | None = Field(default=None, description="Claim text (alias for finding)")
    tool: str | None = Field(default=None, description="Tool name (alias for source)")
    field_source_ref: str | None = Field(default=None, description="Field or source reference")

    @model_validator(mode="before")
    @classmethod
    def sync_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize claim <-> finding
            if "claim" in data and not data.get("finding"):
                data["finding"] = data["claim"]
            elif "finding" in data and not data.get("claim"):
                data["claim"] = data["finding"]

            # Synchronize tool <-> source
            if "tool" in data and not data.get("source"):
                data["source"] = data["tool"]
            elif "source" in data and not data.get("tool"):
                data["tool"] = data["source"]

            # Synchronize field_source_ref <-> reference
            if "field_source_ref" in data and not data.get("reference"):
                data["reference"] = data["field_source_ref"]
            elif "reference" in data and not data.get("field_source_ref"):
                data["field_source_ref"] = data["reference"]
        return data


class RunTelemetry(BaseModel):
    llm_calls: int | None = None
    tool_calls: int | None = None
    tool_names: list[str] = Field(default_factory=list)
    latency_ms: float | None = None


class ApprovalRequirementItem(BaseModel):
    approver: str
    reason: str
    rule_id: str


class RiskFlagItemDetail(BaseModel):
    flag: str
    severity: str = "medium"
    detail: str


class ProcurementDecision(BaseModel):
    request_id: str
    recommendation: str = Field(description="Recommendation: approve_to_proceed | use_existing_tool | needs_more_info | escalate_to_human | reject")
    summary: str = Field(default="", description="Summary of the rationale")
    evidence: list[EvidenceItem] = Field(default_factory=list)
    required_approvals: list[str] = Field(default_factory=list)
    approvals_required: list[ApprovalRequirementItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    risk_flag_details: list[RiskFlagItemDetail] = Field(default_factory=list)
    next_step: str = Field(default="")
    human_review_required: bool = True
    needs_human_review: bool = True
    confidence: float = 1.0
    telemetry: RunTelemetry | None = None
    raw_tool_results: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def sync_review_flags(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync human_review_required <-> needs_human_review
            if "needs_human_review" in data and "human_review_required" not in data:
                data["human_review_required"] = data["needs_human_review"]
            elif "human_review_required" in data and "needs_human_review" not in data:
                data["needs_human_review"] = data["human_review_required"]

            # Sync required_approvals <-> approvals_required
            if "approvals_required" in data and data["approvals_required"] and not data.get("required_approvals"):
                data["required_approvals"] = [
                    a.get("approver") if isinstance(a, dict) else getattr(a, "approver", str(a))
                    for a in data["approvals_required"]
                ]
            elif "required_approvals" in data and data["required_approvals"] and not data.get("approvals_required"):
                data["approvals_required"] = [
                    {"approver": str(a), "reason": "Policy approval required", "rule_id": "RULE-POLICY"}
                    for a in data["required_approvals"]
                ]
        return data


Architecture = Literal["single", "staged", "A", "B"]
