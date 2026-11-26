import unittest
from datetime import datetime, timedelta, timezone
from market_risk.frie.engine import evaluate
from market_risk.frie.registry import REGISTRY

NOW = datetime(2026, 11, 26, 8, tzinfo=timezone.utc)

def assessment(sid, **changes):
    a = dict(signal_id=sid, status='CONFIRMED', evidence_id='ev-'+sid,
             economic_event_id='event-'+sid, source_url='https://example.org/'+sid,
             observed_at=(NOW-timedelta(hours=2)).isoformat(),
             available_at=(NOW-timedelta(hours=1)).isoformat(),
             expires_at=(NOW+timedelta(days=1)).isoformat(), quality='VERIFIED',
             license_status='ADMITTED', license_ref='offline-admission-record',
             rationale='Explicit reviewed offline assessment', counter_evidence='')
    a.update(changes)
    return a

class EngineTests(unittest.TestCase):
    def test_registry_complete(self):
        self.assertEqual(len(REGISTRY), 28)
        self.assertEqual(sum(s.weight for s in REGISTRY if s.kind == 'opportunity'),100)
        for s in REGISTRY:
            for field in ('formula','threshold','sources','frequency','ttl_days','dedup_group','unit','license_status','version'):
                self.assertTrue(getattr(s,field))

    def test_empty_unknown_not_safe(self):
        r=evaluate([],NOW)
        self.assertEqual(r['risk']['level'],'UNKNOWN')
        self.assertIsNone(r['risk']['score'])
        self.assertEqual(r['risk']['coverage'],0)
        self.assertFalse(r['auto_trading'])

    def test_full_risk_and_opportunity_coexist(self):
        r=evaluate([assessment(s.id) for s in REGISTRY],NOW)
        self.assertEqual(r['risk']['score'],100)
        self.assertEqual(r['risk']['level'],'L4')
        self.assertEqual(r['opportunity']['score'],100)
        self.assertEqual(r['model_status'],'NOT_VALIDATED')
        self.assertFalse(r['production_scoring'])

    def test_future_expired_proxy_and_unlicensed_excluded(self):
        for changes in (dict(available_at=(NOW+timedelta(seconds=1)).isoformat()),
                        dict(expires_at=NOW.isoformat()),dict(quality='PROXY'),
                        dict(license_status='UNKNOWN'),dict(license_ref='')):
            with self.subTest(changes=changes):
                r=evaluate([assessment('F01',**changes)],NOW)
                self.assertEqual(r['risk']['coverage'],0)

    def test_unknown_not_negative_and_conflicts_fail_closed(self):
        a=assessment('F01')
        b=assessment('F01',evidence_id='other',status='NOT_TRIGGERED')
        r=evaluate([a,b],NOW)
        self.assertEqual(r['signals'][0]['status'],'CONFLICT')
        self.assertEqual(r['risk']['coverage'],0)

    def test_correlated_and_cross_module_events_not_repeated(self):
        rows=[assessment(s.id,status='NOT_TRIGGERED') for s in REGISTRY]
        for row in rows:
            if row['signal_id'] in ('F01','F08','F12'):
                row.update(status='CONFIRMED',economic_event_id='one-news-event')
        r=evaluate(rows,NOW)
        self.assertEqual(r['risk']['score'],20)
        self.assertEqual(len(r['risk']['voting_events']),1)

    def test_module_missing_blocks_even_with_80_percent(self):
        rows=[assessment(s.id) for s in REGISTRY if s.kind=='risk' and s.module!='industry']
        r=evaluate(rows,NOW)
        self.assertGreaterEqual(r['risk']['coverage'],80)
        self.assertIsNone(r['risk']['score'])

    def test_naive_and_unknown_id_rejected(self):
        with self.assertRaises(ValueError): evaluate([],NOW.replace(tzinfo=None))
        with self.assertRaises(ValueError): evaluate([assessment('BAD')],NOW)

    def test_ttl_cannot_be_extended_by_import(self):
        a=assessment('F08',observed_at=(NOW-timedelta(days=30)).isoformat(),expires_at=(NOW+timedelta(days=30)).isoformat())
        self.assertEqual(evaluate([a],NOW)['risk']['coverage'],0)

    def test_explicit_supersession_is_point_in_time_and_same_signal(self):
        old=assessment('F01')
        replacement=assessment('F01',evidence_id='new',status='NOT_TRIGGERED',
                               supersedes_evidence_id=old['evidence_id'])
        r=evaluate([old,replacement],NOW)
        self.assertEqual(r['signals'][0]['status'],'NOT_TRIGGERED')
        future=dict(replacement,available_at=(NOW+timedelta(days=1)).isoformat())
        self.assertEqual(evaluate([old,future],NOW)['signals'][0]['status'],'CONFIRMED')
        invalid=assessment('F08',supersedes_evidence_id=old['evidence_id'])
        with self.assertRaises(ValueError): evaluate([old,invalid],NOW)

    def test_expired_replacement_does_not_resurrect_superseded_judgment(self):
        old=assessment('F01',expires_at=(NOW+timedelta(days=10)).isoformat())
        new=assessment('F01',evidence_id='new',status='NOT_TRIGGERED',
                       supersedes_evidence_id=old['evidence_id'],expires_at=(NOW+timedelta(hours=1)).isoformat())
        self.assertEqual(evaluate([old,new],NOW+timedelta(hours=2))['signals'][0]['status'],'UNKNOWN')

if __name__=='__main__': unittest.main()
