"""Minimal official FRED CSV client. Current-vintage series are not PIT histories."""
from __future__ import annotations
import csv, hashlib, io, urllib.parse, urllib.request
from datetime import datetime, timezone

SERIES = {
    "hy_oas": "BAMLH0A0HYM2", "ig_oas": "BAMLC0A0CM", "ccc_oas": "BAMLH0A3HYC",
    "ust10y": "DGS10", "ust30y": "DGS30", "real10y": "DFII10", "vix": "VIXCLS",
    "sofr": "SOFR", "iorb": "IORB", "nfci": "NFCI", "reserves": "WRESBAL",
    "rrp": "RRPONTSYD", "tga": "WTREGEN", "broad_usd": "DTWEXBGS",
    "case_shiller": "CSUSHPISA", "home_sales": "EXHOSLUSM495S",
    "mortgage30y": "MORTGAGE30US", "cpi": "CPIAUCSL", "stlfsi": "STLFSI4",
}
LICENSE_RESTRICTED = {"hy_oas", "ig_oas", "ccc_oas"}
BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

def parse_fred_csv(raw: bytes, series_id: str):
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("Empty FRED response")
    result = {}
    for row in rows:
        day = row.get("observation_date") or row.get("DATE")
        value = row.get(series_id)
        if not day or value is None:
            raise ValueError("Unexpected FRED CSV schema")
        datetime.strptime(day, "%Y-%m-%d")
        if value.strip() in ("", "."):
            continue
        number = float(value)
        if number != number or abs(number) == float("inf"):
            raise ValueError("Non-finite FRED observation")
        if day in result:
            raise ValueError("Duplicate FRED observation date")
        result[day] = number
    return result

def fetch_series(series_key, asof, opener=None, timeout=20):
    if series_key not in SERIES:
        raise ValueError("FRED series key is not allowlisted")
    datetime.strptime(asof, "%Y-%m-%d")
    series_id = SERIES[series_key]
    query = urllib.parse.urlencode({"id": series_id, "coed": asof})
    url = BASE_URL + "?" + query
    req = urllib.request.Request(url, headers={"User-Agent": "CRS-Research/1.0"})
    open_url = opener or (lambda request: urllib.request.urlopen(request, timeout=timeout))
    with open_url(req) as response:
        raw = response.read()
    values = parse_fred_csv(raw, series_id)
    values = {d: v for d, v in values.items() if d <= asof}
    if not values:
        raise ValueError("No FRED observation on or before as-of date")
    retrieved = datetime.now(timezone.utc).isoformat()
    return {
        "series_key": series_key, "series_id": series_id, "values": values,
        "source": f"https://fred.stlouisfed.org/series/{series_id}",
        "source_kind": "FRED_CURRENT_VINTAGE",
        "quality": "LICENSE_RESTRICTED" if series_key in LICENSE_RESTRICTED else "CURRENT_VINTAGE",
        "observation_date": max(values), "published_at": None, "retrieved_at": retrieved,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "unit_note": "FRED source units are retained; OAS series are percent, convert to bp before scoring.",
        "license_note": "Check individual series copyright and redistribution terms before publishing raw values or derived data.",
    }
