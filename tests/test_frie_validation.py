import unittest
from datetime import datetime,timedelta,timezone
from market_risk.frie.validation import run_validation

class ValidationTests(unittest.TestCase):
    def fixture(self):
        dates=[(datetime(2000,1,1,tzinfo=timezone.utc)+timedelta(days=x)).isoformat() for x in range(180)]
        return dict(dates=dates,prices=[100+x for x in range(180)],source='SYNTHETIC',exchange_sessions=True,
          admission=dict(status='ADMITTED',license_ref='synthetic-test-only'),
          snapshots=[dict(as_of=d,risk=dict(score=50,blockers=[],modules={'a':dict(weight=50,intensity=1)})) for d in dates])
    def test_end_to_end(self):
        result=run_validation(self.fixture(),purge_horizon=5,ma_window=3,trend_window=2)
        self.assertEqual(result['status'],'synthetic_only')
        self.assertEqual(result['model_status'],'NOT_VALIDATED')
        self.assertEqual(len(result['metrics']),27)
        self.assertIn('without_a',result['ablations'])
        self.assertIsNotNone(result['strategies']['frie'])
        self.assertLess(result['partitions']['train'][-1]+5,result['partitions']['validation'][0])
    def test_fail_closed(self):
        data=self.fixture(); data['admission']['status']='UNKNOWN'
        with self.assertRaises(ValueError): run_validation(data)
        data=self.fixture(); data['snapshots'][0]['as_of']=data['dates'][1]
        with self.assertRaises(ValueError): run_validation(data)
        data=self.fixture(); data['exchange_sessions']=False
        with self.assertRaises(ValueError): run_validation(data)
    def test_missing_scores_omit_strategy(self):
        data=self.fixture(); data['snapshots'][0]['risk']['score']=None
        result=run_validation(data,purge_horizon=5)
        self.assertIsNone(result['strategies']['frie'])
        self.assertEqual(result['coverage']['missing_scores'],1)

    def test_horizon_specific_boundary_and_gates(self):
        data=self.fixture()
        data['snapshots'][1]['risk']['blockers']=['risk_coverage_below_80_percent']
        result=run_validation(data,purge_horizon=1)
        self.assertEqual(result['coverage']['missing_scores'],1)
        for row in result['metrics']:
            if row['partition']=='train' and row['horizon']==120:
                self.assertEqual(row['eligible_labels'],0)
            if row['partition']=='test' and row['horizon']==20:
                self.assertEqual(row['eligible_labels'],16)
        self.assertIsNone(result['strategies']['frie'])
        self.assertEqual(result['ablations']['without_a']['available_scores'],179)

    def test_invalid_prices_and_times(self):
        data=self.fixture(); data['prices'][3]=float('inf')
        with self.assertRaises(ValueError): run_validation(data)
        data=self.fixture(); data['dates'][3]=data['dates'][2]
        with self.assertRaises(ValueError): run_validation(data)
