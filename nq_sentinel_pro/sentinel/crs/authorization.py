"""Pure offline checks for a proposed test; contains no HTTP execution client."""
from datetime import date, datetime
import json
from pathlib import Path

PLAN_PATH = Path(__file__).with_name("nyfed_bounded_test_plan.json")
SAFE_FIELDS = {"rate_type", "http_status", "record_count", "observation_date", "started_at",
    "completed_at", "elapsed_ms", "bytes_received", "schema_validation", "unit_validation", "error_code"}
ERROR_CODES = {"NONE", "TIMEOUT", "TLS_FAILURE", "HTTP_FAILURE", "REDIRECT_BLOCKED",
    "RESPONSE_TOO_LARGE", "SCHEMA_MISMATCH", "UNIT_MISMATCH", "DATE_MISMATCH",
    "TERMS_CHANGED", "AUTHORIZATION_ABSENT", "UNEXPECTED_RATE_TYPE", "EMPTY_RESPONSE", "NETWORK_FAILURE"}


def validate_plan(plan):
    if plan["approved"] is not False or plan["maximum_market_data_requests"] != 3:
        raise ValueError("This is a proposal, not permission to execute")
    expected = [f"https://markets.newyorkfed.org/api/rates/secured/{kind}/search.json?startDate=2026-11-19&endDate=2026-11-19&type=rate"
        for kind in ("sofr", "tgcr", "bgcr")]
    if [r["url"] for r in plan["requests"]] != expected or any(r["method"] != "GET" for r in plan["requests"]):
        raise ValueError("Request scope drift")
    if set(plan["retained_diagnostic_fields"]) != SAFE_FIELDS:
        raise ValueError("Diagnostic scope drift")
    controls = plan["controls"]
    limits = {"maximum_concurrency": 1, "minimum_seconds_between_requests": 2,
        "connect_timeout_seconds": 5, "read_timeout_seconds": 10,
        "batch_wall_clock_limit_seconds": 45, "maximum_body_bytes_per_request": 262144,
        "maximum_records_per_request": 1}
    if any(controls[k] != v for k, v in limits.items()):
        raise ValueError("Request limit drift")
    if controls["retries"] != 0 or any(controls[k] for k in ("redirects", "raw_response_persistence",
            "github_cache", "public_numerical_artifacts", "credentials", "scheduled_runs")):
        raise ValueError("Control boundary drift")
    return plan


def load_plan():
    return validate_plan(json.loads(PLAN_PATH.read_text(encoding="utf-8")))


def safe_diagnostic(fields):
    """Only typed request metadata may be retained; never exception/server text."""
    if set(fields) - SAFE_FIELDS:
        raise ValueError("Forbidden diagnostic fields")
    for key, value in fields.items():
        if key == "rate_type":
            valid = value in ("sofr", "tgcr", "bgcr")
        elif key == "http_status":
            valid = type(value) is int and 100 <= value <= 599
        elif key in ("record_count", "elapsed_ms", "bytes_received"):
            limit = {"record_count": 1, "elapsed_ms": 45000, "bytes_received": 262144}[key]
            valid = type(value) is int and 0 <= value <= limit
        elif key == "observation_date":
            try:
                valid = date.fromisoformat(value).isoformat() == value
            except (ValueError, TypeError):
                valid = False
        elif key in ("started_at", "completed_at"):
            try:
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
                valid = stamp.tzinfo is not None and stamp.utcoffset() is not None
            except (ValueError, TypeError, AttributeError):
                valid = False
        elif key == "error_code":
            valid = isinstance(value, str) and value in ERROR_CODES
        else:
            valid = value in ("PASS", "FAIL", "NOT_RUN")
        if not valid:
            raise ValueError("Invalid diagnostic value")
    return dict(fields)
