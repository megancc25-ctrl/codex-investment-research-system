import unittest
from datetime import timedelta
from test_aswm_engine import rows,context,NOW
from market_risk.aswm.engine import evaluate
from market_risk.aswm.reporting import public_snapshot
class BoundaryTests(unittest.TestCase):
 def test_valuation_failure_is_not_hardware_failure(self):
  c=context();c['risk_context']['valuation']['state']='FAIL'
  s=evaluate(rows(),NOW,context=c)
  self.assertEqual(s['hardware']['status'],'SUPPORTED')
  self.assertEqual(s['applications']['status'],'SUPPORTED')
  self.assertEqual(s['growth']['state'],'S3')
  self.assertIn('valuation_failed',s['admission']['blockers'])
  self.assertFalse(s['admission']['execution_allowed'])
 def test_naive_event_and_future_returns_do_not_qualify(self):
  a=rows();a[7]['facts']['one_day_reactions'][0]['available_at']='2027-01-01T00:00:00Z'
  self.assertEqual(evaluate(a,NOW,context=context())['growth']['state'],'UNKNOWN')
 def test_public_export_excludes_budget_values(self):
  s=evaluate([],NOW);s['budget']={'account_nav':99999,'theoretical_max_weight':.42}
  r=public_snapshot(s)
  self.assertNotIn('account_nav',r['budget'])
  self.assertNotIn('theoretical_max_weight',r['budget'])
 def test_unvalidated_context_cannot_enable_trading(self):
  c=context();c['model_status']='VALIDATED';c['auto_trading']=True
  s=evaluate(rows(),NOW,context=c)
  self.assertEqual(s['model_status'],'NOT_VALIDATED');self.assertFalse(s['auto_trading'])
 def test_new_failed_session_invalidates_old_five_day_confirmation(self):
  a=rows();a[7]['facts']['exchange_session_closes'].append('2026-11-24T21:00:00Z')
  s=evaluate(a,NOW,context=context())
  self.assertEqual(s['growth']['state'],'S0')
 def test_bad_private_config_does_not_hide_valid_industry_evidence(self):
  from test_aswm_budget import BudgetTests
  c=context();p=BudgetTests().config();p['confirmed_at']=(NOW-timedelta(days=1)).isoformat();p['expires_at']=(NOW+timedelta(days=10)).isoformat();p['risk_budget']['fx_loss']='bad';c['private_config']=p
  s=evaluate(rows(),NOW,context=c)
  self.assertEqual(s['growth']['state'],'S3');self.assertEqual(s['budget']['status'],'UNKNOWN')
