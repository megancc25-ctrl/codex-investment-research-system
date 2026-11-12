"""Market data, close-to-next-open research simulation, and audit-ready reports."""
import csv
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from .core import evaluate, drawdown
from .risk_v2 import technical_observations, score_v2
from .official_data import official_module_observations

TICKERS = {
    "NDX":"^NDX", "SOX":"^SOX", "QQQ":"QQQ",
    "SMH":"SMH","SOXX":"SOXX",
    "NVDA":"NVDA","MSFT":"MSFT","AAPL":"AAPL","AMZN":"AMZN","GOOGL":"GOOGL","META":"META","TSLA":"TSLA",
    "MU":"MU","WDC":"WDC","STX":"STX","LITE":"LITE","COHR":"COHR","AVGO":"AVGO"
}
BREADTH = ("NVDA","MU","WDC","STX","LITE","COHR","AVGO")
REQUIRED = ("NDX","SOX","QQQ")

def download(path, period="10y"):
    import yfinance as yf
    rows = []
    failures = {}
    acquired = datetime.now(timezone.utc).isoformat()
    for name,ticker in TICKERS.items():
        try:
            df=yf.Ticker(ticker).history(period=period,auto_adjust=True,actions=False)
            if df.empty:
                raise ValueError("empty vendor series")
            for timestamp,bar in df.iterrows():
                op,cl=float(bar["Open"]),float(bar["Close"])
                if math.isfinite(op) and math.isfinite(cl) and op>0 and cl>0:
                    rows.append({"date":str(timestamp.date()),"symbol":name,"open":op,"close":cl,
                                 "source":"Yahoo_via_yfinance_UNVERIFIED","retrieved_utc":acquired})
        except Exception as exc:
            failures[name]=str(exc)[:140]
    missing=[x for x in REQUIRED if x in failures or not any(r["symbol"]==x for r in rows)]
    if missing:
        raise RuntimeError(f"Missing critical vendor series {missing}; refused report. Errors: {failures}")
    target=Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=("date","symbol","open","close","source","retrieved_utc"))
        writer.writeheader()
        writer.writerows(sorted(rows,key=lambda r:(r["date"],r["symbol"])))
    return failures

def load(path):
    result={}
    with open(path,encoding="utf-8-sig",newline="") as f:
        reader=csv.DictReader(f)
        if not {"date","symbol","open","close"}.issubset(reader.fieldnames or []):
            raise ValueError("Expected date,symbol,open,close")
        for row in reader:
            d=row["date"]
            datetime.strptime(d,"%Y-%m-%d")
            symbol=row["symbol"].upper().strip()
            op,cl=float(row["open"]),float(row["close"])
            if not symbol or not all(math.isfinite(x) and x>0 for x in (op,cl)):
                raise ValueError("Invalid OHLC")
            bucket=result.setdefault(symbol,{})
            if d in bucket:
                raise ValueError("Duplicate date/symbol")
            bucket[d]={"open":op,"close":cl}
    return result

def common_dates(bars):
    if any(s not in bars for s in REQUIRED):
        raise ValueError("Missing required NDX/SOX/QQQ series")
    dates=sorted(set(bars["NDX"]) & set(bars["SOX"]) & set(bars["QQQ"]))
    if len(dates)<260:
        raise ValueError("Need 260 common historical trading sessions")
    for a,b in zip(dates,dates[1:]):
        if (datetime.fromisoformat(b)-datetime.fromisoformat(a)).days>7:
            raise ValueError("Large calendar gap in key market series")
    return dates

def historical_close(bars, cutoff):
    from datetime import date
    return {s:{date.fromisoformat(d):r["close"] for d,r in rows.items() if d<=cutoff}
            for s,rows in bars.items()}

def signal(bars, cutoff):
    from datetime import date
    return evaluate(historical_close(bars,cutoff),date.fromisoformat(cutoff),BREADTH)

def summary(path):
    equity=[r["equity"] for r in path]
    rets=[equity[i]/equity[i-1]-1 for i in range(1,len(equity))]
    years=(datetime.fromisoformat(path[-1]["date"])-datetime.fromisoformat(path[0]["date"])).days/365.25
    return {"return":round(equity[-1]/equity[0]-1,5),
            "max_drawdown":round(drawdown(equity),5),
            "annual_vol":round(statistics.stdev(rets)*math.sqrt(252),5) if len(rets)>1 else None,
            "cagr":round((equity[-1]/equity[0])**(1/years)-1,5) if years>0 else None,
            "observations":len(path)}

