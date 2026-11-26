import unittest
from test_aswm_engine import NOW,rows
from market_risk.frie.pipeline import evaluate_modules
class UnifiedTests(unittest.TestCase):
 def test_missing_sources_and_gate_statuses(self):
  r=evaluate_modules({},NOW)
  self.assertEqual(r['usable_modules'],0)
  self.assertEqual(r['crs_gates']['G1'],'NO_GO')
  self.assertTrue(all(v['status']=='UNKNOWN' for v in r['modules'].values()))
 def test_unauthorized_stale_and_future_data_never_compute(self):
  row=rows()[0];row['license_status']='UNKNOWN'
  r=evaluate_modules({'modules':{'commercialization':row}},NOW)
  self.assertEqual(r['modules']['commercialization']['quality'],'RESTRICTED')
  row=rows()[0];row['available_at']='2027-01-01T00:00:00Z'
  self.assertEqual(evaluate_modules({'modules':{'commercialization':row}},NOW)['usable_modules'],0)
 def test_circular_source_event_is_not_new_independent_vote(self):
  a=rows()[0];b=dict(a)
  r=evaluate_modules({'modules':{'funding':a,'circular_financing':b}},NOW)
  self.assertFalse(r['modules']['circular_financing']['independent_vote'])
 def test_one_invalid_module_does_not_stop_other_sources(self):
  a=rows()[0];a['facts']={'volatility_percentile':'bad','leverage_percentile':95}
  b=rows()[1];b['facts']={'businesses':[{'business_id':x,'capex_rising':True,'incremental_return_worse':True,'real_paid_demand_worse':True} for x in ('a','b')]}
  r=evaluate_modules({'modules':{'leverage':a,'commercialization':b}},NOW)
  self.assertEqual(r['modules']['leverage']['status'],'UNKNOWN')
  self.assertEqual(r['modules']['commercialization']['risk_status'],'TRIGGERED')
