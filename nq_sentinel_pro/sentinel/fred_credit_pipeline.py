"""Reproducible FRED credit-spread research pipeline.

Public CSV is a current vintage, NOT an as-known-at-the-time ALFRED vintage.
The three OAS series are percentage points, not basis points.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SERIES = {"hy_oas":"BAMLH0A0HYM2", "ig_oas":"BAMLC0A0CM",
          "ccc_oas":"BAMLH0A3HYC"}
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
MIN_HISTORY = 60

def parse_csv(raw, series):
    rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    if not rows:
        raise ValueError("Empty FRED response")
    result={}
    for r in rows:
        day=r.get("observation_date") or r.get("DATE")
        value=r.get(series)
        if not day or value is None:
            raise ValueError("Unexpected FRED schema")
        datetime.strptime(day,"%Y-%m-%d")
        if value.strip() in ("", "."):
            continue
        number=float(value)
        if not math.isfinite(number) or number<0:
            raise ValueError("Invalid credit spread")
        if day in result:
            raise ValueError("Duplicate observation date")
        result[day]=number
    if len(result)<MIN_HISTORY:
        raise ValueError("Insufficient historical observations")
    return result

def api_to_csv(payload, series):
    """Normalize official FRED API v1 JSON into the same audited CSV schema."""
    data=json.loads(payload.decode("utf-8"))
    if not isinstance(data.get("observations"),list):
        raise ValueError("Missing FRED API observations")
    stream=io.StringIO()
    writer=csv.writer(stream,lineterminator="\\n")
    writer.writerow(["observation_date",series])
    for row in data["observations"]:
        writer.writerow([row["date"],row["value"]])
    return stream.getvalue().encode("utf-8")

def _request(req, opener, timeout=12):
    if opener is None:
        opener=lambda request:urllib.request.urlopen(request,timeout=timeout)
    with opener(req) as response:
        raw=response.read(10_000_001)
    if len(raw)>10_000_000:
        raise ValueError("FRED response exceeds size limit")
    return raw

def download(series, opener=None, api_key=None, attempts=2):
    """API preferred when configured; otherwise public graph CSV.

    Bounded retries; HTTP authentication errors do not trigger a fallback
    that might hide misconfiguration. Returned URL never contains API key.
    """
    key=api_key if api_key is not None else os.getenv("FRED_API_KEY","")
    if key:
        query=urllib.parse.urlencode({"series_id":series,"api_key":key,"file_type":"json"})
        url="https://api.stlouisfed.org/fred/series/observations?"+query
        public_url="https://api.stlouisfed.org/fred/series/observations?series_id="+series
        backend="FRED_API"
    else:
        url=URL+series
        public_url=url
        backend="FRED_GRAPH"
    request=urllib.request.Request(url,headers={"User-Agent":"NQ-Sentinel-Pro-Research/2.0"})
    last=None
    for attempt in range(attempts):
        try:
            raw=_request(request,opener)
            return (api_to_csv(raw,series) if key else raw),backend,public_url
        except urllib.error.HTTPError as exc:
            if exc.code in (400,401,403,404):
                raise ValueError("FRED API authorization/configuration HTTP "+str(exc.code)) from None
            last=exc
        except (TimeoutError,OSError) as exc:
            last=exc
        if attempt+1<attempts:
            time.sleep(min(2**attempt,2))
    raise RuntimeError("FRED "+backend+" failed after "+str(attempts)+
                       " attempts: "+type(last).__name__) from None

def compute(history, asof, min_history=MIN_HISTORY):
    """Expanding prior-only percentile and 20-observation spread change.
    Risk percentile is *not* a calibrated credit-module score.
    """
    dates=sorted(d for d in history if d<=asof)
    rows=[]
    for i,day in enumerate(dates):
        if i<max(min_history,20):
            continue
        previous=[history[d] for d in dates[:i]]
        current=history[day]
        rank=100*sum(v<=current for v in previous)/len(previous)
        rows.append({"date":day,"value_pct_points":current,
                     "change_20obs_pct_points":round(current-history[dates[i-20]],6),
                     "expanding_risk_percentile":round(rank,6),
                     "prior_observations":len(previous)})
    return rows

def run(asof, output, opener=None):
    datetime.strptime(asof,"%Y-%m-%d")
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    histories={}
    manifest={"asof":asof,"generated_utc":datetime.now(timezone.utc).isoformat(),
              "series":{},"errors":{},
              "pit_status":"CURRENT_VINTAGE_ONLY_NOT_HISTORICAL_PIT_VERIFIED",
              "full_credit_financing_module":"MISSING_FINRA",
              "note":"Current-vintage FRED CSV cannot establish original historical publication timestamps."}
    for name,series in SERIES.items():
        try:
            raw,backend,public_url=download(series,opener)
            history=parse_csv(raw,series)
            path=output/(series+".raw.csv")
            path.write_bytes(raw)
            histories[name]=history
            manifest["series"][name]={"fred_id":series,"url":public_url,"backend":backend,
                "raw_sha256":hashlib.sha256(raw).hexdigest(),
                "raw_file":path.name,
                "observations":len(history),
                "last_observation":max(history),
                "first_observation":min(history)}
        except Exception as exc:
            manifest["errors"][name]=f"{type(exc).__name__}: {str(exc)[:180]}"
    factors=[]
    for name,history in histories.items():
        for r in compute(history,asof):
            factors.append({"series":name,**r})
    factors.sort(key=lambda x:(x["date"],x["series"]))
    fields=("date","series","value_pct_points","change_20obs_pct_points",
            "expanding_risk_percentile","prior_observations")
    with (output/"fred_credit_factors.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(factors)
    manifest["factor_rows"]=len(factors)
    manifest["all_three_available"]=len(histories)==3
    manifest["all_three_with_factor_rows"]=all(any(x["series"]==name for x in factors) for name in SERIES)
    (output/"fred_credit_audit.json").write_text(
        json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--asof",default=datetime.now(timezone.utc).date().isoformat())
    p.add_argument("--out",default="reports/fred_credit")
    args=p.parse_args()
    result=run(args.asof,args.out)
    print(json.dumps(result,indent=2))
    if not result["all_three_available"] or not result["all_three_with_factor_rows"]:
        raise SystemExit(1)
