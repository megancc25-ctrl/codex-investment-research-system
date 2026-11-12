"""Safe bounded network diagnostics for FRED endpoints.

Never log credentials, URL query strings or response bodies.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime,timezone
from pathlib import Path

TARGETS={
    "fred_graph":"https://fred.stlouisfed.org/graph/fredgraph.csv?id=BAMLH0A0HYM2",
    "fred_api":"https://api.stlouisfed.org/fred/series/observations?series_id=BAMLH0A0HYM2&file_type=json",
    "fred_site":"https://fred.stlouisfed.org/",
    "fred_api_root":"https://api.stlouisfed.org/",
}
def probe(label,url,timeout=9):
    start=time.monotonic()
    request=urllib.request.Request(url,headers={"User-Agent":"NQ-Sentinel-Diagnostics/2.0"})
    try:
        with urllib.request.urlopen(request,timeout=timeout) as resp:
            resp.read(256)
            return {"endpoint":label,"status":resp.status,
                    "elapsed_ms":round((time.monotonic()-start)*1000),
                    "outcome":"REACHABLE"}
    except urllib.error.HTTPError as exc:
        # 400 on API without a key is expected and proves HTTP reachability.
        return {"endpoint":label,"status":exc.code,
                "elapsed_ms":round((time.monotonic()-start)*1000),
                "outcome":"HTTP_ERROR"}
    except Exception as exc:
        return {"endpoint":label,"status":None,
                "elapsed_ms":round((time.monotonic()-start)*1000),
                "outcome":type(exc).__name__}

def run(out):
    results=[probe(k,v) for k,v in TARGETS.items()]
    report={"checked_at":datetime.now(timezone.utc).isoformat(),
            "has_api_key":bool(os.getenv("FRED_API_KEY")),
            "results":results,
            "note":"elapsed_ms includes DNS, TLS, server response and first read; not isolated TCP connect time"}
    Path(out).parent.mkdir(parents=True,exist_ok=True)
    Path(out).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
    return report
if __name__=="__main__":
    run("reports/fred_credit/network_diagnostics.json")
