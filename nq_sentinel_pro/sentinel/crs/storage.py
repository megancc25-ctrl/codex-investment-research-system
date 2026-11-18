"""DuckDB evidence store. Private portfolio inputs are never accepted here."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import date

FRED_CACHE_MAX_AGE_DAYS = {
    "reserves": 35, "tga": 35, "case_shiller": 120, "home_sales": 120,
    "cpi": 120, "mortgage30y": 35,
}

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


def load_fred_cache(con, asof):
    """Return only fresh cached FRED series; cached data remain explicitly labeled."""
    asof_date = date.fromisoformat(asof)
    rows = con.execute("""SELECT metric_id, observation_date, value, source_id, source_url,
        source_kind, quality, published_at, retrieved_at, raw_sha256, metadata
        FROM crs_observations WHERE source_kind LIKE 'FRED_%' AND observation_date <= ?
        ORDER BY metric_id, observation_date""", [asof_date]).fetchall()
    grouped = {}
    for row in rows:
        key, day, value, source_id, source_url, source_kind, quality, published, retrieved, raw_hash, metadata = row
        item = grouped.setdefault(key, {"values": {}, "series_id": source_id, "source": source_url,
            "source_kind": source_kind, "quality": quality, "published_at": published,
            "retrieved_at": retrieved, "raw_sha256": raw_hash, "license_status": "UNKNOWN"})
        item["values"][day.isoformat()] = float(value)
        if metadata:
            meta = json.loads(metadata) if isinstance(metadata, str) else metadata
            item["license_status"] = meta.get("license_status") or item["license_status"]
            item["source"] = meta.get("source") or item["source"]
            item["retrieved_at"] = meta.get("retrieved_at") or item["retrieved_at"]
            item["published_at"] = meta.get("published_at")
            item["raw_sha256"] = meta.get("raw_sha256") or item["raw_sha256"]
    fresh = {}
    for key, item in grouped.items():
        latest_day = max(item["values"])
        age = (asof_date - date.fromisoformat(latest_day)).days
        if age > FRED_CACHE_MAX_AGE_DAYS.get(key, 14):
            continue
        item.update({"series_key": key, "observation_date": latest_day, "cached": True,
                     "cache_age_days": age, "cache_max_age_days": FRED_CACHE_MAX_AGE_DAYS.get(key, 14),
                     "cache_retrieved_at": item.get("retrieved_at")})
        fresh[key] = item
    return fresh

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
