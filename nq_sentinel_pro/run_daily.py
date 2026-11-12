import argparse
import json
from sentinel.pipeline import download,load,backtest,make_report
from sentinel.official_data import fetch_official
p=argparse.ArgumentParser()
p.add_argument("--download",action="store_true")
p.add_argument("--official",action="store_true",help="Fetch FRED official public series; fail closed per missing series")
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
print(json.dumps({"market_date":report["market_date"],"data_quality":report["data_quality"],"level":report["signal"]["level"]},indent=2))
