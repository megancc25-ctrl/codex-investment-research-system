"""G1 evidence catalog and offline source contracts; no live execution path."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
from xml.etree import ElementTree as ET

MATRIX_PATH = Path(__file__).with_name("source_admission_matrix.json")
USES = ("public_access", "internal_analysis", "automated_collection", "memory_processing",
        "local_persistence", "github_cache", "report_html_json", "redistribution")


def load_matrix():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    evidence_ids = {x["id"] for x in matrix["evidence"]}
    for source in matrix["sources"]:
        if set(source["uses"]) != set(USES):
            raise ValueError("Incomplete purpose matrix")
        for permission in source["uses"].values():
            if permission["status"] not in ("ALLOWED", "RESTRICTED", "UNKNOWN"):
                raise ValueError("Unknown permission state")
            if not permission["evidence_ids"] or not set(permission["evidence_ids"]) <= evidence_ids:
                raise ValueError("Missing evidence reference")
    return matrix


def authorized_action(source_id, purpose, action):
    """Reject before calling network, credential, or persistence callbacks."""
    if purpose not in USES:
        raise ValueError("Unknown purpose")
    source = next((x for x in load_matrix()["sources"] if x["id"] == source_id), None)
    if source is None:
        raise PermissionError("Unknown source is not admitted")
    if source["uses"][purpose]["status"] != "ALLOWED":
        raise PermissionError(f"{source_id}: {purpose} not allowed")
    # This G1 module deliberately has no approved production execution mode.
    # Matrix edits alone cannot silently enable G2 or accept a publisher's terms.
    raise PermissionError(f"{source_id}: G1 offline only; live interface and separate execution approval absent")


def _instant(text):
    result = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return result.astimezone(timezone.utc)


def _number(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not numeric source data")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Non-finite source value")
    return value


def parse_payload(source_id, raw, *, decision_at, retrieved_at):
    """Parse caller-supplied synthetic bytes. Does not fetch, cache or admit data.

    Release schedule, filed date, observation date and retrieval are distinct.
    None can be promoted into first-available evidence by this parser.
    """
    cutoff, fetched = _instant(decision_at), _instant(retrieved_at)
    if not raw:
        raise ValueError("Empty source response")
    raw_hash = hashlib.sha256(raw).hexdigest()
    output = []

    def add(indicator, day, value, unit, **metadata):
        obs = date.fromisoformat(day)
        if obs > cutoff.date():
            raise ValueError("Future observation rejected")
        output.append({"source": source_id, "indicator": indicator, "observation_date": day,
            "value": _number(value), "unit": unit, "retrieved_at": fetched.isoformat(),
            "published_at": None, "first_available_at": None, "pit_status": "NOT_VERIFIED",
            "quality_status": "OFFLINE_SYNTHETIC_CONTRACT", "raw_content_sha256": raw_hash,
            "publication_evidence_sha256": None, **metadata})

    if source_id == "treasury":
        # No external XML entities/DTD are accepted, even in offline payloads.
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("XML entity declarations prohibited")
        root = ET.fromstring(raw)
        for entry in root.iter():
            if entry.tag.rsplit("}", 1)[-1] != "entry":
                continue
            fields = {x.tag.rsplit("}", 1)[-1]: x.text for x in entry.iter()}
            day = str(fields.get("NEW_DATE", ""))[:10]
            for field, indicator in (("BC_10YEAR", "ust10y"), ("BC_30YEAR", "ust30y"), ("TC_10YEAR", "real10y")):
                if fields.get(field) not in (None, ""):
                    add(indicator, day, fields[field], "percent", source_field=field)
    elif source_id == "new_york_fed":
        payload = json.loads(raw)
        if not isinstance(payload.get("refRates"), list):
            raise ValueError("Expected refRates list")
        for row in payload["refRates"]:
            kind = row.get("type")
            if kind not in ("SOFR", "TGCR", "BGCR") or row.get("unit", "percent") != "percent":
                raise ValueError("Unexpected rate type or unit")
            if "percent" in row and "percentRate" in row and _number(row["percent"]) != _number(row["percentRate"]):
                raise ValueError("Conflicting documented and legacy rate fields")
            rate_field = "percent" if "percent" in row else "percentRate"
            add(kind.lower(), row["effectiveDate"], row[rate_field], "percent",
                source_field=rate_field,
                schema_status="DOCUMENTED_FIELD_MAPPING_NOT_LIVE_VERIFIED" if rate_field == "percent" else "LEGACY_SYNTHETIC_ALIAS_NOT_DOCUMENTED",
                revision_indicator=row.get("revisionIndicator"),
                volume=_number(row["volumeInBillions"]) if row.get("volumeInBillions") is not None else None,
                volume_unit="billion USD")
    elif source_id in ("chicago_fed", "cboe"):
        records = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        required = {"Date", "NFCI", "ANFCI"} if source_id == "chicago_fed" else {"DATE", "CLOSE"}
        if not required <= set(records.fieldnames or []):
            raise ValueError("Unexpected CSV columns")
        for row in records:
            if source_id == "chicago_fed":
                for key in ("NFCI", "ANFCI"):
                    add(key.lower(), row["Date"], row[key], "standardized_index")
            else:
                day = datetime.strptime(row["DATE"], "%m/%d/%Y").date().isoformat()
                add("vix", day, row["CLOSE"], "index_points")
    elif source_id == "sec":
        payload = json.loads(raw)
        concepts = payload.get("facts", {}).get("us-gaap", {})
        for concept in ("NetCashProvidedByUsedInOperatingActivities", "PaymentsToAcquirePropertyPlantAndEquipment"):
            units = concepts.get(concept, {}).get("units", {})
            if units and set(units) != {"USD"}:
                raise ValueError("Unmapped accounting currency/unit")
            for row in units.get("USD", []):
                if date.fromisoformat(row["filed"]) > cutoff.date():
                    raise ValueError("Future filing rejected")
                add(concept, row["end"], row["val"], "USD", filed_date=row["filed"],
                    period_start=row.get("start"), accession=row.get("accn"), form=row.get("form"),
                    accounting_scope="REPORTED_PERIOD_NOT_AUTOMATICALLY_QUARTERLY")
    else:
        raise ValueError("No verified offline schema for this candidate")
    if not output:
        raise ValueError("No usable observations")
    identities = set()
    for item in output:
        key = (item["indicator"], item["observation_date"], item.get("period_start"), item.get("accession"))
        if key in identities:
            raise ValueError("Duplicate or conflicting observation")
        identities.add(key)
    return output


def pit_eligible(row, decision_at):
    proof = row.get("publication_evidence_sha256")
    if not isinstance(proof, str) or not re.fullmatch(r"[a-f0-9]{64}", proof) or not row.get("published_at"):
        return False
    # G1 contains documentation evidence only, never historical publication proofs.
    # A future independently audited release corpus must bind proof to source,
    # observation, content version and exact timestamp. Hash shape alone is not PIT.
    proofs = [e for e in load_matrix()["evidence"]
        if e.get("evidence_kind") == "FIRST_AVAILABLE_MARKET_OBSERVATION"
        and e.get("artifact_sha256") == proof and e.get("source_id") == row.get("source")
        and e.get("observation_date") == row.get("observation_date")
        and e.get("raw_content_sha256") == row.get("raw_content_sha256")
        and e.get("published_at") == row.get("published_at")]
    if not proofs:
        return False
    try:
        return (_instant(row["published_at"]) <= _instant(decision_at) and
                date.fromisoformat(row["observation_date"]) <= _instant(decision_at).date())
    except (ValueError, TypeError):
        return False


def offline_probe(transport):
    """Fault-injection harness; never installs a live/default transport."""
    for attempt in range(1, 3):
        try:
            payload = transport()
            if not payload:
                raise ValueError("Empty offline payload")
            return {"status": "OFFLINE_CONTRACT_ONLY", "attempts": attempt, "live_attempted": False}
        except (TimeoutError, ConnectionError):
            if attempt == 2:
                return {"status": "COLLECTION_FAILED", "attempts": attempt, "live_attempted": False}


def release_state(observation_date, report_date, *, next_release_at, decision_at):
    if date.fromisoformat(observation_date) > date.fromisoformat(report_date):
        raise ValueError("Future observation")
    if next_release_at is None:
        return "RELEASE_CALENDAR_UNKNOWN"
    return "EXPECTED_LAG" if _instant(decision_at) < _instant(next_release_at) else "STALE"


def export_audit(directory):
    matrix = load_matrix()
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": "crs-g1-audit-1", "review_date": matrix["review_date"],
        "baseline": matrix["baseline"], "g1_investigation": "COMPLETE_WITH_DOCUMENTED_GAPS",
        "g1_data_admission": "NO_GO", "g2": "NOT_STARTED", "g3": "NOT_STARTED",
        "formal_score": None, "real_data_coverage_pct": None,
        "source_admission_matrix_sha256": hashlib.sha256(json.dumps(matrix, sort_keys=True).encode()).hexdigest(),
        "live_sources_admitted": [], "sources": matrix["sources"], "fred_series": matrix["fred_series"],
        "evidence": matrix["evidence"]}
    json_path = out/"source_admission_matrix.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    lines = ["# G1_DECISION_REPORT", "", "G1: PARTIAL (investigation delivered; live data admission NO_GO).",
        "G2/G3: NOT_STARTED. Formal score: N/A. Real coverage: N/A.", "",
        "ALLOWED describes the published permission within its recorded scope, not project approval or accepted terms.", "",
        "| Source | Access | Analysis | Automation | Memory | Local | GitHub | HTML/JSON | Redistribution | Interface |",
        "|---|---|---|---|---|---|---|---|---|---|"]
    for source in matrix["sources"]:
        lines.append("| "+source["id"]+" | "+" | ".join(source["uses"][purpose]["status"] for purpose in USES)+" | "+source["interface_validation"]+" |")
    for source in matrix["sources"]:
        lines += ["", "## "+source["id"], source["summary"], "", "Evidence: "+", ".join(
            f"[{x['id']}]({x['url']})" for x in matrix["evidence"] if x["id"] in source["evidence_ids"]),
            "", "Gaps: "+"; ".join(source["gaps"])]
    lines += ["", "## Scope, evidence integrity and execution boundary",
        "Ten bounded candidates were investigated; this is not an exhaustive inventory of issuers or national property agencies.",
        "No numerical data feed was fetched. Only official documentation, terms, developer specifications and catalog metadata were read. No credentials, consent forms or paid services were used.",
        "Evidence records distinguish complete origin-response hashes from short web-rendered excerpt hashes. Raw page bodies are not redistributed. Origin request timestamps identify request start; exact response-completion time was not captured.",
        "Published permissions do not change the 19 FRED baseline restrictions. Treasury CC0 is scoped to the named catalog datasets; modern-feed mapping and service automation conditions remain gaps.",
        "Five source-family parser contracts (Treasury, New York Fed, Chicago Fed, Cboe, SEC) use synthetic payloads. Chicago CSV headers remain an unverified candidate schema; remaining five candidates are catalog/investigation only. No parser test is a live interface acceptance.",
        "Expected release time, filed date, observation date and fetched time never become first-available proof. All parser outputs remain NOT_VERIFIED for PIT.",
        "", "## Verification",
        "Baseline: 132 existing tests retained. G1: 23 additional tests. Full suite expected total: 155; actual local/hosted results and commit SHA are reported in the final delivery. CI configuration alone is not evidence of success.",
        "The unchanged seven-module engine/configuration/state machine and CRS 1.1 branch remain frozen. G1 CI is a new separate workflow.",
        "", "## Minimal user decision",
        "| Decision | Narrow option | Safe default |",
        "|---|---|---|",
        "| Authorize the final bounded-test packet and applicable existing terms | New York Fed SOFR/TGCR/BGCR only; at most three fixed-date GET requests with required notices, memory-only, no GitHub cache or public numerical report; not G2 scheduling | Do not perform until explicitly authorized |",
        "", "There is no need to buy data, configure a FRED key, approve 19 series, contact owners, or enable G2/G3 now. Cboe/Chicago permissions and other unresolved sources remain disabled; any later request to owners must be separately authorized.",
        "", "## Unchanged FRED series",
        "RESTRICTED: "+", ".join(x["series_id"] for x in matrix["fred_series"] if x["license_status"] == "RESTRICTED"),
        "REVIEW_REQUIRED: "+", ".join(x["series_id"] for x in matrix["fred_series"] if x["license_status"] == "REVIEW_REQUIRED")]
    markdown_path = out/"G1_DECISION_REPORT.md"
    markdown_path.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return [str(json_path), str(markdown_path)]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export frozen G1 audit; no network or credentials")
    parser.add_argument("--output", default="reports/crs-g1")
    args = parser.parse_args(argv)
    print(json.dumps(export_audit(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