def backtest(bars, commission_bps=10, slippage_bps=5, holdout_fraction=0.3):
    dates=common_dates(bars)
    if not (0.1<=holdout_fraction<=0.6) or min(commission_bps,slippage_bps)<0:
        raise ValueError("Invalid backtest assumptions")
    cutoff=max(202,int(len(dates)*(1-holdout_fraction)))
    if cutoff>=len(dates)-2:
        raise ValueError("Insufficient holdout")
    capitals={k:1.0 for k in ("sentinel","trend","buy_hold")}
    prior={k:0.0 for k in capitals}
    paths={k:[] for k in capitals}
    records=[]
    for i in range(201,len(dates)-1):
        sig=signal(bars,dates[i-1]) # previous close; today's opening fill
        targets={"sentinel":sig["model_risk_weight"],
                 "trend":float(sig["ndx_vs_200dma"]>0),
                 "buy_hold":1.0}
        now, nxt=bars["QQQ"][dates[i]]["open"],bars["QQQ"][dates[i+1]]["open"]
        ret=nxt/now-1
        for name,target in targets.items():
            fee=abs(target-prior[name])*(commission_bps+slippage_bps)/10000
            capitals[name]*=(1-fee)*(1+target*ret)
            paths[name].append({"date":dates[i+1],"equity":capitals[name],
                                "partition":"holdout" if i>=cutoff else "development"})
            prior[name]=target
        records.append({"information_date":dates[i-1],"execution_date":dates[i],
                        "level":sig["level"],"target":targets["sentinel"]})
    metrics={}
    for key,path in paths.items():
        base=[{"date":dates[201],"equity":1.0}]
        holdout=[p.copy() for p in path if p["partition"]=="holdout"]
        starting_equity=next((p["equity"] for p in reversed(path) if p["partition"]=="development"),1.0)
        for p in holdout:
            p["equity"]/=starting_equity
        metrics[key]={"full":summary(base+path),
                      "holdout":summary([{"date":dates[cutoff],"equity":1.0}]+holdout)}
    return {"last_market_date":dates[-1], "holdout_start":dates[cutoff],
            "metrics":metrics,"signals":records,
            "assumptions":{"execution":"prior session close -> next session open; QQQ open-to-open proxy",
                           "backtest":"fixed single chronological holdout, NOT walk-forward retraining",
                           "price_source":"unverified Yahoo vendor proxy; not directly tradable indices",
                           "commission_bps":commission_bps,"slippage_bps":slippage_bps}}

def make_report(bars, results, out, official_snapshot=None):
    d=results["last_market_date"]
    sig=signal(bars,d)
    modules = technical_observations(sig, d)
    if official_snapshot is not None:
        modules.update(official_module_observations(official_snapshot))
    v2 = score_v2(modules)
    report={"market_date":d,"generated_utc":datetime.now(timezone.utc).isoformat(),
            "risk_v2":v2,
            "official_data": official_snapshot,
            "data_quality":"UNVERIFIED_VENDOR_PROXY",
            "signal":sig,"last_closes":{s:bars[s][d]["close"] for s in REQUIRED},
            "holdout_start":results["holdout_start"],"metrics":results["metrics"],
            "assumptions":results["assumptions"],
            "decision":"RESEARCH_ONLY; no live execution, no fund NAV, no personalized risk recommendation"}
    target=Path(out)
    target.mkdir(parents=True,exist_ok=True)
    (target/(d+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=[f"# NQ-Sentinel Pro market report | {d}","",
           "## V2 six-module risk score: " + (str(v2["score"]) if v2["score"] is not None else "N/A"),
           f"Status: {v2['status']}; verified coverage: {v2['verified_coverage_pct']}%; candidate weights UNVALIDATED.",
           "Missing modules are not zero. Technical proxies are not independently verified.", "",
           "> Research-only, unverified third-party historical price proxy. Not real-time.",
           f"> Risk level {sig['level']} and model risk weight {sig['model_risk_weight']:.0%} are **unvalidated candidate parameters**, not individual portfolio instructions.","",
           "## Last vendor closes",
           f"NDX {report['last_closes']['NDX']:.2f}; SOX {report['last_closes']['SOX']:.2f}; QQQ {report['last_closes']['QQQ']:.2f}.","",
           "## Chronological holdout results (not an independent audit)",
           f"Holdout begins {results['holdout_start']}.  Fixed rules; next-open QQQ proxy; execution costs simulated.","",
           "| Method | Holdout return | Max drawdown | Annual volatility |",
           "|---|---:|---:|---:|"]
    for key in ("buy_hold","trend","sentinel"):
        met=results["metrics"][key]["holdout"]
        lines.append(f"| {key} | {met['return']:.2%} | {met['max_drawdown']:.2%} | {met['annual_vol']:.2%} |")
    lines+=["","Missing: authorized exchange data cross-check, fund holdings/NAV, real fund execution timing, taxes, independent walk-forward tests.",
            "Do not use an unverified score to place trades."]
    (target/(d+".md")).write_text("\n".join(lines)+"\n",encoding="utf-8")
    return report
