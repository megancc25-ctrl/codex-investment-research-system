"""Validated manual inputs for sources not available in the free automated adapters."""
from __future__ import annotations
import json, math
from datetime import date, datetime, timezone
from pathlib import Path
from .config import RULES

EVENT_KEYS = {"cdx_hy_widening", "repo_extreme", "funding_market_failure", "margin_stress"}

def _utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Manual timestamps must include a timezone")
    return dt.astimezone(timezone.utc)

def load_manual_evidence(path, asof):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("asof") != asof:
        raise ValueError("Manual evidence asof must match the report date")
    cutoff = datetime.fromisoformat(asof + "T23:59:59+00:00")
    features, events = {}, {}
    for key, record in payload.get("features", {}).items():
        if key not in RULES:
            raise ValueError(f"Unsupported CRS feature: {key}")
        value = record.get("value")
        if isinstance(value, bool):
            if key not in ("ndx_below_200dma", "synchronized_three_asset_down_20d", "synchronized_three_asset_loss_5pct"):
                raise ValueError("Boolean value is invalid for this feature")
        elif not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("Feature value must be finite numeric or an allowed boolean")
        observation_date = date.fromisoformat(record["observation_date"])
        if observation_date > date.fromisoformat(asof):
            raise ValueError("Manual feature has a future observation date")
        published, retrieved = _utc(record["published_at"]), _utc(record["retrieved_at"])
        if published > retrieved or retrieved > cutoff:
            raise ValueError("Publication/retrieval timestamp is not available by report cutoff")
        source_url = record.get("source_url", "")
        if not source_url.startswith("https://"):
            raise ValueError("Manual source_url must use HTTPS")
        features[key] = {"value": value, "quality": record.get("quality", "UNKNOWN"),
                         "source": source_url, "observation_date": str(observation_date),
                         "published_at": published.isoformat(), "retrieved_at": retrieved.isoformat(),
                         "license_status": record.get("license_status", "REVIEW_REQUIRED"),
                         "stale": False, "age_days": (date.fromisoformat(asof)-observation_date).days}
    for key, record in payload.get("events", {}).items():
        if key not in EVENT_KEYS:
            raise ValueError(f"Unsupported event flag: {key}")
        if record.get("value") is not True:
            events[key] = False
            continue
        published, retrieved = _utc(record["published_at"]), _utc(record["retrieved_at"])
        if published > retrieved or retrieved > cutoff or not record.get("source_url", "").startswith("https://"):
            raise ValueError("Event evidence needs valid time order and an HTTPS source")
        events[key] = True
    return {"features": features, "events": events,
            "source_status": {"manual_evidence": {"status": "AVAILABLE", "asof": asof,
                             "feature_count": len(features), "event_count": len(events),
                             "note": "Manual evidence is attributable only to its supplied public source."}}}
