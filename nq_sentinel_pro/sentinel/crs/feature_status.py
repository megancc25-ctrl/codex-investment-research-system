"""Shared fail-closed interpretation of feature status/value pairs."""
from __future__ import annotations


VALID_STATES = {"AVAILABLE", "MISSING", "INSUFFICIENT_DATA"}


def read_feature(features, key, expected_type=None):
    """Return (state, value); never expose a value when its state is unusable."""
    if not isinstance(features, dict) or key not in features:
        return "MISSING", None
    item = features[key]
    if isinstance(item, dict):
        value = item.get("value")
        raw_state = item.get("status")
        if item.get("stale") is True:
            return "INSUFFICIENT_DATA", None
        state = str(raw_state).upper() if raw_state is not None else (
            "AVAILABLE" if value is not None and item.get("stale") is not True else
            "INSUFFICIENT_DATA" if item.get("stale") is True else "MISSING")
    else:
        value = item
        state = "AVAILABLE" if value is not None else "MISSING"
    if state not in VALID_STATES:
        return "UNKNOWN", None
    if state == "AVAILABLE":
        if value is None or (expected_type is not None and type(value) is not expected_type):
            return "UNKNOWN", None
        return "AVAILABLE", value
    return state, None

