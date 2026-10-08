"""Procurement policy configuration and threshold definitions.

Derived directly from data/procurement_policy.md (Policy version 2026.09).
Reference evaluation snapshot date: 2026-09-30.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import NamedTuple


# Snapshot reference date strictly mandated by policy
POLICY_REFERENCE_DATE = date(2026, 9, 30)
POLICY_VERSION = "2026.09"
POLICY_SOURCE_DOC = "data/procurement_policy.md"

# Vendor security assessment validity period in days
VENDOR_ASSESSMENT_VALIDITY_DAYS = 365


class ApprovalThreshold(NamedTuple):
    min_amount: Decimal
    max_amount: Decimal | None
    approvers: list[str]
    rule_id: str
    citation: str


# Deterministic Financial Approval Thresholds (Policy Section 4)
FINANCIAL_THRESHOLDS: list[ApprovalThreshold] = [
    ApprovalThreshold(
        min_amount=Decimal("0.00"),
        max_amount=Decimal("1000.00"),
        approvers=["Manager"],
        rule_id="RULE-FIN-01",
        citation="Policy Section 4 (Up to $1,000)",
    ),
    ApprovalThreshold(
        min_amount=Decimal("1000.01"),
        max_amount=Decimal("10000.00"),
        approvers=["Department Head", "Procurement"],
        rule_id="RULE-FIN-02",
        citation="Policy Section 4 ($1,000.01 - $10,000)",
    ),
    ApprovalThreshold(
        min_amount=Decimal("10000.01"),
        max_amount=Decimal("25000.00"),
        approvers=["Department Head", "Finance", "Procurement"],
        rule_id="RULE-FIN-03",
        citation="Policy Section 4 ($10,000.01 - $25,000)",
    ),
    ApprovalThreshold(
        min_amount=Decimal("25000.01"),
        max_amount=None,
        approvers=["Department Head", "Finance", "CFO", "Procurement"],
        rule_id="RULE-FIN-04",
        citation="Policy Section 4 (Above $25,000)",
    ),
]

# Sensitive data triggers for security review (Policy Section 5)
SECURITY_DATA_LEVEL_TRIGGERS = {
    "source_code",
    "production_telemetry",
    "confidential_documents",
    "customer_pii",
    "employee_pii",
    "credentials",
    "secrets",
}

# Integration triggers for security review (Policy Section 5)
SECURITY_INTEGRATION_TRIGGERS = [
    "git",
    "repository",
    "production",
    "cloud account",
    "aws",
    "gcp",
    "azure",
]

# Privacy review data triggers (Policy Section 6)
PRIVACY_DATA_TRIGGERS = {
    "customer_pii",
    "employee_pii",
}

# Legal review threshold for new vendors (Policy Section 7)
LEGAL_NEW_VENDOR_THRESHOLD = Decimal("10000.00")
