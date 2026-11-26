"""Six shared offline research modules. No fetching, rights grants or production score.

Numerical helpers consume already-aligned completed inputs. The pipeline below
checks their common point-in-time and license envelope before calling them.
"""
from contextlib import closing
from math import isfinite,sqrt
from statistics import median
from pathlib import Path
import json,sqlite3
from .engine import timestamp,digest
from .indicators import f06_fcf_declines,f04_volatility_leverage

def reaction_paths(paths,as_of,*,negative_history=(),minimum_history=20):
    """Completed cumulative abnormal-return paths, with right-censored recovery.

    Each path has event_id, event_time, direction POSITIVE/NEGATIVE,
    session_closes, available_at_per_session, cumulative_excess_returns and
    contaminated. No recovery time is manufactured for an unfinished path.
    """
    as_of=timestamp(as_of);out=[];seen=set()
    for p in sorted(paths,key=lambda p:timestamp(p['event_time'])):
        identity=p.get('economic_event_id') or p['event_id']
        if identity in seen:continue
        seen.add(identity)
        event=timestamp(p['event_time']);closes=[timestamp(x) for x in p['session_closes']];avail=[timestamp(x) for x in p['available_at_per_session']];values=p['cumulative_excess_returns']
        if len(closes)!=len(values) or len(closes)!=len(avail) or any(a>=b for a,b in zip(closes,closes[1:])):raise ValueError('aligned increasing event path required')
        _finite(values)
        if p.get('contaminated') is not False or event>as_of:
            out.append({'event_id':p['event_id'],'status':'UNKNOWN','reason':'future or contaminated event'});continue
        completed=[v for c,a,v in zip(closes,avail,values) if event<c<=a<=as_of]
        if not completed:out.append({'event_id':p['event_id'],'status':'UNKNOWN','reason':'unmatured path'});continue
        direction=p['direction'];duration=None
        if direction=='POSITIVE':duration=next((i for i,v in enumerate(completed,1) if v<=0),None)
        elif direction=='NEGATIVE':duration=next((i for i,v in enumerate(completed,1) if v>=0),None)
        else:raise ValueError('event direction must be independent POSITIVE/NEGATIVE classification')
        historical=[h['excess_return'] for h in negative_history if timestamp(h['available_at'])<event and timestamp(h['event_time'])<event]
        _finite(historical)
        percentile=100*sum(v<=completed[0] for v in historical)/len(historical) if direction=='NEGATIVE' and len(historical)>=minimum_history else None
        out.append({'event_id':p['event_id'],'status':'RESEARCH_COMPUTED','direction':direction,'duration_sessions':duration,
                    'right_censored':duration is None,'completed_sessions':len(completed),'negative_reaction_percentile':percentile,'history_count':len(historical)})
    return {'status':'RESEARCH_COMPUTED' if out else 'UNKNOWN','paths':out,'model_status':'NOT_VALIDATED'}

