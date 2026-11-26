"""Three independent questions: growth, hardware transmission, risk admission."""
from copy import deepcopy
from types import SimpleNamespace
from market_risk.frie.engine import resolve_assessments, timestamp, digest, _eligible, INTENSITY
from .registry import REGISTRY
from .signals import derive_signal, conjunction
from .budget import risk_budget

def _or(*values):
    return True if any(v is True for v in values) else False if all(v is False for v in values) else None

def _support(value):return 'SUPPORTED' if value is True else 'NOT_CONFIRMED' if value is False else 'UNKNOWN'

def _risk_record(record,as_of,ttl=2):
    if not isinstance(record,dict):return None
    row=dict(record,status='NOT_TRIGGERED')
    return record if _eligible(row,SimpleNamespace(ttl_days=ttl),as_of) is None else None

def _persistence(evidence,as_of):
    closes=set(); confirmed=set()
    for a in evidence:
        f=a.get('facts',{})
        for close in f.get('exchange_session_closes',[]):
            dt=timestamp(close)
            if dt<=as_of:closes.add(dt)
        for r in f.get('session_confirmations',[]):
            dt=timestamp(r['session_close'])
            if dt<=as_of and r.get('condition_met') is True:confirmed.add(dt)
    latest=sorted(closes)[-5:]
    return len(latest)==5 and all(t in confirmed for t in latest) if closes else None

