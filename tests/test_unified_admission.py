import unittest
from market_risk.frie.admission import check_access
class AdmissionTests(unittest.TestCase):
 def test_public_permission_does_not_activate_source(self):
  m={'sources':[{'id':'public','live_enabled':False,'uses':{'internal_analysis':{'status':'ALLOWED'}}}]}
  self.assertFalse(check_access(m,'public','internal_analysis',project_authorized=True,g1_passed=True)['allowed'])
 def test_each_purpose_must_be_allowed(self):
  m={'sources':[{'id':'x','live_enabled':True,'uses':{'read':{'status':'ALLOWED'},'publish':{'status':'UNKNOWN'}}}]}
  self.assertFalse(check_access(m,'x','publish',project_authorized=True,g1_passed=True)['allowed'])
  self.assertTrue(check_access(m,'x','read',project_authorized=True,g1_passed=True)['allowed'])
