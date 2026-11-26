import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from test_frie_engine import NOW, assessment
from market_risk.frie.storage import Store
from market_risk.frie.engine import evaluate
from market_risk.frie.registry import REGISTRY

class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'db.sqlite')
    def tearDown(self): self.tmp.cleanup()
    def test_append_only_evidence_and_idempotent_runs(self):
        rows=[assessment('F01')]
        first=self.store.save(rows,NOW)
        self.assertEqual(self.store.save(rows,NOW)['snapshot_hash'],first['snapshot_hash'])
        self.assertEqual(len(self.store.history()),1)
        with self.assertRaises(ValueError): self.store.save([assessment('F01',rationale='rewritten')],NOW)
        self.assertEqual(len(self.store.assessments()),1)
    def test_transition_unknown_is_not_recovery(self):
        rows=[assessment(s.id) for s in REGISTRY]
        r=self.store.save(rows,NOW)
        self.assertEqual(r['transition']['type'],'INITIAL')
        later=self.store.save([],NOW+timedelta(days=200))
        self.assertEqual(later['transition']['type'],'DATA_UNAVAILABLE')
        self.assertNotEqual(later['transition']['type'],'CLEARED')
    def test_history_keeps_immutable_inputs_and_recomputes_hash(self):
        r=self.store.save([assessment('F01')],NOW)
        restored=self.store.run(r['snapshot_hash'])
        self.assertEqual(restored['snapshot_hash'],r['snapshot_hash'])
        self.assertEqual(self.store.recompute(r['snapshot_hash']),True)
    def test_earlier_snapshot_cannot_reset_current_state(self):
        self.store.save([],NOW)
        with self.assertRaises(ValueError): self.store.save([],NOW-timedelta(days=1))
    def test_report_external_text_is_escaped(self):
        from market_risk.frie.reporting import render_html, markdown
        r=evaluate([assessment('F01',rationale='<script>alert(1)</script>')],NOW)
        self.assertNotIn('<script>alert(1)</script>',render_html(r))
        self.assertIn('F18',markdown(r))
        self.assertIn('O10',markdown(r))

    def test_opportunity_change_and_supersession_are_persisted(self):
        rows=[assessment(s.id,status='NOT_TRIGGERED') for s in REGISTRY]
        self.store.save(rows,NOW)
        new=assessment('O01',evidence_id='new-O01',status='CONFIRMED',supersedes_evidence_id='ev-O01')
        r=self.store.save([new],NOW+timedelta(minutes=1))
        self.assertEqual(r['transition']['type'],'OPPORTUNITY_CHANGED')
        self.assertIn('O01',r['transition']['new_signals'])
        self.assertEqual(len(self.store.alerts()),1)
        self.assertTrue(self.store.recompute(r['snapshot_hash']))

    def test_same_asof_latest_is_latest_inserted_revision(self):
        self.store.save([],NOW)
        current=self.store.save([assessment('F01')],NOW)
        self.assertEqual(self.store.latest()['snapshot_hash'],current['snapshot_hash'])

if __name__=='__main__': unittest.main()
