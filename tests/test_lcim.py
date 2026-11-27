import unittest
from datetime import datetime, timezone
from market_risk.frie.lcim import evaluate, percentile, registry
NOW=datetime(2026,11,27,tzinfo=timezone.utc)
class LCIMTests(unittest.TestCase):
 def test_registry_and_missing(self):
  self.assertEqual(len(registry()),21)
  r=evaluate({},NOW);self.assertEqual(len(r['indicators']),21);self.assertTrue(all(x['status']=='UNKNOWN' for x in r['indicators'].values()))
 def test_percentile_excludes_future_and_requires_120(self):
  h=[{'value':i,'available_at':'2026-01-01T00:00:00Z'} for i in range(120)]+[{'value':999,'available_at':'2027-01-01T00:00:00Z'}]
  self.assertEqual(percentile(119,h,NOW)['percentile'],100)
  self.assertIsNone(percentile(119,h[:119],NOW)['percentile'])
 def test_finra_ratios_and_missing_denominator(self):
  r=evaluate({'margin':{'debt':100,'gdp_saar':1000,'m2':2000,'market_cap':0,'unit':'USD_BN','denominator_unit':'USD_BN','cash_credit':10,'margin_credit':20}},NOW)['indicators']
  self.assertEqual(r['L02']['value'],.1);self.assertIsNone(r['L04']['value']);self.assertEqual(r['L08']['value'],-70)
 def test_duplicate_issuer_and_ytd_alignment(self):
  e={'event_id':'a','economic_event_id':'e1','issuer':'A','event_type':'IPO','event_date':'2026-10-01','available_at':'2026-10-02T00:00:00Z','gross_proceeds':10,'issuer_proceeds':7,'secondary_proceeds':3,'unit':'USD_BN','status':'COMPLETED','offering_type':'IPO','profitability':'LOSS'}
  f=dict(e,event_id='b',economic_event_id='e2',issuer='B',gross_proceeds=5,issuer_proceeds=5,secondary_proceeds=0)
  r=evaluate({'offerings':[e,e,f],'market_cap':1000,'unit':'USD_BN'},NOW)['indicators']
  self.assertEqual(r['I01']['value'],15);self.assertEqual(r['I04']['value']['count'],2);self.assertEqual(r['I05']['value']['top2'],1)
 def test_future_and_conflicting_event_never_count(self):
  e={'event_id':'x','economic_event_id':'e','event_type':'IPO','event_date':'2026-10-01','available_at':'2027-01-01T00:00:00Z','gross_proceeds':99,'unit':'USD_BN','status':'COMPLETED','offering_type':'IPO'}
  self.assertIsNone(evaluate({'offerings':[e],'unit':'USD_BN'},NOW)['indicators']['I01']['value'])
 def test_form4_is_not_automatic_insider_bearish(self):
  r=evaluate({'form4':[{'event_id':'a','available_at':'2026-10-01T00:00:00Z','net_sale':10,'context':'UNKNOWN'}]},NOW)
  self.assertEqual(r['indicators']['I10']['status'],'UNKNOWN')
if __name__=='__main__':unittest.main()
