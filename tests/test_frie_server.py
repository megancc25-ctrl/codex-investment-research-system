import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from market_risk.frie.server import create_server

class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=create_server(Path(self.tmp.name)/'db.sqlite',port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def test_initial_snapshot_and_page(self):
        with urlopen(self.url+'/api/snapshot') as r: data=json.load(r)
        self.assertEqual(len(data['signals']),28)
        self.assertIsNone(data['risk']['score'])
        with urlopen(self.url+'/frie.html') as r: self.assertIn('FRIE',r.read().decode())
    def test_evaluate_persist_and_report_formats(self):
        req=Request(self.url+'/api/evaluate',data=b'{"schema_version":"frie-1.0","assessments":[],"catalysts":[]}',headers={'Content-Type':'application/json'})
        with urlopen(req) as r: self.assertFalse(json.load(r)['auto_trading'])
        for suffix in ('json','md','html'):
            with urlopen(self.url+'/api/report.'+suffix) as r: self.assertEqual(r.status,200)
    def test_cross_origin_and_bad_host_blocked(self):
        for headers in ({'Origin':'https://evil.example'}, {'Host':'evil.example'}):
            req=Request(self.url+'/api/evaluate',data=b'{}',headers={'Content-Type':'application/json',**headers})
            with self.assertRaises(HTTPError) as cm: urlopen(req)
            self.assertEqual(cm.exception.code,403)
    def test_future_nonfinite_and_path_traversal_rejected(self):
        for body in (b'{"assessments":[],"as_of":"2999-01-01T00:00:00+00:00"}', b'{"assessments":[],"portfolio":{"shock":NaN}}'):
            with self.assertRaises(HTTPError) as cm:
                urlopen(Request(self.url+'/api/evaluate',data=body,headers={'Content-Type':'application/json'}))
            self.assertEqual(cm.exception.code,400)
        with self.assertRaises(HTTPError) as cm: urlopen(self.url+'/../AGENTS.md')
        self.assertEqual(cm.exception.code,404)

    def test_stress_persists_across_refresh_and_reports(self):
        body={'assessments':[],'portfolio':{'semiconductor_weight':.2,'cash_weight':.8,'shock':-.3,'max_loss':.1}}
        with urlopen(Request(self.url+'/api/evaluate',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})) as r:
            self.assertIsNotNone(json.load(r)['stress'])
        with urlopen(self.url+'/api/snapshot') as r:
            self.assertIsNotNone(json.load(r)['stress'])

if __name__=='__main__': unittest.main()
