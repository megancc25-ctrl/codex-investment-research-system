"""DuckDB evidence store. Private portfolio inputs are never accepted here."""
from __future__ import annotations
import json
import re
from pathlib import Path
from datetime import date, datetime

FRED_CACHE_MAX_AGE_DAYS = {
    "reserves": 35, "tga": 35, "case_shiller": 120, "home_sales": 120,
    "cpi": 120, "mortgage30y": 35,
}
FRED_CACHE_DEFAULT_MAX_AGE_DAYS = 14


def connect_fred_cache(path):
    """Open a dedicated cache DB; never mix source cache data with reports/state."""
    import duckdb
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(target))
    con.execute("""CREATE TABLE IF NOT EXISTS crs_fred_cache (
        series_key VARCHAR, observation_date DATE, value DOUBLE, source_id VARCHAR,
        source_url VARCHAR, source_kind VARCHAR, quality VARCHAR,
        license_status VARCHAR, cache_authorization VARCHAR,
        published_at TIMESTAMPTZ, retrieved_at TIMESTAMPTZ, vintage_id VARCHAR,
        raw_sha256 VARCHAR, metadata JSON,
        PRIMARY KEY(series_key, observation_date, source_id, vintage_id))""")
    return con

def connect(path):
    import duckdb
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(target))
    con.execute("""CREATE TABLE IF NOT EXISTS crs_observations (
        metric_id VARCHAR, observation_date DATE, value DOUBLE, unit VARCHAR,
        source_id VARCHAR, source_url VARCHAR, source_kind VARCHAR, quality VARCHAR,
        published_at TIMESTAMPTZ, retrieved_at TIMESTAMPTZ, vintage_id VARCHAR,
        raw_sha256 VARCHAR, frequency VARCHAR, metadata JSON,
        PRIMARY KEY(metric_id, observation_date, source_id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS crs_fred_vintages (
        metric_id VARCHAR, observation_date DATE, value DOUBLE, source_id VARCHAR,
        source_url VARCHAR, vintage_date DATE, retrieved_at TIMESTAMPTZ,
        raw_sha256 VARCHAR, source_kind VARCHAR, quality VARCHAR,
        license_status VARCHAR, published_at TIMESTAMPTZ, metadata JSON,
        PRIMARY KEY(metric_id, observation_date, source_id, vintage_date))""")
    con.execute("""CREATE TABLE IF NOT EXISTS crs_features (
        asof_date DATE, metric_id VARCHAR, value DOUBLE, unit VARCHAR,
        source_id VARCHAR, source_url VARCHAR, quality VARCHAR, age_days INTEGER,
        metadata JSON, PRIMARY KEY(asof_date, metric_id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS crs_reports (
        asof_date DATE PRIMARY KEY, score DOUBLE, state VARCHAR, status VARCHAR,
        generated_at TIMESTAMPTZ, payload JSON)""")
    return con

def save_collected(con, collection):
    for key, source in collection["fred"].items():
        if source.get("source_kind") == "FRED_API_VINTAGE_ASOF" and source.get("vintage_date"):
            for day, value in source["values"].items():
                con.execute("""INSERT OR REPLACE INTO crs_fred_vintages
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    [key, day, float(value), source.get("series_id") or "UNKNOWN",
                     source.get("source") if str(source.get("source", "")).startswith("https://") else None,
                     source["vintage_date"], source.get("retrieved_at"), source.get("raw_sha256"),
                     source["source_kind"], source.get("quality") or "UNKNOWN",
                     source.get("license_status") or "UNKNOWN", source.get("published_at"),
                     json.dumps({"vintage_date": source["vintage_date"],
                                 "published_at": source.get("published_at"),
                                 "license_status": source.get("license_status"),
                                 "raw_sha256": source.get("raw_sha256"),
                                 "realtime_vintage_is_not_intraday_release_time": True})])
        for day, value in source["values"].items():
            con.execute("""INSERT OR REPLACE INTO crs_observations
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [key, day, float(value), "source-native", source.get("series_id") or "UNKNOWN",
                 source.get("source") if str(source.get("source", "")).startswith("https://") else None,
                 source["source_kind"], source["quality"], source.get("published_at"), source["retrieved_at"],
                 "CURRENT_VINTAGE", source["raw_sha256"], "source-defined",
                 json.dumps({"source": source.get("source") or "UNKNOWN",
                             "series_id": source.get("series_id"),
                             "published_at": source.get("published_at"),
                             "retrieved_at": source.get("retrieved_at"),
                             "raw_sha256": source.get("raw_sha256"),
                             "license_status": source.get("license_status"),
                             "source_kind": source.get("source_kind"),
                             "quality": source.get("quality"),
                             "license_note": source.get("license_note"), "unit_note": source.get("unit_note")})])
    for symbol, series in collection["prices"].items():
        price_meta = collection.get("price_status", {}).get(symbol, {})
        for day, value in series.items():
            con.execute("""INSERT OR REPLACE INTO crs_observations
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [f"price:{symbol}", day, float(value), "adjusted_close_proxy", price_meta.get("source_id") or "UNKNOWN",
                 price_meta.get("source_url") or None, "YAHOO_YFINANCE", "UNVERIFIED_VENDOR_PROXY",
                 price_meta.get("published_at"), price_meta.get("retrieved_at"), "VENDOR_HISTORY",
                 price_meta.get("raw_sha256"), "daily",
                 json.dumps({"proxy": True, **price_meta})])
    for metric, record in collection["features"].items():
        if not isinstance(record, dict) or record.get("value") is None:
            continue
        con.execute("""INSERT OR REPLACE INTO crs_features
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [collection["asof"], metric, float(record["value"]), "feature-native",
             record.get("source_id") or "UNKNOWN", record.get("source_url") or None,
             record.get("quality") or "UNKNOWN", int(record.get("age_days") or 0),
            json.dumps({"observation_date": record.get("observation_date"),
                        "source": record.get("source") or "UNKNOWN",
                        "source_id": record.get("source_id") or "UNKNOWN",
                        "ticker": record.get("ticker") or "UNKNOWN",
                        "raw_sha256": record.get("raw_sha256"),
                        "published_at": record.get("published_at"),
                        "retrieved_at": record.get("retrieved_at"),
                        "license_status": record.get("license_status") or "REVIEW_REQUIRED",
                        "stale": record.get("stale", False)})])

