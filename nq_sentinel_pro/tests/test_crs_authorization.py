"""No live calls: final authorization packet contract and metadata boundary."""
import json
import unittest
from copy import deepcopy
from unittest.mock import Mock

from sentinel.crs import authorization
from sentinel.crs.admission import parse_payload


class AuthorizationTests(unittest.TestCase):
    def test_exact_three_fixed_requests_and_no_execution_authority(self):
        plan = authorization.load_plan()
        self.assertFalse(plan["approved"])
        self.assertEqual(plan["maximum_market_data_requests"], 3)
        self.assertEqual(len(plan["requests"]), 3)
        self.assertEqual([r["rate_type"] for r in plan["requests"]], ["sofr", "tgcr", "bgcr"])
        self.assertTrue(all(r["method"] == "GET" and r["data_date"] == "2026-11-19" for r in plan["requests"]))
        self.assertFalse(plan["controls"]["redirects"])
        self.assertEqual(plan["controls"]["retries"], 0)

    def test_plan_drift_is_rejected_before_any_action(self):
        for alteration in ("approved", "request", "log_scope", "body_cap"):
            plan = deepcopy(authorization.load_plan())
            if alteration == "approved":
                plan["approved"] = True
            elif alteration == "request":
                plan["requests"][0]["url"] += "&newScope=all"
            elif alteration == "log_scope":
                plan["retained_diagnostic_fields"].append("percent")
            else:
                plan["controls"]["maximum_body_bytes_per_request"] *= 2
            with self.assertRaises(ValueError):
                authorization.validate_plan(plan)

    def test_response_numbers_body_and_exception_messages_cannot_be_logged(self):
        for key in ("percent", "percentRate", "volume", "body", "headers", "exception_message", "body_sha256"):
            with self.assertRaises(ValueError):
                authorization.safe_diagnostic({key: "forbidden"})

    def test_safe_metadata_is_typed_and_cannot_hide_raw_response(self):
        sample = {"rate_type": "sofr", "http_status": 200, "record_count": 1,
            "observation_date": "2026-11-19", "error_code": "NONE", "elapsed_ms": 100,
            "started_at": "2026-11-22T00:00:00+00:00"}
        self.assertEqual(authorization.safe_diagnostic(sample), sample)
        for bad in ({"rate_type": "raw response"}, {"error_code": "server text"},
                    {"record_count": {"percent": 3.5}}, {"observation_date": "not-a-date"}):
            with self.assertRaises(ValueError):
                authorization.safe_diagnostic(bad)

    def test_documented_percent_field_parses_without_rate_alias(self):
        payload = {"refRates": [{"effectiveDate": "2026-11-19", "type": "SOFR", "percent": 3.5}]}
        row = parse_payload("new_york_fed", json.dumps(payload).encode(),
            decision_at="2026-11-22T00:00:00+00:00", retrieved_at="2026-11-22T00:00:00+00:00")[0]
        self.assertEqual(row["value"], 3.5)
        self.assertEqual(row["source_field"], "percent")
        self.assertEqual(row["schema_status"], "DOCUMENTED_FIELD_MAPPING_NOT_LIVE_VERIFIED")

    def test_conflicting_rate_fields_are_not_silently_selected(self):
        payload = {"refRates": [{"effectiveDate": "2026-11-19", "type": "SOFR", "percent": 3.5, "percentRate": 4.5}]}
        with self.assertRaises(ValueError):
            parse_payload("new_york_fed", json.dumps(payload).encode(),
                decision_at="2026-11-22T00:00:00+00:00", retrieved_at="2026-11-22T00:00:00+00:00")

    def test_legacy_synthetic_alias_is_explicitly_not_live_schema(self):
        payload = {"refRates": [{"effectiveDate": "2026-11-19", "type": "SOFR", "percentRate": 3.5}]}
        row = parse_payload("new_york_fed", json.dumps(payload).encode(),
            decision_at="2026-11-22T00:00:00+00:00", retrieved_at="2026-11-22T00:00:00+00:00")[0]
        self.assertEqual(row["schema_status"], "LEGACY_SYNTHETIC_ALIAS_NOT_DOCUMENTED")

    def test_notices_bound_to_official_sections_and_hashes(self):
        plan = authorization.load_plan()
        self.assertEqual(len(plan["required_notices"]), 4)
        self.assertTrue(all(len(n["normalized_notice_sha256"]) == 64 for n in plan["required_notices"]))
        self.assertEqual(plan["controls"]["raw_response_persistence"], False)
        self.assertEqual(plan["controls"]["public_numerical_artifacts"], False)


if __name__ == "__main__":
    unittest.main()
