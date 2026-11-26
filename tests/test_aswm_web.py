import json,tempfile,threading,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from market_risk.frie.server import create_server
class WebTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=create_server(Path(self.tmp.name)/'shared.sqlite',port=0,private_config_path=Path(self.tmp.name)/'absent.json')
  self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start();self.url='http://127.0.0.1:'+str(self.s.server_port)
 def tearDown(self):self.s.shutdown();self.s.server_close();self.t.join();self.tmp.cleanup()
 def test_default_page_and_reports(self):
  for path in ('/aswm.html','/api/aswm/snapshot','/api/aswm/report.json','/api/aswm/report.md','/api/aswm/report.html','/api/research/snapshot','/api/report.md'):
   with urlopen(self.url+path) as r:self.assertEqual(r.status,200)
  with urlopen(self.url+'/api/aswm/snapshot') as r:d=json.load(r)
  self.assertEqual(d['growth']['state'],'UNKNOWN');self.assertEqual(d['admission']['state'],'BLOCKED')
  self.assertEqual(len(d['signals']),10)
 def test_save_and_reject_private_account_upload(self):
  body={'schema_version':'aswm-1.0','assessments':[],'catalysts':[]}
  def req(b):return Request(self.url+'/api/aswm/evaluate',data=json.dumps(b).encode(),headers={'Content-Type':'application/json'})
  with urlopen(req(body)) as r:self.assertFalse(json.load(r)['auto_trading'])
  with self.assertRaises(HTTPError) as c:urlopen(req(dict(body,private_config={'account_nav':1})))
  self.assertEqual(c.exception.code,400)
 def test_reports_contain_separate_aswm_column(self):
  with urlopen(self.url+'/api/report.json') as r:d=json.load(r)
  self.assertIn('aswm',d);self.assertIn('unified',d)
  self.assertIsNone(d['risk']['score'])
