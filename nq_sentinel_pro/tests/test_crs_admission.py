"""G1 offline contracts. All numerical payloads below are synthetic."""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from sentinel.crs import admission

NOW = "2026-11-20T22:00:00+00:00"


class AdmissionTests(unittest.TestCase):
    def test_catalog_has_complete_source_and_purpose_evidence(self):
        matrix = admission.load_matrix()
        self.assertEqual(len(matrix["sources"]), 10)
        self.assertEqual(len(matrix["fred_series"]), 19)
        for row in matrix["sources"]:
            self.assertEqual(set(row["uses"]), set(admission.USES))
            self.assertFalse(row["live_enabled"])
            self.assertEqual(row["interface_validation"], "OFFLINE_ONLY_NOT_ADMITTED")
            for item in row["uses"].values():
                self.assertIn(item["status"], ("ALLOWED", "RESTRICTED", "UNKNOWN"))
                self.assertTrue(item["evidence_ids"])
        for evidence in matrix["evidence"]:
            self.assertEqual(hashlib.sha256(evidence["excerpt"].encode()).hexdigest(), evidence["excerpt_sha256"])
            self.assertLessEqual(len(evidence["excerpt"].split()), 25)

    def test_all_live_actions_fail_before_transport_credentials_or_writer(self):
        action = Mock(side_effect=AssertionError("side effect"))
        for row in admission.load_matrix()["sources"]:
            for use in admission.USES:
                with self.assertRaises(PermissionError):
                    admission.authorized_action(row["id"], use, action)
        action.assert_not_called()

    def test_treasury_xml_has_three_separate_fields_and_no_invented_release(self):
        raw = b'<feed xmlns:d="urn:d"><entry><d:NEW_DATE>2026-11-20T00:00:00</d:NEW_DATE><d:BC_10YEAR>3.1</d:BC_10YEAR><d:BC_30YEAR>3.2</d:BC_30YEAR></entry></feed>'
        rows = admission.parse_payload("treasury", raw, decision_at=NOW, retrieved_at=NOW)
        self.assertEqual([r["indicator"] for r in rows], ["ust10y", "ust30y"])
        self.assertTrue(all(r["unit"] == "percent" and r["published_at"] is None for r in rows))
        real = admission.parse_payload("treasury", raw.replace(b'BC_10YEAR', b'TC_10YEAR'), decision_at=NOW, retrieved_at=NOW)
        self.assertIn("real10y", [r["indicator"] for r in real])

    def test_ny_rates_revision_and_volume_retained_without_derived_substitution(self):
        raw = json.dumps({"refRates": [{"effectiveDate": "2026-11-19", "type": "SOFR", "percentRate": 3.2,
            "volumeInBillions": 100, "revisionIndicator": "*"}]}).encode()
        row = admission.parse_payload("new_york_fed", raw, decision_at=NOW, retrieved_at=NOW)[0]
        self.assertEqual(row["indicator"], "sofr")
        self.assertEqual(row["revision_indicator"], "*")
        self.assertEqual(row["volume_unit"], "billion USD")
        self.assertIsNone(row["published_at"])

    def test_chicago_weekly_pair_allows_negative_values(self):
        rows = admission.parse_payload("chicago_fed", b'Date,NFCI,ANFCI\n2026-11-13,-0.2,-0.3\n', decision_at=NOW, retrieved_at=NOW)
        self.assertEqual([r["indicator"] for r in rows], ["nfci", "anfci"])
        self.assertEqual(rows[0]["value"], -0.2)

    def test_vix_close_is_not_open(self):
        rows = admission.parse_payload("cboe", b'DATE,OPEN,HIGH,LOW,CLOSE\n11/19/2026,11,13,10,12\n', decision_at=NOW, retrieved_at=NOW)
        self.assertEqual(rows[0]["value"], 12)
        self.assertEqual(rows[0]["observation_date"], "2026-11-19")

    def test_sec_filing_day_is_not_first_available_timestamp(self):
        raw = json.dumps({"facts": {"us-gaap": {"NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [{
            "start": "2026-01-01", "end": "2026-09-30", "filed": "2026-11-01", "val": 100,
            "form": "10-Q", "accn": "synthetic-1"}]}}}}}).encode()
        rows = admission.parse_payload("sec", raw, decision_at=NOW, retrieved_at=NOW)
        self.assertEqual(rows[0]["filed_date"], "2026-11-01")
        self.assertEqual(rows[0]["period_start"], "2026-01-01")
        self.assertIsNone(rows[0]["published_at"])
        self.assertEqual(rows[0]["pit_status"], "NOT_VERIFIED")

    def test_future_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "Future"):
            admission.parse_payload("cboe", b'DATE,CLOSE\n11/21/2026,12\n', decision_at=NOW, retrieved_at=NOW)

    def test_duplicate_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            admission.parse_payload("cboe", b'DATE,CLOSE\n11/19/2026,12\n11/19/2026,13\n', decision_at=NOW, retrieved_at=NOW)

    def test_empty_missing_and_nonfinite_fail_closed(self):
        for raw in (b'', b'DATE,CLOSE\n11/19/2026,NaN\n', b'DATE,WRONG\n11/19/2026,12\n'):
            with self.assertRaises(ValueError):
                admission.parse_payload("cboe", raw, decision_at=NOW, retrieved_at=NOW)

    def test_wrong_rate_unit_and_unknown_rate_type_rejected(self):
        for row in ({"effectiveDate": "2026-11-19", "type": "SOFR", "percentRate": "320bp"},
                    {"effectiveDate": "2026-11-19", "type": "OTHER", "percentRate": 3.2}):
            with self.assertRaises(ValueError):
                admission.parse_payload("new_york_fed", json.dumps({"refRates": [row]}).encode(), decision_at=NOW, retrieved_at=NOW)

    def test_publication_evidence_is_required_for_strict_pit(self):
        raw = b'DATE,CLOSE\n11/19/2026,12\n'
        row = admission.parse_payload("cboe", raw, decision_at=NOW, retrieved_at=NOW)[0]
        self.assertFalse(admission.pit_eligible(row, NOW))
        row.update(published_at="2026-11-20T23:00:00+00:00", publication_evidence_sha256="a"*64)
        self.assertFalse(admission.pit_eligible(row, NOW))
        row["published_at"] = "2026-11-20T20:00:00+00:00"
        # A hash-shaped string is not independent release evidence.
        self.assertFalse(admission.pit_eligible(row, NOW))

    def test_timeout_and_disconnect_are_bounded_offline(self):
        for failure in (TimeoutError("timeout"), ConnectionError("disconnected")):
            transport = Mock(side_effect=failure)
            result = admission.offline_probe(transport)
            self.assertEqual(transport.call_count, 2)
            self.assertEqual(result["status"], "COLLECTION_FAILED")
            self.assertFalse(result["live_attempted"])

    def test_probe_success_is_not_live_admission(self):
        result = admission.offline_probe(lambda: b'synthetic')
        self.assertEqual(result["status"], "OFFLINE_CONTRACT_ONLY")
        self.assertEqual(result["attempts"], 1)

    def test_expected_lag_uses_explicit_calendar_not_weekend_inference(self):
        self.assertEqual(admission.release_state("2026-11-19", "2026-11-20", next_release_at="2026-11-23T13:00:00+00:00", decision_at=NOW), "EXPECTED_LAG")
        self.assertEqual(admission.release_state("2026-11-01", "2026-11-20", next_release_at="2026-11-19T13:00:00+00:00", decision_at=NOW), "STALE")
        self.assertEqual(admission.release_state("2026-11-19", "2026-11-20", next_release_at=None, decision_at=NOW), "RELEASE_CALENDAR_UNKNOWN")

    def test_audit_outputs_reproducible_and_stages_separate(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, right = admission.export_audit(a), admission.export_audit(b)
            for x, y in zip(left, right):
                self.assertEqual(Path(x).read_bytes(), Path(y).read_bytes())
            payload = json.loads(Path(left[0]).read_text())
            self.assertEqual(payload["g1_data_admission"], "NO_GO")
            self.assertEqual(payload["g2"], "NOT_STARTED")
            self.assertIsNone(payload["formal_score"])

    def test_unknown_source_and_unknown_use_cannot_execute(self):
        action = Mock()
        with self.assertRaises(PermissionError):
            admission.authorized_action("invented", "public_access", action)
        with self.assertRaises(ValueError):
            admission.authorized_action("treasury", "invented", action)
        action.assert_not_called()

    def test_explicit_wrong_unit_rejected(self):
        row = {"effectiveDate": "2026-11-19", "type": "SOFR", "percentRate": 320, "unit": "basis_points"}
        with self.assertRaises(ValueError):
            admission.parse_payload("new_york_fed", json.dumps({"refRates": [row]}).encode(), decision_at=NOW, retrieved_at=NOW)

    def test_tgcr_bgcr_and_negative_rates_supported(self):
        payload = {"refRates": [{"type": kind, "effectiveDate": "2026-11-19", "percentRate": -0.1} for kind in ("TGCR", "BGCR")]}
        rows = admission.parse_payload("new_york_fed", json.dumps(payload).encode(), decision_at=NOW, retrieved_at=NOW)
        self.assertEqual([r["indicator"] for r in rows], ["tgcr", "bgcr"])

    def test_xml_entities_fail_before_expansion(self):
        with self.assertRaises(ValueError):
            admission.parse_payload("treasury", b'<!DOCTYPE x [<!ENTITY test "bad">]><feed/>', decision_at=NOW, retrieved_at=NOW)

    def test_unverified_schema_is_not_fabricated(self):
        with self.assertRaises(ValueError):
            admission.parse_payload("bis", b'time,value\n2026-Q3,100', decision_at=NOW, retrieved_at=NOW)

    def test_naive_timestamp_and_wrong_currency_rejected(self):
        with self.assertRaises(ValueError):
            admission.parse_payload("cboe", b'DATE,CLOSE\n11/19/2026,12\n', decision_at=NOW, retrieved_at="2026-11-20T22:00:00")
        raw = b'{"facts":{"us-gaap":{"PaymentsToAcquirePropertyPlantAndEquipment":{"units":{"EUR":[]}}}}}'
        with self.assertRaises(ValueError):
            admission.parse_payload("sec", raw, decision_at=NOW, retrieved_at=NOW)

    def test_no_admission_is_not_relabelled_by_synthetic_probe(self):
        matrix = admission.load_matrix()
        self.assertTrue(all(not x["next_stage_eligible"] for x in matrix["sources"]))
        self.assertEqual(sum(x["license_status"] == "RESTRICTED" for x in matrix["fred_series"]), 3)
        self.assertEqual(sum(x["license_status"] == "REVIEW_REQUIRED" for x in matrix["fred_series"]), 16)


if __name__ == "__main__":
    unittest.main()
