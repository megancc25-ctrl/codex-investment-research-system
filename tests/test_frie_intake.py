import tempfile
import unittest
from pathlib import Path
from market_risk.frie.intake import mrm_report

class IntakeTests(unittest.TestCase):
    def test_unadmitted_mrm_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'events.sqlite'
            with self.assertRaises(ValueError): mrm_report({},target)
            self.assertFalse(target.exists())
    def test_invalid_prices_do_not_leave_partial_events_in_database(self):
        from market_risk.frie.mrm import EventStore
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'events.sqlite'
            body={'admission':{'status':'ADMITTED','license_ref':'synthetic fixture'},
                  'decision_cutoff':'2026-01-03T00:00:00+00:00',
                  'events':[{'event_id':'e','economic_event_id':'econ','ticker':'TEST','event_type':'earnings',
                  'event_time':'2026-01-02T10:00:00+00:00','expectation_available_at':'2026-01-01T00:00:00+00:00',
                  'expected_value':1,'actual_value':2,'source_url':'https://example.org/synthetic','quality':'VERIFIED'}],
                  'sessions':[], 'prices':[{'ticker':'TEST','time':'2026-01-02T16:00:00+00:00',
                                          'value':100,'available_at':'2026-01-02T16:00:00+00:00'}]}
            with self.assertRaises(ValueError): mrm_report(body,target)
            if target.exists():
                with EventStore(target) as store: self.assertEqual(store.list_events(),[])

if __name__=='__main__': unittest.main()
