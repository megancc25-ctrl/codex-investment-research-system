"""Minimal official FRED CSV client. Current-vintage series are not PIT histories."""
from __future__ import annotations
import csv, hashlib, io, json, time, urllib.error, urllib.parse, urllib.request
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
# Populate only after the series owner's storage and internal-use terms have been reviewed.
CACHE_LICENSE_APPROVALS = {}
BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
API_URL = "https://api.stlouisfed.org/fred/series/observations"

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

def _parse_api_json(raw, asof):
    payload = json.loads(raw.decode("utf-8"))
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise ValueError("Unexpected FRED API response schema")
    result = {}
    for row in observations:
        day, value = row.get("date"), row.get("value")
        if not day or day > asof or value in (None, ".", ""):
            continue
        datetime.strptime(day, "%Y-%m-%d")
        number = float(value)
        if number != number or abs(number) == float("inf"):
            raise ValueError("Non-finite FRED observation")
        result[day] = number
    return result


def _read_response(request, opener, timeout):
    with opener(request, timeout=timeout) as response:
        return response.read()


def fetch_series(series_key, asof, opener=None, timeout=15, retries=2, api_key=None, sleep=time.sleep):
    # CRS 1.1 engineering delivery has no admitted live sources. An injected
    # transport is reserved for offline contract tests, never selected by CLI.
    if opener is None:
        raise PermissionError("LICENSE_BLOCKED: live FRED collection is not admitted")
    if series_key not in SERIES:
        raise ValueError("FRED series key is not allowlisted")
    datetime.strptime(asof, "%Y-%m-%d")
    series_id = SERIES[series_key]
    api_key = api_key if api_key is not None else ""
    if api_key:
        params = {"series_id": series_id, "api_key": api_key, "file_type": "json",
                  "observation_end": asof, "realtime_start": asof, "realtime_end": asof,
                  "limit": 100000, "sort_order": "asc"}
        url = API_URL + "?" + urllib.parse.urlencode(params)
        source_kind = "FRED_API_VINTAGE_ASOF"
    else:
        params = {"id": series_id, "coed": asof}
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        source_kind = "FRED_CURRENT_VINTAGE_CSV"
    req = urllib.request.Request(url, headers={"User-Agent": "CRS-Research/1.0"})
    opener_fn = opener or urllib.request.urlopen
    attempts = max(1, int(retries))
    last_error = None
    for attempt in range(attempts):
        try:
            raw = _read_response(req, opener_fn, timeout)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            retryable = not isinstance(exc, urllib.error.HTTPError) or exc.code in (408, 429) or exc.code >= 500
            if not retryable or attempt + 1 >= attempts:
                break
            sleep(min(0.25 * (attempt + 1), 1.0))
    if last_error:
        message = str(last_error)
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        message = message.split("?", 1)[0] if "?" in message and "http" in message.lower() else message
        raise RuntimeError(f"FRED request failed after {attempt + 1} attempt(s): {message[:160]}") from None
    values = _parse_api_json(raw, asof) if api_key else parse_fred_csv(raw, series_id)
    values = {d: v for d, v in values.items() if d <= asof}
    if not values:
        raise ValueError("No FRED observation on or before as-of date")
    retrieved = datetime.now(timezone.utc).isoformat()
    license_status = ("RESTRICTED" if series_key in LICENSE_RESTRICTED else
                      CACHE_LICENSE_APPROVALS.get(series_key, "REVIEW_REQUIRED"))
    return {
        "series_key": series_key, "series_id": series_id, "values": values,
        "source": f"https://fred.stlouisfed.org/series/{series_id}",
        "source_kind": source_kind,
        "vintage_date": asof if api_key else None,
        "quality": "LICENSE_RESTRICTED" if series_key in LICENSE_RESTRICTED else "CURRENT_VINTAGE",
        "license_status": license_status,
        "cache_authorization": license_status if license_status == "APPROVED_FOR_INTERNAL_CACHE" else "NOT_APPROVED",
        "observation_date": max(values), "published_at": None, "retrieved_at": retrieved,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "unit_note": "FRED source units are retained; OAS series are percent, convert to bp before scoring.",
        "license_note": "Check individual series copyright and redistribution terms before publishing raw values or derived data.",
    }