def latest_reports(con, limit=10):
    rows = con.execute("SELECT payload FROM crs_reports ORDER BY asof_date DESC LIMIT ?", [limit]).fetchall()
    return [json.loads(row[0]) for row in reversed(rows)]


def save_fred_cache(con, collection):
    """Persist only explicitly license-approved, attributable, hashed live series."""
    import math
    from .fred import SERIES
    summary = {"saved_series_count": 0, "ineligible_series_count": 0}
    status = collection.get("source_status", {})
    asof = date.fromisoformat(collection["asof"])
    for key, source in collection.get("fred", {}).items():
        if status.get(f"fred:{key}", {}).get("fetch_status", "SUCCESS") != "SUCCESS":
            continue
        source_id = source.get("series_id")
        source_url = source.get("source")
        raw_hash = source.get("raw_sha256")
        retrieved_at = source.get("retrieved_at")
        allowed = (
            key in SERIES and source_id == SERIES[key] and
            source.get("source_kind") in ("FRED_API_VINTAGE_ASOF", "FRED_CURRENT_VINTAGE_CSV") and
            source.get("license_status") == "APPROVED_FOR_INTERNAL_CACHE" and
            source.get("cache_authorization") == "APPROVED_FOR_INTERNAL_CACHE" and
            source.get("quality") != "LICENSE_RESTRICTED" and
            source_url == f"https://fred.stlouisfed.org/series/{source_id}" and
            isinstance(raw_hash, str) and re.fullmatch(r"[0-9a-fA-F]{64}", raw_hash) is not None and
            isinstance(retrieved_at, str)
        )
        try:
            retrieved_day = date.fromisoformat(retrieved_at[:10]) if retrieved_at else None
        except ValueError:
            retrieved_day = None
        if not allowed or retrieved_day is None or retrieved_day > asof:
            summary["ineligible_series_count"] += 1
            continue
        values = source.get("values", {})
        if not values or any(day > collection["asof"] or not math.isfinite(float(value))
                             for day, value in values.items()):
            summary["ineligible_series_count"] += 1
            continue
        obs_day = source.get("observation_date") or max(values)
        try:
            date.fromisoformat(obs_day)
            datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
        except ValueError:
            summary["ineligible_series_count"] += 1
            continue
        if obs_day != max(values):
            summary["ineligible_series_count"] += 1
            continue
        vintage_id = source.get("vintage_date") or "CURRENT"
        con.execute("DELETE FROM crs_fred_cache WHERE series_key = ?", [key])
        for day, value in values.items():
            con.execute("""INSERT OR REPLACE INTO crs_fred_cache
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [key, day, float(value), source_id, source_url, source.get("source_kind"),
                 source.get("quality"), source.get("license_status"), source.get("cache_authorization"),
                 source.get("published_at"), retrieved_at, vintage_id, raw_hash,
                 json.dumps({"observation_date": obs_day, "retrieved_at": retrieved_at,
                             "raw_sha256": raw_hash, "license_status": source.get("license_status"),
                             "cache_authorization": source.get("cache_authorization")})])
        summary["saved_series_count"] += 1
    return summary


def load_fred_cache(con, asof):
    """Return approved fresh cache plus counts; invalid or expired rows fail closed."""
    asof_date = date.fromisoformat(asof)
    rows = con.execute("""SELECT series_key, observation_date, value, source_id, source_url,
        source_kind, quality, license_status, cache_authorization, published_at,
        retrieved_at, vintage_id, raw_sha256, metadata FROM crs_fred_cache
        ORDER BY series_key, retrieved_at DESC, observation_date""").fetchall()
    from .fred import SERIES
    grouped = {}
    for row in rows:
        key, day, value, source_id, source_url, source_kind, quality, license_status, cache_auth, published, retrieved, vintage_id, raw_hash, metadata = row
        retrieved_text = retrieved.isoformat() if hasattr(retrieved, "isoformat") else str(retrieved)
        published_text = published.isoformat() if hasattr(published, "isoformat") else published
        item = grouped.setdefault(key, {"rows": [], "latest_retrieved_at": retrieved,
            "series_id": source_id, "source": source_url, "source_kind": source_kind,
            "quality": quality, "license_status": license_status,
            "cache_authorization": cache_auth, "published_at": published_text,
            "retrieved_at": retrieved_text, "raw_sha256": raw_hash, "vintage_date": vintage_id})
        item["rows"].append((day, float(value), source_id, source_url, source_kind, quality,
                             license_status, cache_auth, retrieved, raw_hash))
    fresh, expired, ineligible = {}, 0, 0
    for key, item in grouped.items():
        if key not in SERIES or not item["rows"]:
            ineligible += 1
            continue
        latest_batch = max(row[8] for row in item["rows"])
        selected = [row for row in item["rows"] if row[8] == latest_batch]
        source_id = item["series_id"]
        source_url = item["source"]
        raw_hash = item["raw_sha256"]
        retrieved_at = str(item["retrieved_at"])
        try:
            retrieved_day = date.fromisoformat(retrieved_at[:10])
        except ValueError:
            retrieved_day = None
        valid = (source_id == SERIES[key] and
                 source_url == f"https://fred.stlouisfed.org/series/{source_id}" and
                 item["license_status"] == "APPROVED_FOR_INTERNAL_CACHE" and
                 item["cache_authorization"] == "APPROVED_FOR_INTERNAL_CACHE" and
                 item["source_kind"] in ("FRED_API_VINTAGE_ASOF", "FRED_CURRENT_VINTAGE_CSV") and
                 item["quality"] != "LICENSE_RESTRICTED" and
                 re.fullmatch(r"[0-9a-fA-F]{64}", str(raw_hash or "")) is not None and
                 retrieved_day is not None and retrieved_day <= asof_date and
                 all(row[2] == source_id and row[3] == source_url and row[6] == item["license_status"]
                     and row[4] == item["source_kind"] and row[5] == item["quality"]
                     and row[7] == item["cache_authorization"] and row[9] == raw_hash for row in selected))
        if not valid:
            ineligible += 1
            continue
        values = {row[0].isoformat(): row[1] for row in selected if row[0] <= asof_date}
        if not values:
            ineligible += 1
            continue
        latest_day = max(values)
        age = (asof_date - date.fromisoformat(latest_day)).days
        if age > FRED_CACHE_MAX_AGE_DAYS.get(key, 14):
            expired += 1
            continue
        item.update({"series_key": key, "values": values, "observation_date": latest_day, "cached": True,
                     "cache_age_days": age, "cache_max_age_days": FRED_CACHE_MAX_AGE_DAYS.get(key, 14),
                     "cache_retrieved_at": item.get("retrieved_at")})
        fresh[key] = item
    return fresh, {"stored_series_count": len(grouped), "fresh_series_count": len(fresh),
                   "expired_series_count": expired, "ineligible_series_count": ineligible}

def save_report(con, report):
    state = report.get("state_machine", {}).get("state", "INSUFFICIENT_DATA")
    score = report.get("score_result", {}).get("score")
    score_status = report.get("score_result", {}).get("status", "UNKNOWN")
    con.execute("""INSERT OR REPLACE INTO crs_reports VALUES (?, ?, ?, ?, ?, ?)""",
                [report["asof"], score, state, score_status, report["generated_at"],
                 json.dumps(report, ensure_ascii=False)])

def export_parquet(con, directory):
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    for table in ("crs_observations", "crs_features", "crs_reports"):
        path = (target / f"{table}.parquet").resolve().as_posix().replace("'", "''")
        con.execute(f"COPY (SELECT * FROM {table}) TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
