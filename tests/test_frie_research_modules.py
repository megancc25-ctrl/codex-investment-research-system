import unittest,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_risk.frie.research_modules import rates_regression, funding_pressure, circular_financing, leverage_cycle, commercialization, RelationshipStore, lcim_ratios,reaction_paths,cashflow_panel
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class ModuleTests(unittest.TestCase):
 def test_rate_beta_units_uncertainty_and_nonoverlap(self):
  changes=[(-1)**i*(1+i%7) for i in range(260)];market=[((i*7)%13-6)/1000 for i in range(260)]
  returns=[-.001*x+.4*m+(i%3-1)*.0001 for i,(x,m) in enumerate(zip(changes,market))]
  r=rates_regression(returns,changes,market,rate_unit='bp',target='SOX',market='EX_SOFTWARE',independent_risk=True)
  self.assertEqual(r['windows']['60']['sample_count'],60)
  self.assertAlmostEqual(r['windows']['60']['beta_per_10bp'],-.01,delta=.001)
  self.assertEqual(len(r['windows']['120']['ci95_per_10bp']),2)
  with self.assertRaises(ValueError):rates_regression(returns,changes,market,rate_unit='percent',target='SOX',market='SOX')
 def test_funding_negative_fcf_not_no_cash(self):
  v={'A':{'current':[(10,20),(12,25)],'prior_year':[(10,12),(12,15)]},'B':{'current':[(10,20),(12,25)],'prior_year':[(10,12),(12,15)]}}
  r=funding_pressure(v,{'A':True,'B':True},independent_financing=None)
  self.assertEqual(r['status'],'UNKNOWN')
  self.assertIsNone(r['cash_exhaustion_claim'])
 def test_crossinvestment_alone_is_not_fraud(self):
  r=circular_financing([],None,None,None)
  self.assertEqual(r['status'],'UNKNOWN');self.assertIsNone(r['fraud_claim'])
 def test_relationship_immutability_and_currency(self):
  with tempfile.TemporaryDirectory() as d:
   s=RelationshipStore(Path(d)/'x.sqlite')
   record={'relationship_id':'a','from_company':'A','to_company':'B','kind':'guarantee','economic_event_id':'evt','amount':10,'currency':'USD','payment_type':'COMMITMENT','available_at':NOW.isoformat(),'source_url':'https://example.org/synthetic','license_status':'ADMITTED','license_ref':'synthetic','quality':'VERIFIED'}
   s.append(record);s.append(record)
   with self.assertRaises(ValueError):s.append(dict(record,amount=20))
   self.assertEqual(len(s.records(NOW)),1)
 def test_leverage_vulnerability_and_explosion_distinct(self):
  r=leverage_cycle(10,95,volatility_jump=False,liquidity_worse=False,breadth_worse=False,forced_selling=None)
  self.assertEqual(r['accumulation'],'TRIGGERED');self.assertEqual(r['explosion'],'NOT_TRIGGERED');self.assertEqual(r['otc_net_leverage'],'UNKNOWN')
 def test_commercialization_not_token_proxy(self):
  self.assertEqual(commercialization([{'business_id':'a','token_growth':True}])['risk_status'],'UNKNOWN')
 def test_lcim_units_denominator_and_samples(self):
  with self.assertRaises(ValueError):lcim_ratios(10,100,100,100,unit='billions',denominator_unit='millions')
  self.assertEqual(lcim_ratios(10,0,100,100,unit='billions',denominator_unit='billions')['debt_gdp'],None)
 def test_duplicate_relationship_does_not_double_exposure(self):
  r={'relationship_id':'a','from_company':'A','to_company':'B','economic_event_id':'evt','kind':'guarantee','amount':10,'currency':'USD','payment_type':'COMMITMENT'}
  self.assertEqual(circular_financing([r,r],None,None,None)['exposure_by_currency_and_payment_type']['USD:COMMITMENT'],10)
 def test_reaction_repair_is_censored_not_invented(self):
  p={'event_id':'e','event_time':'2026-11-20T12:00:00Z','direction':'NEGATIVE','contaminated':False,'session_closes':['2026-11-20T21:00:00Z','2026-11-23T21:00:00Z'],'available_at_per_session':['2026-11-20T22:00:00Z','2026-11-23T22:00:00Z'],'cumulative_excess_returns':[-.1,-.02]}
  r=reaction_paths([p],NOW)['paths'][0]
  self.assertTrue(r['right_censored']);self.assertIsNone(r['duration_sessions'])
  p['cumulative_excess_returns'][-1]=.01
  self.assertEqual(reaction_paths([p],NOW)['paths'][0]['duration_sessions'],2)
 def test_cashflow_negative_ocf_and_future_quarter(self):
  q={'period':'2026Q3','available_at':'2026-11-01T00:00:00Z','currency':'USD','unit':'millions','accounting_scope':'consolidated','ocf':-10,'cash_capex':20,'cash':100,'short_term_investments':50,'total_debt':200}
  p=cashflow_panel([q,dict(q,period='2026Q4',available_at='2027-01-01T00:00:00Z')],NOW)
  self.assertEqual(len(p['quarters']),1);self.assertIsNone(p['quarters'][0]['capex_ocf'])
  self.assertEqual(p['quarters'][0]['fcf'],-30);self.assertEqual(p['quarters'][0]['cash_and_short_term_stock'],150)
