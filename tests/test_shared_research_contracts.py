import tempfile
import unittest
from pathlib import Path
from test_frie_engine import NOW, assessment
from market_risk.frie.engine import resolve_assessments
from market_risk.frie.registry import REGISTRY
from market_risk.frie.storage import Store

class SharedContractsTests(unittest.TestCase):
    def test_registry_injected_evidence_resolution(self):
        subset=(REGISTRY[0],)
        rows=resolve_assessments([assessment('F01')],NOW,subset)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'CONFIRMED')
        with self.assertRaises(ValueError): resolve_assessments([assessment('F02')],NOW,subset)
    def test_namespaced_store_does_not_mix_models(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'shared.sqlite'
            a=Store(path);b=Store(path,namespace='aswm')
            a.save([assessment('F01')],NOW)
            self.assertEqual(b.assessments(),[])
            b.save([assessment('F02')],NOW)
            self.assertEqual(a.assessments()[0]['signal_id'],'F01')
    def test_unsafe_namespace_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): Store(Path(d)/'x.sqlite',namespace='bad; DROP TABLE')

if __name__=='__main__': unittest.main()
