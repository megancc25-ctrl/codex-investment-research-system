import csv
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from sentinel.core import evaluate,drawdown
from sentinel.pipeline import load,backtest,make_report
from local_portfolio import scenario_table,write_obsidian

class TestSentinel(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.csv=self.root/"prices.csv"
        d=date(2023,1,2)
        with self.csv.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(("date","symbol","open","close"))
            for i in range(420):
                while d.weekday()>=5:d+=timedelta(days=1)
                for sym,k in (("NDX",1),("SOX",1.6),("QQQ",0.5)):
                    price=100*k*(1+.001*i)
                    w.writerow((d,sym,price,price*1.001))
                d+=timedelta(days=1)
    def tearDown(self):
        self.tmp.cleanup()
    def test_fixed_holdout(self):
        b=load(self.csv)
        result=backtest(b)
        self.assertGreater(result["metrics"]["buy_hold"]["holdout"]["observations"],30)
        report=make_report(b,result,self.root/"reports")
        self.assertEqual(report["data_quality"],"UNVERIFIED_VENDOR_PROXY")
    def test_costs_cannot_improve_bullish_strategy(self):
        bars=load(self.csv)
        a=backtest(bars,0,0)["metrics"]["sentinel"]["full"]["return"]
        b=backtest(bars,100,50)["metrics"]["sentinel"]["full"]["return"]
        self.assertGreaterEqual(a,b)
    def test_future_close_does_not_change_past_signal(self):
        bars=load(self.csv)
        dates=sorted(set(bars["NDX"])&set(bars["SOX"]))
        from sentinel.pipeline import signal
        before=signal(bars,dates[-2])
        bars["SOX"][dates[-1]]["close"]*=0.01
        self.assertEqual(before,signal(bars,dates[-2]))
    def test_duplicate_rejected(self):
        with self.csv.open("a") as f:
            f.write("2023-01-02,SOX,100,100\n")
        with self.assertRaises(ValueError):
            load(self.csv)
    def test_drawdown(self):
        self.assertAlmostEqual(drawdown([1,1.2,.9,1.3]),-.25)
    def test_private_unknown_not_cash(self):
        p={"asof":"2025-01-01","semiconductor_fund_weight":0.6,"remaining_weight":0.4,
           "semiconductor_proxy":"SOX","remaining_asset_type":"UNKNOWN","leverage":"UNKNOWN"}
        self.assertIsNone(scenario_table(p)[1]["total_nav_change_pct"])
        fn=self.root/"portfolio.private.json"
        fn.write_text(json.dumps(p),encoding="utf-8")
        out=write_obsidian(self.root/"Vault",fn)
        self.assertTrue(out.exists())
        self.assertIn("UNKNOWN",out.read_text(encoding="utf-8"))
    def test_reject_path_traversal_date(self):
        p={"asof":"../../oops","semiconductor_fund_weight":0.6,"remaining_weight":0.4,
           "semiconductor_proxy":"SOX","remaining_asset_type":"UNKNOWN","leverage":"UNKNOWN"}
        fn=self.root/"portfolio.private.json"
        fn.write_text(json.dumps(p),encoding="utf-8")
        with self.assertRaises(ValueError):
            write_obsidian(self.root/"Vault",fn)
