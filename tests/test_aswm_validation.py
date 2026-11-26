import unittest
from datetime import datetime,timezone,timedelta
from market_risk.aswm.validation import run_validation
class ValidationTests(unittest.TestCase):
 def fixture(self):
  dates=[(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=x)).isoformat() for x in range(100)]
  return dict(dates=dates,prices=list(range(100,200)),source='SYNTHETIC',exchange_sessions=True,admission={'status':'ADMITTED','license_ref':'test'},snapshots=[{'as_of':d,'growth_state':'KNOWN','stage':'S2','data':{}} for d in dates])
 def test_offline(self):
  r=run_validation(self.fixture(),upside_threshold=.1,horizons=(5,),purge_horizon=5,ma_window=5,trend_window=3,periods_per_year=252)
  self.assertEqual(r['status'],'synthetic_only'); self.assertFalse(r['auto_trade'])
  self.assertLess(r['partitions']['test'][-1]+5,r['partitions']['holdout'][0])
  self.assertIsNotNone(r['strategies']['aswm'])
 def test_unknown_no_fill(self):
  d=self.fixture(); d['snapshots'][0]['stage']=None
  self.assertIsNone(run_validation(d,upside_threshold=.1)['strategies']['aswm'])
 def test_future_rejected(self):
  d=self.fixture();d['snapshots'][0]['as_of']=d['dates'][1]
  with self.assertRaises(ValueError):run_validation(d,upside_threshold=.1)

 def test_admission_and_ablations_preserve_unknown(self):
  d=self.fixture();d['admission']['status']='UNKNOWN'
  with self.assertRaises(ValueError):run_validation(d,upside_threshold=.1)
  d=self.fixture();d['snapshots'][0]['growth_state']='UNKNOWN'
  r=run_validation(d,upside_threshold=.1,ablations={'without_x':['S2']*100})
  self.assertIsNone(r['ablations']['without_x']['strategy'])

 def test_metrics_and_execution(self):
  d=self.fixture()
  r=run_validation(d,upside_threshold=.01,horizons=(5,),purge_horizon=5)
  self.assertEqual(r['metrics'][0]['precision'],1)
  self.assertEqual(r['strategies']['buy_hold']['executed_exposure'][0],1)
  self.assertAlmostEqual(r['strategies']['buy_hold']['max_drawdown'],0)

 def test_multiple_folds_and_freshness(self):
  d=self.fixture();d['snapshots'][0]['as_of']='2019-12-31T00:00:00+00:00'
  with self.assertRaises(ValueError):run_validation(d,upside_threshold=.1)
  d['snapshots'][0]['revalidated_at']=d['dates'][0]
  r=run_validation(d,upside_threshold=.1,horizons=(5,),purge_horizon=5,rolling_folds=2)
  self.assertEqual(len(r['walk_forward_folds']),2)
  for fold in r['walk_forward_folds']:
   p=fold['partitions']
   self.assertLess(p['train'][-1]+5,p['validation'][0])
   self.assertLess(p['validation'][-1]+5,p['test'][0])
   self.assertLess(p['test'][-1]+5,r['partitions']['holdout'][0])
 def test_strict_stage_and_sessions(self):
  d=self.fixture(); d['snapshots'][0]['stage']='S4'
  with self.assertRaises(ValueError):run_validation(d,upside_threshold=.1)
  d=self.fixture();del d['exchange_sessions']
  with self.assertRaises(ValueError):run_validation(d,upside_threshold=.1)
  with self.assertRaises(ValueError):run_validation(self.fixture(),upside_threshold=.1,periods_per_year=True)
