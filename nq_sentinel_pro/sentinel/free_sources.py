"""Six free-source adapters. A failed or inaccessible feed is MISSING, never invented.

External endpoints are source-specific and can change. Never scrape licensed quotes.
Adapters return raw public evidence and source diagnostics, not trade signals.
"""
import csv
import io
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from .point_in_time import sha256_payload

SEC_CIK = {
    "MSFT": "0000789019", "GOOGL": "0001652044",
    "AMZN": "0001018724", "META": "0001326801",
    "NVDA": "0001045810", "AMD": "0000002488",
    "AVGO": "0001730168", "MU": "0000723125",
    "AMAT": "0000006951", "LRCX": "0000707549",
}
CBOE_VIX = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
FINRA_MARGIN = "https://www.finra.org/rules-guidance/key-topics/margin-accounts/margin-statistics"
TSMC_IR = "https://investor.tsmc.com/english/monthly-revenue"
NASDAQ_INDEX = "https://indexes.nasdaq.com/"
UA = "NQ-Sentinel-Pro-FreeResearch/2.0 research@example.org"

def request_bytes(url, opener=None, user_agent=UA):
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    opener = opener or (lambda req: urllib.request.urlopen(req, timeout=18))
    req = urllib.request.Request(url, headers={"User-Agent": user_agent,
                                                "Accept": "application/json,text/csv,text/html,*/*"})
    with opener(req) as response:
        body = response.read(8_000_001)
        if len(body) > 8_000_000:
            raise ValueError("Response too large")
        return body

def missing(source, reason, kind):
    return {"status": "MISSING", "source_url": source, "source_kind": kind,
            "reason": str(reason)[:250]}

def sec_companyfacts(symbol, opener=None, user_agent=UA):
    if symbol not in SEC_CIK:
        raise ValueError("Unknown CIK mapping")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SEC_CIK[symbol]}.json"
    try:
        raw = json.loads(request_bytes(url, opener, user_agent))
        if not isinstance(raw.get("facts"), dict) or not raw.get("cik"):
            raise ValueError("Invalid SEC companyfacts schema")
        return {"status": "RAW_AVAILABLE", "symbol": symbol, "source_url": url,
                "source_kind": "SEC_XBRL", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "sha256": sha256_payload(raw), "facts": raw["facts"]}
    except Exception as exc:
        return missing(url, exc, "SEC_XBRL")

def sec_gaap_facts(raw, tag, asof):
    """Filter by SEC 'filed' date; conservative availability is next UTC day.
    Does not assert exact EDGAR acceptance timestamp.
    """
    if raw.get("status") != "RAW_AVAILABLE":
        return []
    entries = raw["facts"].get("us-gaap", {}).get(tag, {}).get("units", {})
    out = []
    for unit, facts in entries.items():
        for f in facts:
            if not isinstance(f, dict) or "filed" not in f or "val" not in f:
                continue
            if f["filed"] >= asof:  # conservative: usable no earlier than following UTC day
                continue
            if f.get("form") not in ("10-K", "10-Q"):
                continue
            out.append({"tag": tag, "value": f["val"], "unit": unit,
                        "period_end": f.get("end"), "period_start": f.get("start"),
                        "filed": f["filed"], "accession": f.get("accn"),
                        "form": f.get("form"), "source_url": raw["source_url"],
                        "quality": "RELEASE_DATE_ONLY"})
    return out

def cboe_vix(asof, opener=None):
    try:
        body = request_bytes(CBOE_VIX, opener)
        reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
        if not reader.fieldnames or not {"DATE", "CLOSE"}.issubset(set(reader.fieldnames)):
            raise ValueError("Unexpected Cboe VIX schema")
        rows = []
        for row in reader:
            try:
                raw_date = row["DATE"].strip()
                d = datetime.strptime(raw_date, "%m/%d/%Y").date().isoformat()
                value = float(row["CLOSE"])
                if d <= asof and 0 < value < 200:
                    rows.append({"date": d, "vix": value})
            except (ValueError, KeyError, TypeError):
                continue
        if not rows:
            raise ValueError("No valid VIX observations")
        latest = max(rows, key=lambda x:x["date"])
        return {"status": "RAW_AVAILABLE", "source_kind": "CBOE_VIX_DAILY",
                "source_url": CBOE_VIX, "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "latest": latest, "count": len(rows),
                "quality": "OBSERVATION_DATE_ONLY_NOT_PIT"}
    except Exception as exc:
        return missing(CBOE_VIX, exc, "CBOE_VIX_DAILY")

