import unittest
from datetime import datetime, timezone
from market_risk.aswm.registry import REGISTRY
from market_risk.aswm.signals import derive_signal, market_reversal
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class SignalTests(unittest.TestCase):
 def test_registry(self):
  self.assertEqual([x.id for x in REGISTRY],[f'SW{i:02}' for i in range(1,11)])
  self.assertEqual(sum(x.weight for x in REGISTRY),100)
 def test_empty_is_unknown(self):
  for s in REGISTRY:self.assertEqual(derive_signal(s.id,{},NOW)['status'],'UNKNOWN')
 def test_tokens_and_capex_cuts_are_not_hardware(self):
  self.assertEqual(derive_signal('SW04',{'token_only':True},NOW)['status'],'UNKNOWN')
  r=derive_signal('SW05',{'ocf_growth':-.1,'fcf_growth':.2,'capex_change':-.4,'roic_improving':True},NOW)
  self.assertFalse(r['hardware_support'])
 def test_two_independent_paid_businesses(self):
  b={'business_id':'a','paid_growth':True,'renewal_improving':True,'roi_positive':True}
  self.assertNotEqual(derive_signal('SW02',{'businesses':[b,b]},NOW)['status'],'CONFIRMED')
  self.assertTrue(derive_signal('SW02',{'businesses':[b,dict(b,business_id='b')]},NOW)['confirmations']['industrial'])
 def test_credit_proxy_and_software_eps_not_hardware(self):
  self.assertEqual(derive_signal('SW07',{'spread_type':'HY_PROXY','spreads_bp':[300]*21},NOW)['status'],'UNKNOWN')
  self.assertEqual(derive_signal('SW10',{'scope':'SOFTWARE','eps_revision_trend':'UP'},NOW)['status'],'UNKNOWN')
 def test_reversal_median_overlap_and_independence(self):
  rows=[{'economic_event_id':str(i),'positive_surprise':True,'industry_adjusted':True,'excess_return':v,'matured':True,'contaminated':False} for i,v in enumerate([.01,.02,.03,-.01,-.02])]
  self.assertTrue(market_reversal(rows)['passed'])
  rows[-1]['contaminated']=True
  self.assertIsNone(market_reversal(rows)['passed'])
 def test_future_quarter_does_not_confirm(self):
  facts={'commercial_breakthrough':True,'paid_business_model':True,'quarterly_releases':[{'period':'2026Q1','available_at':'2026-03-01T00:00:00Z'},{'period':'2026Q2','available_at':'2027-01-01T00:00:00Z'}]}
  self.assertIsNone(derive_signal('SW01',facts,NOW)['confirmations']['sustained'])
