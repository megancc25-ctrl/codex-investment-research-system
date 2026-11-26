import unittest
from datetime import datetime,timezone
from market_risk.aswm.budget import risk_budget
class BudgetTests(unittest.TestCase):
 def config(self):
  return {'schema_version':'aswm-private-1.0','confirmed_at':'2026-01-01T00:00:00Z','expires_at':'2026-02-01T00:00:00Z','budget_scope':'TOTAL_ACCOUNT','portfolio':{'semiconductor_weight':.3,'cash_weight':.7,'account_nav':1000,'currency':'USD','leverage':False,'completed_reductions':[]},'risk_budget':{'remaining_loss_budget':.1,'semiconductor_stress_loss':.2,'other_assets_loss':.01,'fx_loss':.01,'fees_loss':.01,'uncertainty_buffer':.01,'liquidity_limit':1}}
 def test_math_and_scope(self):
  c=self.config(); r=risk_budget(c,datetime(2026,1,2,tzinfo=timezone.utc))
  self.assertAlmostEqual(r['theoretical_ceiling'],.3)
  self.assertAlmostEqual(r['new_space_nav'],0)
  c['budget_scope']='INCREMENTAL_ADDITIONAL'
  self.assertAlmostEqual(risk_budget(c,datetime(2026,1,2,tzinfo=timezone.utc))['theoretical_ceiling'],.6)
 def test_missing_expired(self):
  c=self.config(); del c['risk_budget']['fx_loss']
  self.assertEqual(risk_budget(c,datetime(2026,1,2,tzinfo=timezone.utc))['status'],'UNKNOWN')
  self.assertEqual(risk_budget(self.config(),datetime(2026,3,2,tzinfo=timezone.utc))['status'],'BLOCKED')

 def test_no_leverage_or_missing_scope(self):
  c=self.config();c['portfolio']['leverage']=True
  self.assertEqual(risk_budget(c,datetime(2026,1,2,tzinfo=timezone.utc))['status'],'BLOCKED')
  c=self.config();del c['budget_scope']
  self.assertEqual(risk_budget(c,datetime(2026,1,2,tzinfo=timezone.utc))['status'],'UNKNOWN')