def evaluate(assessments,as_of,*,catalysts=None,portfolio=None,context=None):
    """Pure offline evaluation. Context carries audited risk records/private config.

    Raw assessment.status never overrides factual signal rules. Facts are frozen
    at their evidence availability, so future releases cannot mature in-place.
    portfolio is rejected: private input is only context.private_config, loaded
    by trusted local CLI/server, never an HTTP account upload.
    """
    if portfolio is not None:raise ValueError('use local private config, not portfolio payload')
    as_of=timestamp(as_of);context=context or {};normalized=[]
    for original in assessments:
        a=deepcopy(original)
        cutoff=min(as_of,timestamp(a['available_at'])) if a.get('available_at') else as_of
        d=derive_signal(a['signal_id'],a.get('facts',{}),cutoff)
        a['status']='CONFLICT' if a.get('status')=='CONFLICT' else d['status']
        a['_derived']=d;normalized.append(a)
    signals=resolve_assessments(normalized,as_of,REGISTRY)
    indexed={s['id']:s for s in signals}
    for s in signals:
        valid=s['usable_evidence'] if s['status'] in INTENSITY else []
        s['confirmations']={k:conjunction(*(a['_derived']['confirmations'][k] for a in valid)) if valid else None for k in ('leading','industrial','sustained')}
        for k in ('hardware_support','application_support'):
            vals=[a['_derived'][k] for a in valid if a['_derived'][k] is not None]
            s[k]=conjunction(*vals) if vals else None
        s['reason']=s['reason']+'; factual '+s['status']
    def flag(sid,stage='industrial'):return indexed[sid]['confirmations'][stage]
    def hw(sid):return indexed[sid]['hardware_support']
    known=[s for s in signals if s['status'] in INTENSITY]
    count_cov=len(known)*10;weight_cov=sum(s['weight'] for s in known)
    # One primary economic event per credited signal; deterministic descending
    # weight prevents source order from giving more points to duplicate news.
    owners={};points=0.
    for s in sorted(known,key=lambda s:(-s['weight'],s['id'])):
        if not INTENSITY[s['status']]:continue
        events=sorted({a['economic_event_id'] for a in s['usable_evidence']})
        new=[e for e in events if e not in owners]
        if new:
            points+=s['weight']*INTENSITY[s['status']]
            # A single primary event is used per credited signal; other linked
            # events reserve references to avoid the same disclosure voting twice.
            for e in events:owners.setdefault(e,s['id'])
    unknown_weight=100-weight_cov
    score=round(points,4) if count_cov>=80 else None
    risk=context.get('risk_context') or {}
    valuation=_risk_record(risk.get('valuation'),as_of,7)
    val=valuation.get('state')=='PASS' if valuation and valuation.get('state') in {'PASS','FAIL'} else None
    market_persistence=_persistence(indexed['SW08']['usable_evidence'],as_of)
    independent=len(set(owners.values()))>=2
    reqs={
      'S1':{'score_45':None if score is None else score>=45,'market_reversal':flag('SW08','leading'),
            'semiconductor_stabilization':flag('SW09','leading'),'commercial_or_credit':_or(flag('SW01','leading'),flag('SW02','leading'),flag('SW07','leading')),
            'independent_evidence':independent,'five_distinct_sessions':market_persistence},
      'S2':{'score_65':None if score is None else score>=65,'paid_demand':flag('SW02'),'inference_to_orders':hw('SW04'),
            'cashflow_stabilization':flag('SW05'),'credit_narrowing':flag('SW07'),'semiconductor_eps_stable':flag('SW10','leading'),
            'market_confirmation':flag('SW09'),'five_distinct_sessions':market_persistence},
      'S3':{'score_80':None if score is None else score>=80,'two_quarters_paid':flag('SW02','sustained'),
            'two_quarters_economics':flag('SW03','sustained'),'external_real_orders':hw('SW06'),
            'semiconductor_earnings_margins':flag('SW10','sustained'),'market_breadth':flag('SW09','sustained'),
            'stable_credit':flag('SW07','sustained')}}
    blockers=[];state='S0';supported='S0'
    if count_cov<80:blockers.append('count_coverage_below_80_percent')
    # Critical credit/reaction observations cannot be replaced by noncritical points.
    if indexed['SW07']['status'] not in INTENSITY or indexed['SW08']['status'] not in INTENSITY:
        blockers.append('critical_credit_or_reaction_unknown')
    if blockers:state='UNKNOWN'
    else:
        for stage,threshold in (('S1',45),('S2',65),('S3',80)):
            if score<threshold:break
            outcome=conjunction(*reqs[stage].values())
            if outcome is True:state=supported=stage
            elif outcome is None:
                state='UNKNOWN';blockers.append(stage+'_mandatory_evidence_unknown');break
            else:break
    app=conjunction(flag('SW02'),flag('SW03'))
    hardware=conjunction(hw('SW04'),hw('SW06'),hw('SW10'))
    try:budget=risk_budget(context.get('private_config'),as_of)
    except (ValueError,TypeError,KeyError,AttributeError):
        budget={'status':'UNKNOWN','reason':'private_config_invalid','auto_trade':False,'actionable_eligibility':False}
    # Compatibility names without changing the mathematical budget's scope.
    budget.setdefault('theoretical_max_weight',budget.get('theoretical_ceiling'))
    budget.setdefault('additional_weight_space',budget.get('new_space'))
    admission_blockers=['model_not_validated']
    crs=_risk_record(risk.get('crs'),as_of);frie=_risk_record(risk.get('frie'),as_of)
    if crs is None or crs.get('state') not in {'NORMAL','ELEVATED','SEVERE'}:admission_blockers.append('crs_unknown')
    elif crs['state']=='SEVERE':admission_blockers.append('crs_severe')
    if frie is None or frie.get('level') not in {'L0','L1','L2','L3','L4'}:admission_blockers.append('frie_unknown')
    elif frie['level'] in {'L3','L4'}:admission_blockers.append('frie_severe')
    if val is not True:admission_blockers.append('valuation_unknown' if val is None else 'valuation_failed')
    if hardware is not True:admission_blockers.append('hardware_transmission_not_confirmed')
    if state not in {'S2','S3'}:admission_blockers.append('growth_stage_not_confirmed')
    if budget['status']!='MATHEMATICAL_ONLY':admission_blockers.append('private_budget_unknown_or_invalid')
    elif budget.get('new_space',0)<=1e-10:admission_blockers.append('no_additional_risk_budget')
    research_candidate=state in {'S2','S3'} and hardware is True
    out={'schema_version':'aswm-1.0','rule_version':'aswm-1.0.0','as_of':as_of.isoformat(),
         'model_status':'NOT_VALIDATED','auto_trading':False,'production_scoring':False,
         'growth':{'state':state,'supported_stage':supported,'score':score,'score_interval':[round(points,4),round(min(100,points+unknown_weight),4)],
                   'count_coverage':count_cov,'weight_coverage':weight_cov,'blockers':blockers,'stage_requirements':reqs,'voting_events':owners},
         'applications':{'status':_support(app),'requirements':{'paid_demand':flag('SW02'),'ai_unit_economics':flag('SW03')}},
         'hardware':{'status':_support(hardware),'requirements':{'actual_inference_to_orders':hw('SW04'),'external_orders':hw('SW06'),'semiconductor_profit':hw('SW10')}},
         'admission':{'state':'BLOCKED','blockers':admission_blockers,'research_candidate':research_candidate,
                      'risk_budget_candidate':research_candidate and len(admission_blockers)==1,'execution_allowed':False,
                      'requirements':{'valuation':val,'industry_transmission':hardware}},
         'budget':budget,'signals':signals,'catalysts':catalysts or [],
         'external_constraints':{'crs':'MISSING' if crs is None else crs.get('state'),'frie':'MISSING' if frie is None else frie.get('level'),
                                 'valuation':'UNKNOWN' if val is None else 'PASS' if val else 'FAIL'},
         'historical_validation':'NOT_RUN_REAL_PIT_DATA_NOT_ADMITTED'}
    material={'state':state,'applications':out['applications']['status'],'hardware':out['hardware']['status'],
              'blockers':admission_blockers,'budget_ceiling':budget.get('theoretical_max_weight'),'new_space':budget.get('additional_weight_space'),
              'signals':[(s['id'],s['status'],s['confirmations'],sorted({a['economic_event_id'] for a in s['usable_evidence']})) for s in signals]}
    out['material_fingerprint']=digest(material);out['snapshot_hash']=digest(out)
    return out
