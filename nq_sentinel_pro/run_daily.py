import argparse
import json
from sentinel.pipeline import download,load,backtest,make_report
p=argparse.ArgumentParser()
p.add_argument("--download",action="store_true")
p.add_argument("--prices",default="data/market_ohlc.csv")
p.add_argument("--out",default="reports")
p.add_argument("--period",default="10y")
args=p.parse_args()
if args.download:
    print("Optional vendor download issues:",json.dumps(download(args.prices,args.period)))
bars=load(args.prices)
result=backtest(bars)
report=make_report(bars,result,args.out)
print(json.dumps({"market_date":report["market_date"],"data_quality":report["data_quality"],"level":report["signal"]["level"]},indent=2))