def cashflow_panel(quarters,as_of):
    """Comparable cash-flow quarters and TTM; cash stocks are not cash flows."""
    as_of=timestamp(as_of);rows=[];periods=set();scope=None
    for q in sorted(quarters,key=lambda q:timestamp(q['available_at'])):
        if timestamp(q['available_at'])>as_of:continue
        if q['period'] in periods:raise ValueError('explicit revision selection required for repeated quarter')
        periods.add(q['period'])
        identity=(q.get('currency'),q.get('unit'),q.get('accounting_scope'))
        if None in identity:raise ValueError('currency, amount unit and accounting scope required')
        if scope is not None and scope!=identity:raise ValueError('incomparable financial quarters')
        scope=identity
        def v(k):
            x=q.get(k)
            if x is not None:_finite([x])
            return x
        ocf,capex=v('ocf'),v('cash_capex');cash,short,debt=v('cash'),v('short_term_investments'),v('total_debt')
        if capex is not None and capex<0:raise ValueError('cash CapEx positive outflow convention required')
        interest,ebit=v('interest_expense'),v('ebit')
        stock=cash+short if cash is not None and short is not None else None
        rows.append({'period':q['period'],'available_at':q['available_at'],'ocf':ocf,'cash_capex':capex,'fcf':ocf-capex if ocf is not None and capex is not None else None,
                     'capex_ocf':capex/ocf if capex is not None and ocf is not None and ocf>0 else None,
                     'cash_and_short_term_stock':stock,'net_debt':debt-stock if debt is not None and stock is not None else None,
                     'interest_coverage':ebit/interest if ebit is not None and interest is not None and interest>0 else None,
                     'finance_leases':v('finance_leases'),'capital_commitments':v('capital_commitments'),
                     'maturing_debt':v('maturing_debt'),'refinancing_cost_bp':v('refinancing_cost_bp')})
    ttm=None
    if len(rows)>=4:
        last=sorted(rows,key=lambda r:r['period'])[-4:]
        def quarter_index(r):
            p=r['period']
            if len(p)!=6 or p[4]!='Q' or p[5] not in '1234':raise ValueError('explicit fiscal YYYYQn quarters required')
            return int(p[:4])*4+int(p[5])
        indices=[quarter_index(r) for r in last]
        if all(b-a==1 for a,b in zip(indices,indices[1:])) and all(r[k] is not None for r in last for k in ('ocf','cash_capex')):
            ocf=sum(r['ocf'] for r in last);capex=sum(r['cash_capex'] for r in last)
            ttm={'ocf':ocf,'cash_capex':capex,'fcf':ocf-capex,'capex_ocf':capex/ocf if ocf>0 else None}
    return {'quarters':rows,'ttm':ttm,'status':'RESEARCH_COMPUTED' if rows else 'UNKNOWN','cash_exhaustion_claim':None,'model_status':'NOT_VALIDATED'}

def _finite(values):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in values):raise ValueError('finite numerical inputs required')

def _tri(*values):
    return False if False in values else True if all(v is True for v in values) else None

def _state(value):return 'UNKNOWN' if value is None else 'TRIGGERED' if value else 'NOT_TRIGGERED'

def rates_regression(returns,rate_changes,benchmark_returns,*,rate_unit,target,market,independent_risk=None):
    """OLS y=a+b*delta_yield_bp+c*nonoverlapping_market_return, windows60/120.

    CI uses a disclosed normal approximation, not a small-sample t claim. Empirical
    beta percentile requires >=120 past fitted windows, excluding the current fit.
    """
    if rate_unit!='bp' or not target or not market or target==market:raise ValueError('bp changes and distinct nonoverlapping control benchmark required')
    if len(returns)!=len(rate_changes) or len(returns)!=len(benchmark_returns):raise ValueError('aligned sessions required')
    _finite(list(returns)+list(rate_changes)+list(benchmark_returns))
    def fit(y,x,m):
        n=len(y);ym=sum(y)/n;xm=sum(x)/n;mm=sum(m)/n
        xx=sum((v-xm)**2 for v in x);zz=sum((v-mm)**2 for v in m);xz=sum((a-xm)*(b-mm) for a,b in zip(x,m))
        xy=sum((a-xm)*(b-ym) for a,b in zip(x,y));zy=sum((a-mm)*(b-ym) for a,b in zip(m,y))
        det=xx*zz-xz*xz
        if det<=1e-15:return None
        beta=(xy*zz-zy*xz)/det;control=(zy*xx-xy*xz)/det;intercept=ym-beta*xm-control*mm
        sse=sum((a-intercept-beta*b-control*c)**2 for a,b,c in zip(y,x,m));se=sqrt(max(0,sse/(n-3)*zz/det))
        return {'beta_per_10bp':beta*10,'ci95_per_10bp':[(beta-1.96*se)*10,(beta+1.96*se)*10],
                'sample_count':n,'market_beta':control,'confidence_method':'normal approximation; descriptive, noncausal'}
    out={}
    for window in (60,120):
        fits=[fit(returns[j-window:j],rate_changes[j-window:j],benchmark_returns[j-window:j]) for j in range(window,len(returns)+1)]
        if not fits or fits[-1] is None:out[str(window)]={'status':'UNKNOWN','reason':'insufficient sessions or singular design'};continue
        last=fits[-1];past=[r['beta_per_10bp'] for r in fits[:-1] if r is not None]
        percentile=100*sum(v<=last['beta_per_10bp'] for v in past)/len(past) if len(past)>=120 else None
        warning=_tri(last['beta_per_10bp']<0,percentile<=10 if percentile is not None else None,independent_risk)
        out[str(window)]=dict(last,status=_state(warning),historical_percentile=percentile,historical_windows=len(past),
                              percentile_rule='past completed fits only, <= ties; >=120 required')
    return {'windows':out,'model_status':'NOT_VALIDATED','causal_claim':False,'target':target,'market_control':market}

