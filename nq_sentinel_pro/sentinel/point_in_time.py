"""Point-in-time evidence contract and audit. Never infer publication time from observation date."""
from datetime import datetime, timezone, date
import hashlib
import json
import math

def iso_utc(value):
    if not value or not isinstance(value, str):
        raise ValueError("UTC timestamp required")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt.astimezone(timezone.utc)

def validate_record(record, decision_at, mode="live"):
    if mode not in ("live", "historical"):
        raise ValueError("mode must be live or historical")
    """Return structured rejection, never treat historical observation as public availability."""
    required = ("indicator", "value", "unit", "observation_date",
                "published_at", "retrieved_at", "source_url", "source_kind")
    missing = [k for k in required if k not in record or record[k] is None]
    if missing:
        return {"usable": False, "reason": "MISSING_FIELDS", "fields": missing}
    try:
        if isinstance(record["value"], bool) or not isinstance(record["value"], (int, float)) or not math.isfinite(record["value"]):
            raise ValueError("Nonfinite numeric value")
        date.fromisoformat(record["observation_date"])
        published = iso_utc(record["published_at"])
        retrieved = iso_utc(record["retrieved_at"])
        cutoff = iso_utc(decision_at)
        if published > retrieved:
            return {"usable": False, "reason": "PUBLICATION_AFTER_RETRIEVAL"}
        if published > cutoff:
            return {"usable": False, "reason": "LOOKAHEAD"}
        if retrieved > cutoff and mode == "live":
            return {"usable": False, "reason": "NOT_OBSERVED_BY_DECISION"}
        if mode == "historical" and not record.get("historical_release_verified", False):
            return {"usable": False, "reason": "UNVERIFIED_HISTORICAL_RELEASE"}
        if not record["source_url"].startswith("https://"):
            return {"usable": False, "reason": "INVALID_SOURCE"}
    except (ValueError, TypeError, KeyError) as exc:
        return {"usable": False, "reason": "INVALID", "detail": str(exc)}
    return {"usable": True, "reason": "OK"}

def audit(records, decision_at, mode="live"):
    items = []
    for record in records:
        check = validate_record(record, decision_at, mode=mode)
        items.append({"indicator": record.get("indicator"), **check})
    return {"decision_at": decision_at, "total": len(items),
            "usable": sum(i["usable"] for i in items), "checks": items}

def sha256_payload(payload):
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()
