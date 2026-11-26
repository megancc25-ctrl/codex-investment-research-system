import unittest
from datetime import datetime, timezone, timedelta
from market_risk.frie import backtest as b

class BacktestTests(unittest.TestCase):
    def test_drawdown_and_complete_windows(self):
        labels = b.forward_labels([100, 150, 100, 90], horizons=(2,), thresholds=(.1,.2,.3))
        self.assertEqual(len(labels), 2)
        self.assertAlmostEqual(labels[0].drawdown, 1/3)
        self.assertTrue(all(labels[0].events.values()))
        self.assertEqual(b.forward_labels([100]*20), [])
    def test_all_thresholds_and_horizons(self):
        labels = b.forward_labels([100]*121)
        self.assertEqual({x.horizon for x in labels}, {20,60,120})
        self.assertEqual(set(labels[0].events), {.1,.2,.3})
    def test_purged_split(self):
        train, test = b.purged_split(100, 70, 20)
        self.assertEqual(train[-1],49)
        self.assertEqual(test[0],70)
        self.assertLess(train[-1]+20,test[0])
    def test_metrics_missing_denominators(self):
        result = b.classification_metrics([False,False],[False,False])
        self.assertIsNone(result['precision'])
        self.assertIsNone(result['recall'])
        self.assertEqual(result['accuracy'],1)
    def test_execution_lag_and_cost(self):
        result = b.simulate_exposure([100,110,121], [0,1,1], cost_bps=10)
        self.assertEqual(result['executed_exposure'],[1,0,1])
        self.assertAlmostEqual(result['strategy_returns'][0],.1)
        self.assertAlmostEqual(result['strategy_returns'][1],-.001)
        self.assertFalse(result['auto_trade'])
    def test_coverage_requires_full_window(self):
        dates=[datetime(2024,8,1,tzinfo=timezone.utc)+timedelta(days=i) for i in range(31)]
        result=b.historical_coverage(dates)
        self.assertTrue(all(x['status']=='unavailable' for x in result))
    def test_invalid_prices(self):
        for value in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError): b.forward_labels([100,value])

    def test_baseline_and_ablation(self):
        signals=b.moving_average_signals([100,90,80],window=2)
        self.assertEqual(signals,[1,0,0])
        result=b.simulate_exposure([100,90,80],signals)
        self.assertEqual(result['executed_exposure'],[1,1,0])
        calls=[]
        def evaluate(scores):
            calls.append(set(scores))
            return len(scores)
        report=b.evaluate_ablations({'value':[1,2],'credit':[3,4]},evaluate)
        self.assertEqual(report,{'all':2,'without_value':1,'without_credit':1})
        self.assertEqual(calls,[{'value','credit'},{'credit'},{'value'}])

    def test_horizon_tail_is_never_labeled(self):
        labels=b.forward_labels([100]*130)
        for label in labels:
            self.assertLess(label.index+label.horizon,130)
        self.assertEqual(sum(x.horizon==120 for x in labels),10)
