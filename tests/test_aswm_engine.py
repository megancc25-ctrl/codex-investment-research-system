import unittest
from datetime import datetime,timezone,timedelta
from market_risk.aswm.engine import evaluate
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def rows():
 q=[{'period':'2026Q2','available_at':'2026-08-01T00:00:00Z'},{'period':'2026Q3','available_at':'2026-11-01T00:00:00Z'}]
 b={'business_id':'a','paid_growth':True,'renewal_improving':True,'roi_positive':True,'ai_revenue_growth':True,'unit_economics_improving':True}
 facts=[{'commercial_breakthrough':True,'paid_business_model':True},{'businesses':[b,dict(b,business_id='b')]},{'businesses':[b,dict(b,business_id='b')]},
 {'actual_workload_growth':True,'compute_demand_growth':True,'hardware_orders_growth':True},
 {'ocf_growth':.2,'fcf_growth':.1,'capex_change':.1,'roic_improving':True},
 {'independent_external_orders':True,'order_conversion':True,'utilization_improving':True},
 {'spread_type':'TECH_MATCHED','matched_rating':True,'matched_maturity':True,'spreads_bp':list(range(200,178,-1)),'sustained_credit_stability':True},
 {'one_day_reactions':[{'economic_event_id':str(i),'positive_surprise':True,'industry_adjusted':True,'matured':True,'contaminated':False,'excess_return':.01} for i in range(5)],'five_day_improving':True,'twenty_day_improving':True,'bad_news_muted':True,
  'exchange_session_closes':[f'2026-11-{d}T21:00:00Z' for d in (16,17,18,19,20)],'session_confirmations':[{'session_close':f'2026-11-{d}T21:00:00Z','condition_met':True} for d in (16,17,18,19,20)]},
 {'sox_closes':list(range(100,160)),'ndx_closes':[100]*60,'breadth_improving':True,'medium_term_trend':True},
 {'scope':'SEMICONDUCTOR','eps_revision_trend':'UP','orders_improving':True,'margins_improving':True}]
 result=[]
 for i,f in enumerate(facts,1):
  f.update(quarterly_releases=q,comparable_quarters=True)
  if i==8:
   for event in f['one_day_reactions']:event.update(event_time='2026-09-01T12:00:00Z',expectation_available_at='2026-08-31T12:00:00Z',end_time='2026-09-02T20:00:00Z',available_at='2026-09-02T21:00:00Z')
   f.update(five_day_matured_at='2026-09-10T00:00:00Z',twenty_day_matured_at='2026-10-01T00:00:00Z')
  result.append(dict(signal_id=f'SW{i:02}',evidence_id=f'e{i}',economic_event_id=f'econ{i}',source_url='https://example.org/synthetic',quality='VERIFIED',license_status='ADMITTED',license_ref='synthetic-test',observed_at='2026-11-25T00:00:00Z',available_at='2026-11-25T01:00:00Z',expires_at='2026-11-28T00:00:00Z',rationale='synthetic audited facts',facts=f))
 return result
def context():
 base=dict(evidence_id='r',economic_event_id='risk',source_url='https://example.org/synthetic',quality='VERIFIED',license_status='ADMITTED',license_ref='synthetic',observed_at='2026-11-25T00:00:00Z',available_at='2026-11-25T01:00:00Z',expires_at='2026-11-28T00:00:00Z',rationale='synthetic risk')
 return {'risk_context':{'valuation':dict(base,state='PASS'),'crs':dict(base,state='NORMAL'),'frie':dict(base,level='L0')}}
class EngineTests(unittest.TestCase):
 def test_three_answers_and_permanent_execution_block(self):
  s=evaluate(rows(),NOW,context=context())
  self.assertEqual(s['growth']['state'],'S3')
  self.assertEqual(s['applications']['status'],'SUPPORTED')
  self.assertEqual(s['hardware']['status'],'SUPPORTED')
  self.assertEqual(s['admission']['state'],'BLOCKED')
  self.assertIn('model_not_validated',s['admission']['blockers'])
  self.assertFalse(s['auto_trading'])
 def test_software_success_not_hardware_reentry(self):
  a=rows();a[3]['facts']['hardware_orders_growth']=False
  s=evaluate(a,NOW,context=context())
  self.assertEqual(s['applications']['status'],'SUPPORTED')
  self.assertEqual(s['hardware']['status'],'NOT_CONFIRMED')
  self.assertFalse(s['admission']['research_candidate'])
 def test_unknown_no_zero_fill(self):
  s=evaluate([],NOW)
  self.assertEqual(s['growth']['state'],'UNKNOWN')
  self.assertIsNone(s['growth']['score'])
  self.assertEqual(s['growth']['score_interval'],[0,100])
 def test_same_event_and_five_repeat_runs_do_not_confirm(self):
  a=rows()
  for r in a:r['economic_event_id']='one'
  self.assertLess(evaluate(a,NOW,context=context())['growth']['score'],45)
  a=rows();a[7]['facts']['session_confirmations']=[a[7]['facts']['session_confirmations'][0]]*5
  self.assertNotIn(evaluate(a,NOW,context=context())['growth']['state'],('S1','S2','S3'))
 def test_severe_crs_blocks_despite_growth(self):
  c=context();c['risk_context']['crs']['state']='SEVERE'
  s=evaluate(rows(),NOW,context=c)
  self.assertEqual(s['growth']['state'],'S3')
  self.assertIn('crs_severe',s['admission']['blockers'])
 def test_expiry_and_future_cannot_confirm(self):
  a=rows();a[6]['available_at']='2027-01-01T00:00:00Z'
  self.assertEqual(evaluate(a,NOW,context=context())['growth']['state'],'UNKNOWN')
  self.assertEqual(evaluate(rows(),NOW+timedelta(days=5),context=context())['growth']['state'],'UNKNOWN')
 def test_score_alone_cannot_promote(self):
  a=rows()
  for r in a:r['facts']={};r['status']='CONFIRMED'
  self.assertEqual(evaluate(a,NOW)['growth']['state'],'UNKNOWN')
