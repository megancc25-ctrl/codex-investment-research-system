"""Loopback-only local research API. No collection, remote publication or trading."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from .engine import evaluate, timestamp
from .registry import REGISTRY, WATCHLIST
from .reporting import markdown, render_html
from .storage import Store, transition

TEMPLATE={'schema_version':'frie-1.0','assessments':[],'catalysts':[]}

def strict_json(data):
    def invalid(value): raise ValueError('nonfinite JSON number: '+value)
    return json.loads(data,parse_constant=invalid)

def validate_request(body):
    if not isinstance(body,dict): raise ValueError('JSON object required')
    if body.get('schema_version','frie-1.0')!='frie-1.0': raise ValueError('unsupported schema_version')
    if not isinstance(body.get('assessments',[]),list): raise ValueError('assessments array required')
    catalysts=body.get('catalysts',[])
    if not isinstance(catalysts,list) or any(not isinstance(c,dict) for c in catalysts): raise ValueError('catalysts must be an array of objects')
    if len(body.get('assessments',[]))>5000: raise ValueError('too many assessments')
    now=datetime.now(timezone.utc)
    as_of=timestamp(body['as_of']) if body.get('as_of') else now
    if as_of>now: raise ValueError('future as_of not allowed')
    return as_of

def create_server(db_path,port=8765,*,private_config_path=None):
    store=Store(db_path)
    from market_risk.aswm.web import ResearchAPI
    aswm_api=ResearchAPI(db_path,store,private_config_path)
    assets=Path(__file__).resolve().parents[1]/'dashboard'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def _host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        def send(self,status,payload,content_type='application/json; charset=utf-8'):
            raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode() if content_type.startswith('application/json') else payload.encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(raw)
        def snapshot(self):
            now=datetime.now(timezone.utc)
            old=store.latest()
            # Reevaluate freshness on every read; never show a stale L0/L4 as current.
            portfolio={k:old['stress'][k] for k in ('semiconductor_weight','cash_weight','shock','max_loss')} if old and old.get('stress') else None
            s=evaluate(store.assessments(),now,catalysts=old.get('catalysts',[]) if old else [],portfolio=portfolio)
            s['transition']=transition(old,s)
            s['history']=store.history()
            s['alerts']=store.alerts()
            s['preview']=True
            return s
        def do_GET(self):
            if not self._host(): return self.send(403,{'error':'invalid Host'})
            path=urlparse(self.path).path
            if path in ('/','/frie.html','/index.html','/aswm.html'):
                file=assets/('frie.html' if path=='/' else path[1:])
                return self.send(200,file.read_text(encoding='utf-8'),'text/html; charset=utf-8')
            if path.startswith('/api/aswm/'):
                result=aswm_api.get(path)
                return self.send(200,*result) if result else self.send(404,{'error':'not found'})
            if path=='/api/research/snapshot':
                from .unified import snapshot as research_snapshot
                return self.send(200,research_snapshot(datetime.now(timezone.utc)))
            if path=='/api/snapshot': return self.send(200,self.snapshot())
            if path=='/api/template': return self.send(200,TEMPLATE)
            if path=='/api/registry': return self.send(200,{'signals':[s.to_dict() for s in REGISTRY],'watchlist':WATCHLIST})
            if path=='/api/history': return self.send(200,store.history())
            if path in ('/api/report.json','/api/report.md','/api/report.html'):
                s=self.snapshot()
                from .unified import snapshot as research_snapshot
                s['aswm']=aswm_api.snapshot();s['unified']=research_snapshot(datetime.now(timezone.utc))
                if path.endswith('.json'): return self.send(200,s)
                if path.endswith('.md'): return self.send(200,markdown(s),'text/markdown; charset=utf-8')
                return self.send(200,render_html(s),'text/html; charset=utf-8')
            return self.send(404,{'error':'not found'})
        def do_POST(self):
            if not self._host(): return self.send(403,{'error':'invalid Host'})
            origin=self.headers.get('Origin')
            if origin and origin!='http://'+self.headers.get('Host',''):
                return self.send(403,{'error':'same-origin required'})
            if self.headers.get('Sec-Fetch-Site')=='cross-site': return self.send(403,{'error':'cross-site denied'})
            if self.path not in {'/api/evaluate','/api/aswm/evaluate'}: return self.send(404,{'error':'not found'})
            if self.headers.get_content_type()!='application/json': return self.send(415,{'error':'application/json required'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=2_000_000: return self.send(413,{'error':'body must be between 1 byte and 2 MB'})
                body=strict_json(self.rfile.read(size))
                if self.path=='/api/aswm/evaluate':return self.send(200,aswm_api.evaluate_body(body))
                as_of=validate_request(body)
                s=store.save(body.get('assessments',[]),as_of,catalysts=body.get('catalysts',[]),portfolio=body.get('portfolio'))
                s['history']=store.history();s['alerts']=store.alerts()
                return self.send(200,s)
            except (ValueError,TypeError,KeyError,AttributeError) as error:
                return self.send(400,{'error':str(error)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server
