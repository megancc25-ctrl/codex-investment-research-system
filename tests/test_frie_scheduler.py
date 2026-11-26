import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from market_risk.frie import scheduler as s

class SchedulerTests(unittest.TestCase):
    def setUp(self): self.now=datetime(2024,8,1,12,tzinfo=timezone.utc)
    def test_default_gates_and_no_bypass(self):
        runner=s.OfflineScheduler()
        called=[]
        for kind in ['daily','weekly','monthly','quarterly','event','minute']:
            result=runner.run(kind,self.now,lambda:called.append(True))
            self.assertEqual(result['status'],'denied')
        self.assertEqual(called,[])
    def test_due_and_retry_heartbeat(self):
        runner=s.OfflineScheduler(s.Authorization(collection=True))
        calls=[]
        def job():
            calls.append(1)
            if len(calls)<3: raise RuntimeError('offline')
            return 42
        result=runner.run('daily',self.now,job,max_attempts=3)
        self.assertEqual(result['attempts'],3)
        self.assertEqual(result['retry_delays'],[1,2])
        self.assertFalse(runner.is_stale('daily',self.now+timedelta(hours=1)))
        self.assertTrue(runner.is_stale('daily',self.now+timedelta(days=2)))
        self.assertEqual(runner.run('daily',self.now,job)['status'],'not_due')
    def test_minute_license_gate(self):
        runner=s.OfflineScheduler(s.Authorization(collection=True))
        self.assertEqual(runner.run('minute',self.now,lambda:1)['status'],'denied')
    def test_persisted_dedup_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'alerts.sqlite'
            with s.AlertTransitions(path) as alerts:
                self.assertTrue(alerts.record('market','red',self.now))
                self.assertFalse(alerts.record('market','red',self.now))
            with s.AlertTransitions(path) as alerts:
                self.assertFalse(alerts.record('market','red',self.now))
                self.assertTrue(alerts.record('market','amber',self.now))
    def test_aware_time_required(self):
        with self.assertRaises(ValueError): s.OfflineScheduler().due('daily',datetime(2024,1,1))

    def test_capability_gate_and_retry_bound(self):
        runner=s.OfflineScheduler(s.Authorization(collection=True))
        self.assertEqual(runner.run('daily',self.now,lambda:1,capability='publication')['status'],'denied')
        self.assertEqual(runner.run('daily',self.now,lambda:1,capability='cache')['status'],'denied')
        def fail(): raise RuntimeError('offline')
        result=runner.run('daily',self.now,fail,max_attempts=2)
        self.assertEqual(result['status'],'failed')
        self.assertEqual(result['attempts'],2)
        self.assertTrue(runner.is_stale('daily',self.now))
        self.assertEqual(runner.heartbeat['daily'],self.now)
        with self.assertRaises(ValueError): runner.run('daily',self.now,fail,max_attempts=11)

    def test_licensed_minute_adapter(self):
        class Adapter:
            def is_licensed(self,now): return True
            def collect(self,now): return 'licensed'
        runner=s.OfflineScheduler(s.Authorization(collection=True))
        result=runner.run('minute',self.now,lambda:'bypass',minute_adapter=Adapter())
        self.assertEqual(result['value'],'licensed')