def funding_pressure(vendors,coverage_deteriorating,*,independent_financing=None):
    fcf=f06_fcf_declines(vendors)
    qualified=[]
    if vendors:
        for name,v in vendors.items():
            if v and len(v.get('current',[]))==2 and len(v.get('prior_year',[]))==2:
                diff=[(a-b)-(c-d) for (a,b),(c,d) in zip(v['current'],v['prior_year'])]
                if all(x<0 for x in diff) and coverage_deteriorating.get(name) is True:qualified.append(name)
    adverse=len(qualified)>=2 if len(vendors or {})>=2 and all(coverage_deteriorating.get(k) is not None for k in vendors) else None
    return {'status':_state(_tri(fcf['status']=='TRIGGERED' if fcf['status']!='UNKNOWN' else None,adverse,independent_financing)),
            'qualified_vendors':qualified,'fcf':fcf,'cash_exhaustion_claim':None,'model_status':'NOT_VALIDATED',
            'note':'cash FCF = OCF minus cash CapEx; negative FCF does not establish insolvency or missing cash'}

def circular_financing(relationships,receivables_growth,revenue_growth,collection_or_financing_worse):
    """Two comparable periods and independent cash-collection/financing evidence.

    Cross-investments/cycles are descriptive exposure, never a fraud conclusion.
    """
    risk=None
    if receivables_growth is not None and revenue_growth is not None:
        if len(receivables_growth)!=len(revenue_growth):raise ValueError('comparable periods required')
        _finite(list(receivables_growth)+list(revenue_growth))
        if len(revenue_growth)>=2:risk=_tri(all(a>b for a,b in zip(receivables_growth[-2:],revenue_growth[-2:])),collection_or_financing_worse)
    nodes={};exposure={};unique={}
    for r in relationships:
        key=r.get('relationship_id') or digest({k:r.get(k) for k in ('economic_event_id','from_company','to_company','kind','currency','payment_type')})
        if key in unique and unique[key]!=r:raise ValueError('conflicting relationship identity')
        unique[key]=r
    for r in unique.values():
        nodes.setdefault(r['from_company'],set()).add(r['to_company'])
        if r.get('amount') is not None:
            _finite([r['amount']])
            if r['amount']<0:raise ValueError('nonnegative exposure required')
            if not r.get('currency') or r.get('payment_type') not in {'PAID','COMMITMENT'}:raise ValueError('currency and paid/commitment distinction required')
            key=r['currency']+':'+r['payment_type'];exposure[key]=exposure.get(key,0)+r['amount']
    def cycle(start,node,visited):
        return any(n==start or n not in visited and cycle(start,n,visited|{n}) for n in nodes.get(node,()))
    return {'status':_state(risk),'cycle_detected':any(cycle(n,n,{n}) for n in nodes),'exposure_by_currency_and_payment_type':exposure,
            'fraud_claim':None,'model_status':'NOT_VALIDATED','missing_disclosures_mean':'UNKNOWN, never zero exposure'}

