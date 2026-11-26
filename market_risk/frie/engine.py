"""Deterministic evidence-to-research snapshots, independent of legacy models."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from urllib.parse import urlparse

from .registry import REGISTRY, BY_ID, MODULE_NAMES, MODULE_WEIGHTS

STATES = {'UNKNOWN','NOT_TRIGGERED','IMPROVING','CONFIRMED','CONFLICT'}
INTENSITY = {'NOT_TRIGGERED':0.,'IMPROVING':.5,'CONFIRMED':1.}

def timestamp(value):
    dt = value if isinstance(value,datetime) else datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone-aware timestamp required')
    return dt.astimezone(timezone.utc)

def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _eligible(a, spec, as_of, *, check_expiry=True):
    if a.get('status') not in STATES: raise ValueError('unsupported assessment status')
    if a['status']=='UNKNOWN': return 'unknown_assessment'
    if a.get('quality')!='VERIFIED': return 'quality_not_verified'
    if a.get('license_status')!='ADMITTED' or not a.get('license_ref'): return 'data_not_admitted'
    for key in ('evidence_id','economic_event_id','source_url','rationale'):
        if not isinstance(a.get(key),str) or not a[key].strip(): return f'missing_{key}'
    if urlparse(a['source_url']).scheme not in {'http','https'} or not urlparse(a['source_url']).netloc:
        return 'invalid_source_url'
    try:
        observed,available,expiry = (timestamp(a[k]) for k in ('observed_at','available_at','expires_at'))
    except (KeyError,ValueError,TypeError,AttributeError): return 'invalid_or_missing_timestamp'
    if observed>as_of or available>as_of: return 'not_available_as_of'
    if available<observed: return 'availability_before_observation'
    if expiry<=available:return 'expiry_not_after_availability'
    if check_expiry and min(expiry,observed+timedelta(days=spec.ttl_days))<=as_of: return 'expired'
    return None

def resolve_assessments(assessments, as_of, registry=REGISTRY):
    """Shared immutable, PIT, quality, rights and supersession evidence contract."""
    as_of=timestamp(as_of)
    by_id={s.id:[] for s in registry}
    evidence_ids={}
    for a in assessments:
        if not isinstance(a,dict) or a.get('signal_id') not in by_id: raise ValueError('unknown signal_id')
        # Identical references are idempotent; an evidence identity cannot be rewritten.
        key=a.get('evidence_id')
        if key:
            h=digest(a)
            if key in evidence_ids and evidence_ids[key]!=h: raise ValueError('conflicting evidence_id')
            if key in evidence_ids: continue
            evidence_ids[key]=h
        by_id[a['signal_id']].append(a)
    indexed={a.get('evidence_id'):a for rows in by_id.values() for a in rows if a.get('evidence_id')}
    for a in indexed.values():
        target=a.get('supersedes_evidence_id')
        if target:
            old=indexed.get(target)
            if old is None or old['signal_id']!=a['signal_id'] or target==a['evidence_id']:
                raise ValueError('supersession requires existing same-signal evidence')
            if timestamp(a['available_at'])<timestamp(old['available_at']):
                raise ValueError('supersession cannot predate prior evidence')
            visited={a['evidence_id']}
            while target:
                if target in visited: raise ValueError('cyclic supersession')
                visited.add(target)
                target=indexed[target].get('supersedes_evidence_id')
    signals=[]
    for s in registry:
        evidence=by_id[s.id]
        valid=[]; reasons=[]
        for a in evidence:
            reason=_eligible(a,s,as_of)
            if reason: reasons.append(reason)
            else: valid.append(a)
        # Accepted revocations remain effective after the replacement becomes
        # stale. Otherwise an old, superseded opinion could silently resurrect.
        superseded={a['supersedes_evidence_id'] for a in evidence if a.get('supersedes_evidence_id')
                    and _eligible(a,s,as_of,check_expiry=False) is None}
        valid=[a for a in valid if a.get('evidence_id') not in superseded]
        states={a['status'] for a in valid}
        state=next(iter(states)) if len(states)==1 else 'CONFLICT' if states else 'UNKNOWN'
        reason='conflicting_assessments' if len(states)>1 else '; '.join(sorted(set(reasons))) if not valid else 'reviewed_evidence'
        row=s.to_dict(); row.update(status=state,reason=reason or 'no_evidence',evidence=evidence,
                                    usable_evidence=valid)
        signals.append(row)
    return signals

def evaluate(assessments, as_of, *, catalysts=None, portfolio=None):
    as_of=timestamp(as_of)
    signals=resolve_assessments(assessments,as_of)
    risk=[r for r in signals if r['kind']=='risk']
    opp=[r for r in signals if r['kind']=='opportunity']
    def known(row): return row['status'] in INTENSITY
    coverage=100*sum(known(r) for r in risk)/len(risk)
    # Max within factor avoids additive double counts; same economic event has
    # one stable voting owner globally within each engine (risk and opportunity
    # are separate hypotheses and are never netted).
    owners={}; factors={}
    for module,weight in MODULE_WEIGHTS.items():
        rows=[r for r in risk if r['module']==module]
        candidates=[]
        for row in rows:
            if not known(row) or not INTENSITY[row['status']]: continue
            events=sorted({a['economic_event_id'] for a in row['usable_evidence']})
            for ev in events:
                if ev not in owners: owners[ev]=row['id']
                if owners[ev]==row['id']: candidates.append(INTENSITY[row['status']])
        factors[module]={'name':MODULE_NAMES[module],'weight':weight,
                         'coverage':100*sum(known(r) for r in rows)/len(rows),
                         'intensity':max(candidates,default=0.) if any(known(r) for r in rows) else None}
    blockers=[]
    if coverage<80: blockers.append('risk_coverage_below_80_percent')
    if any(f['intensity'] is None for f in factors.values()): blockers.append('missing_risk_module')
    independent=len(owners)
    raw=sum(f['weight']*(f['intensity'] or 0) for f in factors.values())
    if raw>=45 and independent<2: blockers.append('insufficient_independent_events')
    score=round(raw,4) if not blockers else None
    level='UNKNOWN' if score is None else 'L'+str(sum(score>=t for t in (25,45,60,80)))
    opp_cov=sum(r['weight'] for r in opp if known(r))
    opp_owners={}; opp_points=0.
    for r in opp:
        if not known(r) or not INTENSITY[r['status']]: continue
        events=sorted({a['economic_event_id'] for a in r['usable_evidence']})
        if any(ev not in opp_owners for ev in events):
            opp_points+=r['weight']*INTENSITY[r['status']]
            for ev in events: opp_owners.setdefault(ev,r['id'])
    # Unknown weights stay unallocated; score is on fixed 100 points.
    opportunity={'score':round(opp_points,4) if opp_cov>=80 else None,'coverage':opp_cov,
                 'level':'RESEARCH_ONLY' if opp_cov>=80 else 'UNKNOWN',
                 'blockers':[] if opp_cov>=80 else ['opportunity_coverage_below_80_percent'],
                 'voting_events':opp_owners}
    out={'schema_version':'frie-1.0','as_of':as_of.isoformat(),'model_status':'NOT_VALIDATED',
         'rule_version':'frie-1.0.0','auto_trading':False,'production_scoring':False,
         'risk':{'score':score,'level':level,'coverage':round(coverage,4),'modules':factors,
                 'blockers':blockers,'voting_events':owners},'opportunity':opportunity,
         'signals':signals,'catalysts':catalysts or [],'stress':stress_test(portfolio) if portfolio else None,
         'consumers':{'NQ-Sentinel':'SHARED_RESEARCH_CONTRACT','CRS':'EXTERNAL_CONSUMER_NOT_CONNECTED'},
         'historical_validation':'NOT_RUN_REAL_DATA_NOT_ADMITTED'}
    out['snapshot_hash']=digest(out)
    return out

def stress_test(portfolio):
    """One user-entered semiconductor shock; cash return zero, no advice mapping."""
    p={k:float(portfolio[k]) for k in ('semiconductor_weight','cash_weight','shock','max_loss')}
    if any(not isfinite(v) for v in p.values()): raise ValueError('finite portfolio values required')
    if not 0<=p['semiconductor_weight']<=1 or not 0<=p['cash_weight']<=1 or abs(p['semiconductor_weight']+p['cash_weight']-1)>1e-8:
        raise ValueError('weights must be fractions summing to one')
    if not -1<=p['shock']<=0 or not 0<p['max_loss']<=1: raise ValueError('shock [-1,0], loss budget (0,1] required')
    loss=-p['semiconductor_weight']*p['shock']
    return {**p,'portfolio_loss':loss,'within_budget':loss<=p['max_loss'],
            'conditional_weight_ceiling':min(1.,p['max_loss']/-p['shock']) if p['shock'] else 1.,
            'assumptions':'single semiconductor shock; zero cash return; excludes FX, fees and other holdings',
            'action':'REVIEW_BUDGET_ONLY_NO_TRADE_INSTRUCTION'}
