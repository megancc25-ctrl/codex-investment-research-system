import unittest,tempfile
from datetime import datetime,timezone
from pathlib import Path
from market_risk.frie.lcim_pit import select_vintages, evaluate_pit, candidate_states, AlertLog, ytd_comparison
NOW=datetime(2026,11,27,tzinfo=timezone.utc)
def obs(series,value,period='2026-10',**kw):
 d={'indicator_id':series,'value':value,'unit':'USD_BN','universe':'US','observation_date':period,'published_at':'2026-11-01T00:00:00Z','available_at':'2026-11-01T00:00:00Z','retrieved_at':'2026-11-02T00:00:00Z','vintage':'v1','source':'synthetic','source_url':'https://example.org/synthetic','license':'ADMITTED','license_ref':'synthetic','quality':'VERIFIED','event_id':series+'-'+period}
 d.update(kw);return d
class PITTests(unittest.TestCase):
 def test_future_revised_restricted_not_used(self):
  a=obs('debt',100);b=obs('debt',200,vintage='v2',available_at='2027-01-01T00:00:00Z',retrieved_at='2027-01-02T00:00:00Z')
  self.assertEqual(select_vintages([a,b],NOW)[('debt','2026-10')]['value'],100)
  self.assertEqual(select_vintages([dict(a,license='RESTRICTED')],NOW),{})
 def test_revisions_latest_and_conflict(self):
  a=obs('debt',100);b=obs('debt',101,vintage='v2',available_at='2026-11-03T00:00:00Z',retrieved_at='2026-11-03T00:00:00Z')
  self.assertEqual(select_vintages([a,b],NOW)[('debt','2026-10')]['value'],101)
  with self.assertRaises(ValueError):select_vintages([a,dict(a,value=102)],NOW)
 def test_calculate_and_metadata(self):
  data=[obs('debt',100),obs('gdp',1000,period='2026-09',event_id='gdp'),obs('m2',2000,event_id='m2'),obs('market_cap',5000,event_id='cap')]
  r=evaluate_pit(data,[],NOW);self.assertEqual(r['indicators']['L02']['value'],.1)
  self.assertEqual(r['indicators']['L02']['observation_date'],'2026-10');self.assertIn('published_at',r['indicators']['L02'])
 def test_different_unit_does_not_compute(self):
  data=[obs('debt',100),obs('gdp',1000,unit='USD_MN')]
  self.assertIsNone(evaluate_pit(data,[],NOW)['indicators']['L02']['value'])
 def test_history_cannot_count_duplicate_months(self):
  from market_risk.frie.lcim_pit import historical_percentile
  a=obs('debt',100,period='2026-10');b=dict(a,vintage='v2',value=101,available_at='2026-11-03T00:00:00Z',retrieved_at='2026-11-03T00:00:00Z')
  self.assertEqual(historical_percentile(100,[a,b],NOW)['sample_count'],1)
 def test_unauthorized_marketcap_cannot_influence_ipo_ratio(self):
  from market_risk.frie.lcim_pit import make_report
  e=obs('ipo',10,period='2026-10-01',event_id='event-a',event_type='IPO',issuer='A',status='COMPLETED',offering_type='IPO')
  r=make_report({'records':[obs('market_cap',1000,license='RESTRICTED')],'events':[e],'complete_universe':True},NOW)
  self.assertIsNone(r['indicators']['I02']['value'])
 def test_year_aligned_ytd(self):
  rows=[{'date':'2024-11-26','value':1,'available_at':'2024-11-27T00:00:00Z'},{'date':'2025-11-27','value':2,'available_at':'2025-11-28T00:00:00Z'}]
  self.assertEqual(ytd_comparison(rows,NOW)['sample_count'],1)
 def test_ipo_events_revisions_and_quality(self):
  from market_risk.frie.lcim_pit import issuance_metrics
  a=obs('ipo',10,period='2026-10-01',event_id='event-a',event_type='IPO',issuer='A',status='COMPLETED',offering_type='IPO',profitability='LOSS')
  b=obs('ipo',5,period='2026-11-01',event_id='event-b',event_type='IPO',issuer='B',status='COMPLETED',offering_type='IPO',profitability='PROFIT')
  r=issuance_metrics([a,a,b],NOW,market_cap=1000,complete_universe=True)
  self.assertEqual(r['I01']['value'],15);self.assertEqual(r['I06']['value'],0)
  r=issuance_metrics([a,b],NOW,market_cap=1000,complete_universe=False)
  self.assertEqual(r['I01']['quality'],'PARTIAL')
 def test_two_ipo_same_day_are_distinct_events(self):
  from market_risk.frie.lcim_pit import issuance_metrics
  a=obs('ipo',10,period='2026-10-01',event_id='a',event_type='IPO',status='COMPLETED',offering_type='IPO')
  b=obs('ipo',5,period='2026-10-01',event_id='b',event_type='IPO',status='COMPLETED',offering_type='IPO')
  self.assertEqual(issuance_metrics([a,b],NOW,market_cap=1000)['I01']['value'],15)
 def test_new_incomplete_period_is_unknown(self):
  a=obs('debt',100,period='2026-10')
  r=evaluate_pit([a],[],NOW)
  self.assertIsNone(r['indicators']['L05']['value'])
 def test_equity_debt_insider_and_ipo_performance(self):
  from market_risk.frie.lcim_pit import secondary_metrics
  def ev(id,kind,value,**kwargs):return obs(kind,value,period='2026-10-01',event_id=id,event_type=kind,**kwargs)
  records=[ev('s','equity_issuance',10),ev('b','buyback',4),ev('d','tech_bond',12),ev('h','hy_bond',8,yield_bp=800),ev('f','form4_sale',3,context='DISCRETIONARY'),ev('p','ipo_return_5',.12,benchmark_return=.05,unit='return_fraction')]
  r=secondary_metrics(records,NOW,complete_universe=True)
  self.assertEqual(r['I07']['value']['net'],6);self.assertEqual(r['I08']['value']['gross'],12)
  self.assertAlmostEqual(r['I11']['value']['5d'][0]['excess_return'],.07)
 def test_missing_buyback_does_not_assume_zero(self):
  from market_risk.frie.lcim_pit import secondary_metrics
  r=secondary_metrics([obs('equity_issuance',10,period='2026-10-01',event_type='equity_issuance')],NOW,complete_universe=False)
  self.assertIsNone(r['I07']['value']['net'])
 def test_out_of_order_alert_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   log=AlertLog(Path(d)/'events.sqlite');log.record('x','OBSERVE',NOW)
   with self.assertRaises(ValueError):log.record('x','ESCALATED',NOW.replace(year=2025))
   log.close()
 def test_evidence_independence_and_no_stale_recovery(self):
  self.assertEqual(candidate_states({'peak_drawdown':.11},None)['deleveraging'],'UNKNOWN')
  self.assertEqual(candidate_states({'peak_drawdown':.11}, {'signal':'credit','event_id':'e2','independent':True})['deleveraging'],'ESCALATED')
  with tempfile.TemporaryDirectory() as d:
   log=AlertLog(Path(d)/'events.sqlite');self.assertTrue(log.record('leverage','OBSERVE',NOW));self.assertFalse(log.record('leverage','OBSERVE',NOW));self.assertFalse(log.record('leverage','UNKNOWN',NOW));log.close()