def finra_margin(asof, csv_path=None):
    """Only parse an explicitly supplied FINRA-exported CSV.
    No guessing website HTML table layout or monthly release timestamp.
    """
    if not csv_path:
        return missing(FINRA_MARGIN, "Official FINRA monthly export not configured; release timestamps unavailable", "FINRA_MARGIN")
    try:
        path = Path(csv_path)
        if path.suffix.lower() != ".csv":
            raise ValueError("CSV only")
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("Empty FINRA export")
        return {"status": "RAW_AVAILABLE", "source_kind": "FINRA_MARGIN",
                "source_url": FINRA_MARGIN, "rows": rows,
                "quality": "MANUAL_EXPORT_RELEASE_TIME_UNVERIFIED",
                "retrieved_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        return missing(FINRA_MARGIN, exc, "FINRA_MARGIN")

def constituents(asof, path=None):
    """Only accept dated official index snapshots; never claim historical membership."""
    if not path:
        return missing(NASDAQ_INDEX, "Official constituent snapshot not configured", "INDEX_MEMBERSHIP")
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not {"index", "effective_date", "symbols", "source_url"}.issubset(data):
            raise ValueError("Invalid constituent snapshot")
        if data["index"] not in ("NDX", "SOX") or data["effective_date"] > asof:
            raise ValueError("Wrong index or future membership")
        if not isinstance(data["symbols"], list) or len(set(data["symbols"])) != len(data["symbols"]):
            raise ValueError("Invalid membership list")
        if not data["source_url"].startswith("https://"):
            raise ValueError("Source URL required")
        return {"status": "RAW_AVAILABLE", "source_kind": "INDEX_MEMBERSHIP",
                "source_url": data["source_url"], "snapshot": data,
                "quality": "SNAPSHOT_PROVENANCE_UNVERIFIED"}
    except Exception as exc:
        return missing(NASDAQ_INDEX, exc, "INDEX_MEMBERSHIP")

def tsmc_revenue(asof, path=None):
    """Official TSMC monthly IR export is accepted only with recorded publication time."""
    if not path:
        return missing(TSMC_IR, "Official IR monthly revenue export not configured", "TSMC_REVENUE")
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not all(k in obj for k in ("month", "revenue", "unit", "published_at", "source_url")):
            raise ValueError("Missing monthly revenue fields")
        if obj["month"] > asof[:7] or not obj["source_url"].startswith("https://investor.tsmc.com/"):
            raise ValueError("Future month or nonofficial source")
        return {"status": "RAW_AVAILABLE", "source_kind": "TSMC_REVENUE",
                "source_url": obj["source_url"], "data": obj,
                "quality": "MANUAL_SOURCE_PENDING_INDEPENDENT_VERIFICATION"}
    except Exception as exc:
        return missing(TSMC_IR, exc, "TSMC_REVENUE")

def valuation_earnings(asof, sec_snapshot=None):
    """Historical SEC earnings only; cannot fabricate NTM consensus or forward PE."""
    if not sec_snapshot or sec_snapshot.get("status") != "RAW_AVAILABLE":
        return missing("https://data.sec.gov/", "SEC financial facts unavailable", "VALUATION_EARNINGS")
    tags = ("NetIncomeLoss", "EarningsPerShareDiluted", "CommonStockSharesOutstanding")
    facts = {tag: sec_gaap_facts(sec_snapshot, tag, asof) for tag in tags}
    return {"status": "RAW_AVAILABLE", "source_kind": "VALUATION_EARNINGS",
            "source_url": sec_snapshot["source_url"], "facts": facts,
            "quality": "HISTORICAL_GAAP_ONLY_FORWARD_PE_MISSING"}

def collect_six_sources(asof, finra_csv=None, ndx_snapshot=None, sox_snapshot=None, tsmc_file=None,
                        sec_symbols=("MSFT","GOOGL","AMZN","META","NVDA","AMD","AVGO","MU")):
    date.fromisoformat(asof)
    sec = {sym: sec_companyfacts(sym) for sym in sec_symbols}
    return {
        "semiconductor_fundamentals": {"sec": sec, "tsmc": tsmc_revenue(asof, tsmc_file)},
        "trend_breadth": {"ndx": constituents(asof, ndx_snapshot),
                          "sox": constituents(asof, sox_snapshot)},
        "credit_financing": {"finra": finra_margin(asof, finra_csv)},
        "liquidity_leverage": {"finra": finra_margin(asof, finra_csv)},
        "valuation_earnings": valuation_earnings(asof, sec.get("NVDA")),
        "sentiment_options": {"vix": cboe_vix(asof),
                              "vx_curve": missing("https://www.cboe.com/", "Authorized VX1/VX2 settlements not configured", "VX_TERM_STRUCTURE")}
    }
