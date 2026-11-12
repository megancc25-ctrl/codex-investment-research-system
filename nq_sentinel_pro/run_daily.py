import argparse
import json
from sentinel.pipeline import download,load,backtest,make_report
from sentinel.official_data import fetch_official
from sentinel.free_sources import collect_six_sources
from pathlib import Path
from datetime import datetime, timezone
p=argparse.ArgumentParser()
p.add_argument("--download",action="store_true")
p.add_argument("--official",action="store_true",help="Fetch FRED official public series; fail closed per missing series")
p.add_argument("--free-sources",action="store_true",help="Collect six public source diagnostics, fail closed")
p.add_argument("--finra-csv",default=None)
p.add_argument("--ndx-snapshot",default=None)
p.add_argument("--sox-snapshot",default=None)
p.add_argument("--tsmc-file",default=None)
p.add_argument("--prices",default="data/market_ohlc.csv")
p.add_argument("--out",default="reports")
p.add_argument("--period",default="10y")
args=p.parse_args()
if args.download:
    print("Optional vendor download issues:",json.dumps(download(args.prices,args.period)))
bars=load(args.prices)
result=backtest(bars)
snapshot=fetch_official(result["last_market_date"]) if args.official else None
report=make_report(bars,result,args.out,official_snapshot=snapshot)
if args.free_sources:
    sources=collect_six_sources(result["last_market_date"], args.finra_csv,
                                args.ndx_snapshot,args.sox_snapshot,args.tsmc_file)
    # Store concise audit manifest, not large SEC companyfacts payloads.
    def compact(item):
        if isinstance(item,dict):
            return {k: ({"available": bool(v), "namespace_count": len(v)} if k=="facts" and isinstance(v,dict)
                        else compact(v)) for k,v in item.items() if k!="rows"}
        if isinstance(item,list):
            return {"count":len(item)}
        return item
    audit={"market_date":result["last_market_date"],
           "generated_utc":datetime.now(timezone.utc).isoformat(),
           "modules":compact(sources),
           "note":"Raw availability does not establish published_at or VERIFIED module scoring."}
    target=Path(args.out);target.mkdir(parents=True,exist_ok=True)
    (target/(result["last_market_date"]+".audit.json")).write_text(
        json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Six-source audit written; unverified sources excluded from official V2 score.")
print(json.dumps({"market_date":report["market_date"],"data_quality":report["data_quality"],"level":report["signal"]["level"]},indent=2))
