"""Append-only local research records. Explicit IDs are immutable; runs reproducible."""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .engine import evaluate, digest, timestamp

def _json(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)

class Store:
    def __init__(self,path,*,namespace="frie",evaluator=None,transition_fn=None):
        if namespace not in {"frie","aswm"}: raise ValueError("unsupported research namespace")
        self.namespace=namespace
        self.evaluate=evaluator or evaluate
        self.transition_fn=transition_fn or transition
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript(self.sql('''
            CREATE TABLE IF NOT EXISTS frie_assessments(
              evidence_id TEXT PRIMARY KEY, payload TEXT NOT NULL, payload_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS frie_runs(
              snapshot_hash TEXT PRIMARY KEY, as_of TEXT NOT NULL, inputs TEXT NOT NULL,
              snapshot TEXT NOT NULL, recorded_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS frie_alerts(
              alert_id TEXT PRIMARY KEY, snapshot_hash TEXT NOT NULL, payload TEXT NOT NULL);
            '''))
            for table in (self.sql(n) for n in ('frie_assessments','frie_runs','frie_alerts')):
                for action in ('UPDATE','DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'append-only research history'); END")
    def sql(self,statement):
        return statement.replace("frie_",self.namespace+"_")
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        return db
    def assessments(self):
        with closing(self.connect()) as db:
            return [json.loads(r['payload']) for r in db.execute(self.sql('SELECT payload FROM frie_assessments ORDER BY evidence_id'))]
    def history(self,limit=100):
        with closing(self.connect()) as db:
            return [dict(r) for r in db.execute(self.sql('SELECT snapshot_hash,as_of,recorded_at FROM frie_runs ORDER BY as_of DESC,rowid DESC LIMIT ?'), (limit,))]
    def run(self,key):
        with closing(self.connect()) as db:
            row=db.execute(self.sql('SELECT snapshot FROM frie_runs WHERE snapshot_hash=?'),(key,)).fetchone()
            return json.loads(row['snapshot']) if row else None
    def latest(self):
        h=self.history(1)
        return self.run(h[0]['snapshot_hash']) if h else None
    def inputs(self,key):
        with closing(self.connect()) as db:
            row=db.execute(self.sql('SELECT inputs FROM frie_runs WHERE snapshot_hash=?'),(key,)).fetchone()
            return json.loads(row['inputs']) if row else None
    def save(self,assessments,as_of,*,catalysts=None,portfolio=None,context=None):
        as_of=timestamp(as_of)
        # Validate imported schema even when all rows might be UNKNOWN.
        self.evaluate(self.assessments()+assessments,as_of,catalysts=catalysts,portfolio=portfolio,**({"context":context} if context is not None else {}))
        with closing(self.connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute(self.sql('SELECT snapshot,as_of FROM frie_runs ORDER BY as_of DESC,rowid DESC LIMIT 1')).fetchone()
            if prior and as_of<timestamp(prior['as_of']): raise ValueError('cannot backdate live state; use offline evaluate for historical research')
            for a in assessments:
                if a.get('status')=='UNKNOWN' and self.namespace=='frie': continue
                key=a.get('evidence_id')
                if not key: raise ValueError('evidence_id required for persistence')
                old=db.execute(self.sql('SELECT payload_hash FROM frie_assessments WHERE evidence_id=?'),(key,)).fetchone()
                if old and old['payload_hash']!=digest(a): raise ValueError('immutable evidence_id; append a new observation ID')
                db.execute(self.sql('INSERT OR IGNORE INTO frie_assessments VALUES(?,?,?)'),(key,_json(a),digest(a)))
            # All evidence remains in history; timestamps/TTL determine current eligibility.
            rows=[json.loads(r['payload']) for r in db.execute(self.sql('SELECT payload FROM frie_assessments ORDER BY evidence_id'))]
            snapshot=self.evaluate(rows,as_of,catalysts=catalysts,portfolio=portfolio,**({"context":context} if context is not None else {}))
            existing=db.execute(self.sql('SELECT snapshot FROM frie_runs WHERE snapshot_hash=?'),(snapshot['snapshot_hash'],)).fetchone()
            if existing: return json.loads(existing['snapshot'])
            previous=json.loads(prior['snapshot']) if prior else None
            snapshot['transition']=self.transition_fn(previous,snapshot)
            inputs={'assessments':rows,'as_of':as_of.isoformat(),'catalysts':catalysts,'portfolio':portfolio}
            if context is not None: inputs['context']=context
            db.execute(self.sql('INSERT INTO frie_runs VALUES(?,?,?,?,?)'),
                       (snapshot['snapshot_hash'],as_of.isoformat(),_json(inputs),_json(snapshot),datetime.now(timezone.utc).isoformat()))
            if snapshot['transition']['type'] not in {'UNCHANGED','INITIAL'}:
                alert={'type':snapshot['transition']['type'],'from':snapshot['transition']['from'],
                       'to':snapshot['transition']['to'],'as_of':as_of.isoformat(),'local_only':True,
                       'new_signals':snapshot['transition']['new_signals'],
                       'opportunity_change':snapshot['transition']['opportunity_change']}
                db.execute(self.sql('INSERT OR IGNORE INTO frie_alerts VALUES(?,?,?)'),(digest(alert),snapshot['snapshot_hash'],_json(alert)))
            return snapshot
    def recompute(self,key):
        with closing(self.connect()) as db:
            row=db.execute(self.sql('SELECT inputs FROM frie_runs WHERE snapshot_hash=?'),(key,)).fetchone()
            if not row: raise KeyError(key)
            inputs=json.loads(row['inputs'])
            return self.evaluate(inputs['assessments'],inputs['as_of'],catalysts=inputs['catalysts'],portfolio=inputs['portfolio'],**({'context':inputs['context']} if 'context' in inputs else {}))['snapshot_hash']==key
    def alerts(self):
        with closing(self.connect()) as db:
            return [json.loads(r['payload']) for r in db.execute(self.sql('SELECT payload FROM frie_alerts ORDER BY rowid DESC LIMIT 100'))]

def transition(previous,current):
    before=previous['risk']['level'] if previous else None
    after=current['risk']['level']
    previous_transition=previous.get('transition',{}) if previous else {}
    since=previous_transition.get('since',previous['as_of']) if previous and before==after else current['as_of']
    duration=(timestamp(current['as_of'])-timestamp(since)).total_seconds()
    previous_signals={s['id']:s['status'] for s in previous['signals']} if previous else {}
    new_signals=[s['id'] for s in current['signals'] if s['status'] in {'CONFIRMED','IMPROVING'}
                 and previous_signals.get(s['id'])!=s['status']]
    opp_before=previous['opportunity']['score'] if previous else None
    opp_after=current['opportunity']['score']
    if previous is None: kind='INITIAL'
    elif before==after: kind='UNCHANGED'
    elif after=='UNKNOWN': kind='DATA_UNAVAILABLE'
    elif before=='UNKNOWN': kind='BECAME_ASSESSABLE'
    elif int(after[1:])>int(before[1:]): kind='ESCALATED'
    elif after=='L0': kind='CLEARED'
    else: kind='DEESCALATED'
    if kind=='UNCHANGED' and opp_before!=opp_after:
        kind='OPPORTUNITY_DATA_UNAVAILABLE' if opp_after is None else 'OPPORTUNITY_CHANGED'
    if kind=='UNCHANGED' and new_signals: kind='SIGNALS_CHANGED'
    return {'type':kind,'from':before,'to':after,'since':since,'duration_seconds':duration,
            'new_signals':new_signals,'opportunity_change':{'from':opp_before,'to':opp_after},
            'scope':'RESEARCH_ONLY','notification':'LOCAL_ONLY'}
