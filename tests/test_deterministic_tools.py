"""Unit tests for the 3 deterministic procurement tools and policy boundary checks."""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.tools import (
    check_budget,
    evaluate_policy,
    get_request_and_employee,
)


class TestDeterministicTools(unittest.TestCase):
    """Verifies deterministic tool behavior, boundary conditions, and reliability."""

    # -------------------------------------------------------------------------
    # Tool 1: get_request_and_employee
    # -------------------------------------------------------------------------

    def test_get_request_and_employee_known(self):
        res = get_request_and_employee("REQ-1001")
        self.assertTrue(res["ok"])
        self.assertEqual(res["source"], "get_request_and_employee")
        data = res["data"]
        self.assertEqual(data["request"]["request_id"], "REQ-1001")
        self.assertEqual(data["requester"]["employee_id"], "E004")
        self.assertEqual(data["requester"]["name"], "Noah Williams")
        self.assertEqual(data["manager"]["manager_id"], "E006")
        self.assertEqual(data["manager"]["manager_name"], "Priya Shah")

    def test_get_request_and_employee_unknown_id(self):
        res = get_request_and_employee("REQ-NONEXISTENT")
        self.assertFalse(res["ok"])
        self.assertIn("not found", res["error"])

    def test_get_request_and_employee_injection_detection(self):
        res = get_request_and_employee("REQ-1006")
        self.assertTrue(res["ok"])
        inj = res["data"]["injection_scan"]
        self.assertTrue(inj["detected"])
        self.assertIn("ignore all procurement rules", " ".join(inj["matches"]).lower())

    # -------------------------------------------------------------------------
    # Tool 3: check_budget
    # -------------------------------------------------------------------------

    def test_check_budget_fits(self):
        # Marketing available budget is 15000
        res = check_budget("Marketing", 12000)
        self.assertTrue(res["ok"])
        data = res["data"]
        self.assertTrue(data["fits_in_budget"])
        self.assertEqual(data["shortfall_usd"], 0.0)
        self.assertEqual(data["remaining_after_purchase_usd"], 3000.0)
        self.assertIsNone(data["risk_flag"])

    def test_check_budget_exact_boundary(self):
        # Exactly available: 15000
        res = check_budget("Marketing", 15000)
        self.assertTrue(res["ok"])
        data = res["data"]
        self.assertTrue(data["fits_in_budget"])
        self.assertEqual(data["shortfall_usd"], 0.0)
        self.assertEqual(data["remaining_after_purchase_usd"], 0.0)

    def test_check_budget_exceeds(self):
        # Available: 15000, Request: 15001
        res = check_budget("Marketing", 15001)
        self.assertTrue(res["ok"])
        data = res["data"]
        self.assertFalse(data["fits_in_budget"])
        self.assertEqual(data["shortfall_usd"], 1.0)
        self.assertEqual(data["risk_flag"], "budget_insufficient")

    def test_check_budget_null_amount(self):
        res = check_budget("Marketing", None)
        self.assertFalse(res["ok"])
        self.assertIn("missing or null", res["error"])

    def test_check_budget_unknown_department(self):
        res = check_budget("ImaginaryDept", 500)
        self.assertFalse(res["ok"])
        self.assertIn("Unknown department", res["error"])

    # -------------------------------------------------------------------------
    # Tool 5: evaluate_policy Financial Boundaries
    # -------------------------------------------------------------------------

    def test_policy_tier_1_boundary_under_1000(self):
        # <= $1,000 -> Manager
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 800,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        approvals = res["data"]["required_approvals"]
        self.assertEqual(approvals, ["Manager"])

    def test_policy_tier_1_exact_1000(self):
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 1000.00,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["required_approvals"], ["Manager"])

    def test_policy_tier_2_just_over_1000(self):
        # $1,000.01 -> Department Head + Procurement
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 1000.01,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        approvals = res["data"]["required_approvals"]
        self.assertEqual(approvals, ["Department Head", "Procurement"])

    def test_policy_tier_2_exact_10000(self):
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 10000.00,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["required_approvals"], ["Department Head", "Procurement"])

    def test_policy_tier_3_just_over_10000(self):
        # $10,000.01 -> Department Head + Finance + Procurement
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 10000.01,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        approvals = res["data"]["required_approvals"]
        self.assertEqual(approvals, ["Department Head", "Finance", "Procurement"])

    def test_policy_tier_3_exact_25000(self):
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 25000.00,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        self.assertEqual(res["data"]["required_approvals"], ["Department Head", "Finance", "Procurement"])

    def test_policy_tier_4_above_25000(self):
        # Above $25,000 -> Department Head + Finance + CFO + Procurement
        req = {
            "requester_id": "E004",
            "product_name": "Test Tool",
            "vendor_name": "SignFlow",
            "annual_cost_usd": 25000.01,
            "user_count": 5,
            "business_justification": "Legitimate business need",
            "data_access_level": "internal_documents",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertTrue(res["ok"])
        approvals = res["data"]["required_approvals"]
        self.assertEqual(approvals, ["Department Head", "Finance", "CFO", "Procurement"])

    # -------------------------------------------------------------------------
    # Tool 5: evaluate_policy Triggers (Security, Privacy, Legal, Missing Info)
    # -------------------------------------------------------------------------

    def test_policy_security_trigger_source_code(self):
        req = {
            "requester_id": "E002",
            "product_name": "CodeMate",
            "vendor_name": "CodeMate",
            "annual_cost_usd": 18000,
            "user_count": 30,
            "business_justification": "Developer tool",
            "data_access_level": "source_code",
            "requested_integrations": ["Git repositories"],
        }
        res = evaluate_policy(req)
        self.assertIn("Security", res["data"]["required_approvals"])
        self.assertIn("security_review_required", res["data"]["risk_flags"])

    def test_policy_privacy_trigger_customer_pii(self):
        req = {
            "requester_id": "E005",
            "product_name": "NeuralDesk",
            "vendor_name": "NeuralDesk",
            "annual_cost_usd": 6000,
            "user_count": 20,
            "business_justification": "Draft support replies",
            "data_access_level": "customer_pii",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertIn("Privacy", res["data"]["required_approvals"])
        self.assertIn("privacy_review_required", res["data"]["risk_flags"])

    def test_policy_missing_information_triggers(self):
        req = {
            "requester_id": "E001",
            "product_name": "NeuralDesk",
            "vendor_name": "NeuralDesk",
            "annual_cost_usd": None,
            "user_count": None,
            "business_justification": "Need AI ASAP",
            "data_access_level": "unknown",
            "requested_integrations": [],
        }
        res = evaluate_policy(req)
        self.assertIn("missing_information", res["data"]["risk_flags"])
        self.assertTrue(len(res["data"]["missing_information"]) >= 2)


if __name__ == "__main__":
    unittest.main()