class RelationshipStore:
    """Immutable directed SEC/IR contract/investment/guarantee references."""
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS frie_relationships(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            for action in ('UPDATE','DELETE'):db.execute(f"CREATE TRIGGER IF NOT EXISTS relationships_no_{action} BEFORE {action} ON frie_relationships BEGIN SELECT RAISE(ABORT,'immutable relationship'); END")
    def append(self,r):
        for k in ('relationship_id','from_company','to_company','kind','economic_event_id','available_at','source_url','license_ref'):
            if not r.get(k):raise ValueError('missing relationship '+k)
        if r.get('license_status')!='ADMITTED' or r.get('quality')!='VERIFIED':raise ValueError('unadmitted relationship')
        timestamp(r['available_at']);circular_financing([r],None,None,None)
        payload=json.dumps(r,sort_keys=True,allow_nan=False)
        with closing(sqlite3.connect(self.path)) as db,db:
            previous=db.execute('SELECT payload FROM frie_relationships WHERE id=?',(r['relationship_id'],)).fetchone()
            if previous and previous[0]!=payload:raise ValueError('immutable relationship conflict')
            db.execute('INSERT OR IGNORE INTO frie_relationships VALUES(?,?)',(r['relationship_id'],payload))
    def records(self,as_of):
        with closing(sqlite3.connect(self.path)) as db:
            rows=[json.loads(x[0]) for x in db.execute('SELECT payload FROM frie_relationships ORDER BY id')]
            return [r for r in rows if timestamp(r['available_at'])<=timestamp(as_of)]

def leverage_cycle(volatility_percentile,leverage_percentile,*,volatility_jump=None,liquidity_worse=None,breadth_worse=None,forced_selling=None):
    return {'accumulation':f04_volatility_leverage(volatility_percentile,leverage_percentile)['status'],
            'explosion':_state(_tri(volatility_jump,liquidity_worse,breadth_worse,forced_selling)),
            'otc_net_leverage':'UNKNOWN','options_volume_is_net_leverage':False,'model_status':'NOT_VALIDATED'}

def commercialization(businesses):
    """Same business facts can support risk and opportunity without score netting."""
    unique={b['business_id']:b for b in businesses};risk=[];growth=[]
    for b in unique.values():
        keys=('capex_rising','incremental_return_worse','real_paid_demand_worse')
        risk.append(_tri(*(b.get(k) for k in keys)))
        growth.append(_tri(*(b.get(k) for k in ('paid_demand_growth','roi_improving','unit_economics_improving'))))
    def at_least_two(values):
        return True if sum(v is True for v in values)>=2 else False if len(values)>=2 and all(type(v) is bool for v in values) else None
    return {'risk_status':_state(at_least_two(risk)),'growth_status':_state(at_least_two(growth)),
            'independent_businesses':list(unique),'model_status':'NOT_VALIDATED','token_volume_sufficient':False}

def lcim_ratios(debt,gdp,m2,market_cap,*,unit,denominator_unit,history=None):
    """LCIM ratios: named same-scale currency amounts; GDP is nominal annual SAAR.

    This helper does not treat GDP quarterly change as annual dollar level.
    Caller supplies PIT-compatible monthly snapshots and denominator vintage.
    """
    if unit!=denominator_unit or unit not in {'units','millions','billions'}:raise ValueError('matching currency scales required')
    values=[v for v in (debt,gdp,m2,market_cap) if v is not None];_finite(values)
    if debt is not None and debt<0:raise ValueError('nonnegative margin debt required')
    def ratio(d):return debt/d if debt is not None and d is not None and d>0 else None
    past=history or [];_finite(past)
    percentile=100*sum(x<=debt for x in past)/len(past) if debt is not None and len(past)>=120 else None
    return {'debt_gdp':ratio(gdp),'debt_m2':ratio(m2),'debt_market_cap':ratio(market_cap),
            'historical_percentile':percentile,'history_months':len(past),'model_status':'NOT_VALIDATED'}
