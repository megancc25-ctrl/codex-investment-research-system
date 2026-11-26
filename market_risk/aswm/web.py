"""ASWM extension of the existing loopback API; private inputs never accepted via HTTP."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from market_risk.frie.engine import evaluate as evaluate_frie
from .budget import load_private_config
from .engine import evaluate
from .registry import REGISTRY
from .storage import ASWMStore,transition
from . import reporting

class ResearchAPI:
    def __init__(self,path,frie_store,private_path=None):
        self.store=ASWMStore(path);self.frie_store=frie_store
        self.private_path=Path(private_path) if private_path else Path(__file__).resolve().parents[2]/'data/aswm/private.json'
    def context(self,risk_context=None,as_of=None):
        old=self.store.latest()
        inputs=self.store.inputs(old['snapshot_hash']) if old else {}
        risk=dict(risk_context if risk_context is not None else (inputs or {}).get('context',{}).get('risk_context',{}))
        # FRIE risk always comes from the local evidence store, never a browser override.
        f=evaluate_frie(self.frie_store.assessments(),as_of or datetime.now(timezone.utc))
        if f['risk']['level']=='UNKNOWN':risk.pop('frie',None)
        else:
            t=f['as_of'];risk['frie']={'level':f['risk']['level'],'evidence_id':f['snapshot_hash'],'economic_event_id':'frie-derived-'+f['snapshot_hash'],
              'source_url':'http://127.0.0.1/api/snapshot','quality':'VERIFIED','license_status':'ADMITTED','license_ref':'derived-from-local-admitted-evidence',
              'observed_at':t,'available_at':t,'expires_at':(datetime.fromisoformat(t)+timedelta(days=1)).isoformat(),
              'rationale':'local research-only FRIE snapshot; not a production score'}
        try:config=load_private_config(self.private_path) if self.private_path.exists() else None
        except (OSError,ValueError,TypeError):config=None
        return {'risk_context':risk,'private_config':config}
    def snapshot(self):
        now=datetime.now(timezone.utc);old=self.store.latest()
        s=evaluate(self.store.assessments(),now,catalysts=old.get('catalysts',[]) if old else [],context=self.context(as_of=now))
        s['transition']=transition(old,s);s['history']=self.store.history();s['preview']=True;s['alerts']=self.store.alerts()
        return s
    def evaluate_body(self,body):
        if not isinstance(body,dict) or body.get('schema_version','aswm-1.0')!='aswm-1.0':raise ValueError('ASWM schema required')
        allowed={'schema_version','assessments','catalysts','as_of','risk_context'}
        if set(body)-allowed:raise ValueError('unsupported input; private account/config must stay in local file')
        from market_risk.frie.server import validate_request
        as_of=validate_request(dict(body,schema_version='frie-1.0'))
        if 'risk_context' in body and not isinstance(body['risk_context'],dict):raise ValueError('risk_context object required')
        s=self.store.save(body.get('assessments',[]),as_of,catalysts=body.get('catalysts',[]),context=self.context(body.get('risk_context'),as_of))
        s['history']=self.store.history();s['alerts']=self.store.alerts()
        return s
    def get(self,path):
        if path=='/api/aswm/snapshot':return self.snapshot(),'application/json; charset=utf-8'
        if path=='/api/aswm/history':return self.store.history(),'application/json; charset=utf-8'
        if path=='/api/aswm/registry':return {'signals':[s.to_dict() for s in REGISTRY]},'application/json; charset=utf-8'
        if path=='/api/aswm/template':return {'schema_version':'aswm-1.0','assessments':[],'catalysts':[]},'application/json; charset=utf-8'
        if path in {'/api/aswm/report.json','/api/aswm/report.md','/api/aswm/report.html'}:
            s=self.snapshot()
            if path.endswith('.json'):return s,'application/json; charset=utf-8'
            if path.endswith('.md'):return reporting.markdown(s),'text/markdown; charset=utf-8'
            return reporting.html(s),'text/html; charset=utf-8'
        return None
