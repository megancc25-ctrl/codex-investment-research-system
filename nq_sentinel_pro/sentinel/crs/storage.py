"""DuckDB evidence store. Private portfolio inputs are never accepted here."""
from __future__ import annotations
import json
from pathlib import Path

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
        for day, value in source["values"].items():
            con.execute("""INSERT OR REPLACE INTO crs_observations
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [key, day, float(value), "source-native", source.get("series_id") or "UNKNOWN",
                 source.get("source") if str(source.get("source", "")).startswith("https://") else None,
                 source["source_kind"], source["quality"], source.get("published_at"), source["retrieved_at"],
                 "CURRENT_VINTAGE", source["raw_sha256"], "source-defined",
                 json.dumps({"source": source.get("source") or "UNKNOWN",
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
