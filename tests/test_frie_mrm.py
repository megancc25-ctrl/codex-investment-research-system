import unittest
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from market_risk.frie import mrm

T = datetime(2026, 1, 5, tzinfo=timezone.utc)
def event(**kw):
    args=dict(event_id='e', ticker='A', event_type='earnings', event_time=T+timedelta(hours=8), expected_value=1, actual_value=2, expectation_available_at=T-timedelta(days=1), source_url='https://example.org', quality='verified', economic_event_id='economic-e')
    args.update(kw)
    return mrm.Event(**args)
class MRMTests(unittest.TestCase):
    def setUp(self):
        self.sessions=[mrm.Session(T+timedelta(days=d,hours=9),T+timedelta(days=d,hours=16)) for d in (-3,0,1,2,3,4,7,8,9,10,11,14,15,16,17,18,21,22,23,24,25,28)]
        self.prices=[mrm.AdjustedClose(ticker,s.close,100+i*(1 if ticker=='A' else .5),s.close) for i,s in enumerate(self.sessions) for ticker in ('A','MARKET')]
    def reactions(self,events=None,**kw):
        return mrm.event_reactions(events or [event()],self.sessions,self.prices,kw.pop('decision_cutoff',T+timedelta(days=40)),**kw)
    def test_returns_benchmark_and_missing_horizon(self):
        r=self.reactions(decision_cutoff=T+timedelta(hours=17))
        self.assertAlmostEqual(r[0].excess_return,.005)
        self.assertEqual(r[1].status,'UNKNOWN')
    def test_afterhours_and_weekend_use_previous_close(self):
        for stamp in [T+timedelta(hours=18),T-timedelta(days=1)]:
            r=self.reactions([event(event_time=stamp)])
            self.assertEqual(r[0].anchor_time,self.sessions[0].close if stamp<T else self.sessions[1].close)
            self.assertIn('close-to-close',r[0].method)
    def test_overlap_and_duplicate_economic_events(self):
        e=event(event_id='other',economic_event_id='other',event_time=T+timedelta(hours=10))
        r=self.reactions([event(),replace(event(),event_id='duplicate'),e])
        self.assertEqual(len(r),6)
        self.assertTrue(r[0].contaminated)
    def test_invalid_and_late_expectations(self):
        with self.assertRaises(ValueError): event(expectation_available_at=T+timedelta(days=1))
        with self.assertRaises(ValueError): event(event_time=datetime(2026,1,1))
        with self.assertRaises(ValueError): mrm.AdjustedClose('A',T,float('nan'),T)
    def test_unavailable_price(self):
        self.prices=[replace(p,available_at=T+timedelta(days=100)) if p.ticker=='A' else p for p in self.prices]
        self.assertEqual(self.reactions()[0].status,'UNKNOWN')
    def test_store_preserves_conflicts(self):
        with mrm.EventStore(':memory:') as store:
            store.append(event()); store.append(event())
            with self.assertRaises(ValueError): store.append(replace(event(),expected_value=3))
            self.assertEqual(store.list_events(),[event()])
    def test_signals_and_ols(self):
        self.assertEqual(mrm.detect_good_news_fatigue([])['status'],'UNKNOWN')
        self.assertEqual(mrm.bad_news_amplification([])['status'],'UNKNOWN')
        result=mrm.rate_sensitivity_change([1,2,3,4,5,6],[2,4,6,12,15,18],window=3)
        self.assertAlmostEqual(result['previous_slope'],2)
        self.assertAlmostEqual(result['current_slope'],3)
        self.assertAlmostEqual(result['change'],1)
    def test_fatigue_unique_last_five_and_contamination(self):
        rows=[]
        for i,excess in enumerate((-.01,0,-.02,.01,.02)):
            e=event(event_id=str(i),economic_event_id=str(i),event_time=T+timedelta(days=i))
            rows.append(mrm.Reaction(e,5,'OK',excess_return=excess))
        rows.append(rows[-1])
        self.assertEqual(mrm.detect_good_news_fatigue(rows,horizon=5)['status'],'FLAG')
        rows[0]=replace(rows[0],contaminated=True)
        self.assertEqual(mrm.detect_good_news_fatigue(rows,horizon=5)['status'],'UNKNOWN')
    def test_bad_news_and_rate_unknown(self):
        rows=[mrm.Reaction(event(event_id=str(i),economic_event_id=str(i),actual_value=0,event_time=T+timedelta(days=i)),5,'OK',excess_return=-.02) for i in range(5)]
        self.assertEqual(mrm.bad_news_amplification(rows)['status'],'FLAG')
        self.assertEqual(mrm.rate_sensitivity_change([1]*6,[1,2,3,4,5,6],window=3)['status'],'UNKNOWN')
    def test_explicit_holiday_calendar_and_beta(self):
        self.sessions.pop(2)
        closes={s.close for s in self.sessions}
        self.prices=[p for p in self.prices if p.time in closes]
        r=self.reactions([event(event_time=T+timedelta(days=1,hours=8))],horizons=(1,),market_beta=0)
        self.assertEqual(r[0].end_time,T+timedelta(days=2,hours=16))
        self.assertAlmostEqual(r[0].excess_return,103/101-1)
    def test_naive_calendar_and_future_event(self):
        with self.assertRaises(ValueError): mrm.Session(datetime(2026,1,1),T)
        self.assertEqual(self.reactions([event(event_time=T+timedelta(days=50))]),[])
    def test_unverified_event_and_forged_reactions_are_unknown(self):
        for quality in ('UNVERIFIED','MISSING'):
            e=event(quality=quality)
            reaction=self.reactions([e])[0]
            self.assertEqual(reaction.status,'UNKNOWN')
            self.assertEqual(reaction.reason,'quality_not_verified')
            rows=[mrm.Reaction(replace(e,event_id=str(i),economic_event_id=str(i)),1,'OK',excess_return=-.1) for i in range(5)]
            self.assertEqual(mrm.detect_good_news_fatigue(rows)['status'],'UNKNOWN')
            negative=[replace(r,event=replace(r.event,actual_value=0),horizon=5) for r in rows]
            self.assertEqual(mrm.bad_news_amplification(negative)['status'],'UNKNOWN')
    def test_signals_reject_mixed_tickers(self):
        rows=[mrm.Reaction(event(ticker=t),1,'OK',excess_return=-.1) for t in ('A','B')]
        for detector in (mrm.detect_good_news_fatigue,mrm.bad_news_amplification):
            with self.assertRaises(ValueError): detector(rows)
    def test_fatigue_defaults_to_one_session(self):
        rows=[mrm.Reaction(event(event_id=str(i),economic_event_id=str(i)),1,'OK',excess_return=-.1) for i in range(5)]
        self.assertEqual(mrm.detect_good_news_fatigue(rows)['status'],'FLAG')
    def test_store_rejects_conflicting_economic_versions_before_insert(self):
        with mrm.EventStore(':memory:') as store:
            store.append(event())
            for changes in ({'actual_value':3},{'expected_value':3},{'event_time':T+timedelta(hours=10)}):
                with self.assertRaises(ValueError):
                    store.append(replace(event(),event_id='conflict',**changes))
            store.append(replace(event(),event_id='same-value-copy'))
            self.assertEqual(len(store.list_events()),2)
    def test_verified_duplicate_selection_is_order_independent(self):
        proxy=event(event_id='proxy',quality='proxy')
        verified=event(event_id='verified',quality='VERIFIED')
        for sequence in ([proxy,verified],[verified,proxy]):
            result=self.reactions(sequence)
            self.assertEqual(result[0].status,'OK')
            self.assertEqual(result[0].event.event_id,'verified')
