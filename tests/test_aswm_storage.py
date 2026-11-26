import unittest,tempfile
from pathlib import Path
from datetime import timedelta
from test_aswm_engine import NOW,rows,context
from market_risk.aswm.storage import ASWMStore
class StorageTests(unittest.TestCase):
 def test_recompute_duplicate_and_expiry(self):
  with tempfile.TemporaryDirectory() as d:
   s=ASWMStore(Path(d)/'shared.sqlite');a=s.save(rows(),NOW,context=context())
   self.assertTrue(s.recompute(a['snapshot_hash']))
   s.save([],NOW+timedelta(minutes=1),context=context())
   self.assertEqual(s.alerts(),[])
   b=s.save([],NOW+timedelta(days=5),context=context())
   self.assertEqual(b['transition']['type'],'INVALIDATED')
   self.assertEqual(len(s.alerts()),1)
 def test_derived_unknown_is_still_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   a=rows()[0];a['facts']={};a['status']='UNKNOWN'
   s=ASWMStore(Path(d)/'s.sqlite');s.save([a],NOW)
   self.assertEqual(len(s.assessments()),1)
