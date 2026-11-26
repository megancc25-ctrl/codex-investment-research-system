"""Offline factual candidates. None means unknown; numerical cutoffs are research only.

Facts use explicit booleans, comparable disclosures and point-in-time dates.
The outer shared evidence contract supplies quality/rights/time provenance.
"""
from math import isfinite
from statistics import median
from market_risk.frie.engine import timestamp
from .registry import BY_ID

def conjunction(*items):
    if any(x is False for x in items): return False
    return True if all(x is True for x in items) else None

def _flag(f,key):
    value=f.get(key)
    if value is not None and type(value) is not bool: raise ValueError(key+' must be boolean or null')
    return value

def _number(f,key):
    v=f.get(key)
    if v is None:return None
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v):raise ValueError('finite numeric '+key+' required')
    return v

def quarterly_periods(f,as_of):
    periods=set()
    for r in f.get('quarterly_releases',[]):
        if timestamp(r['available_at'])<=as_of:
            p=r['period']
            if not isinstance(p,str) or len(p)!=6 or p[4]!='Q' or p[5] not in '1234' or not p[:4].isdigit():raise ValueError('quarter period YYYYQn required')
            periods.add(p)
    return sorted(periods)

def market_reversal(rows):
    unique={}
    for r in rows:
        key=r.get('economic_event_id')
        if not key: return {'passed':None,'reason':'economic event id missing'}
        if key in unique and unique[key]!=r: return {'passed':None,'reason':'conflicting duplicate event'}
        unique[key]=r
    sample=list(unique.values())[-5:]
    if len(sample)<5 or any(r.get('positive_surprise') is not True or r.get('industry_adjusted') is not True or r.get('matured') is not True or r.get('contaminated') is not False for r in sample):
        return {'passed':None,'reason':'five independent clean matured industry-adjusted positive events required'}
    vals=[_number(r,'excess_return') for r in sample]
    if any(v is None for v in vals):return {'passed':None,'reason':'missing return'}
    return {'passed':sum(v>0 for v in vals)>=3 and median(vals)>0,'median':median(vals),'positive_count':sum(v>0 for v in vals),'economic_event_ids':list(unique)[-5:]}

def market_reversal_from_mrm(reactions,as_of,*,industry_adjusted=False):
    """Reuse FRIE Reaction records; verify sector adjustment from explicit model upstream."""
    rows=[]
    for r in sorted(reactions,key=lambda r:r.event.event_time):
        if r.horizon!=1 or r.event.event_time>as_of:continue
        if r.event.actual_value<=r.event.expected_value:continue
        rows.append({'economic_event_id':r.event.economic_event_id,'positive_surprise':True,
                     'industry_adjusted':industry_adjusted is True,
                     'matured':r.status=='OK' and r.end_time<=as_of,'contaminated':r.contaminated,
                     'excess_return':r.excess_return})
    return market_reversal(rows)

def derive_signal(signal_id,facts,as_of):
    if signal_id not in BY_ID:raise ValueError('unknown SW signal')
    if not isinstance(facts,dict):raise ValueError('facts object required')
    f=facts;as_of=timestamp(as_of);periods=quarterly_periods(f,as_of)
    sustained=True if len(periods)>=2 and _flag(f,'comparable_quarters') is True else None
    leading=industrial=None;hardware=application=None;metrics={}
    if signal_id=='SW01':
        leading=_flag(f,'commercial_breakthrough');industrial=conjunction(leading,_flag(f,'paid_business_model'));application=industrial
    elif signal_id in {'SW02','SW03'}:
        keys=('paid_growth','renewal_improving','roi_positive') if signal_id=='SW02' else ('ai_revenue_growth','unit_economics_improving')
        businesses={}
        for b in f.get('businesses',[]):
            if not b.get('business_id'):raise ValueError('independent business_id required')
            if b['business_id'] in businesses and businesses[b['business_id']]!=b:raise ValueError('conflicting business disclosure')
            businesses[b['business_id']]=b
        flags=[conjunction(*(_flag(b,k) for k in keys)) for b in businesses.values()]
        leading=True if any(v is True for v in flags) else False if flags and all(v is False for v in flags) else None
        industrial=True if sum(v is True for v in flags)>=2 else False if len(flags)>=2 and all(v is not None for v in flags) else None
        application=industrial;metrics['independent_business_ids']=list(businesses)
    elif signal_id=='SW04':
        if _flag(f,'token_only') is not True:
            leading=_flag(f,'actual_workload_growth');industrial=conjunction(leading,_flag(f,'compute_demand_growth'));hardware=conjunction(industrial,_flag(f,'hardware_orders_growth'))
    elif signal_id=='SW05':
        ocf=_number(f,'ocf_growth');fcf=_number(f,'fcf_growth');capex=_number(f,'capex_change')
        leading=ocf>=0 if ocf is not None else None
        industrial=conjunction(leading,fcf>0 if fcf is not None else None)
        hardware=conjunction(industrial,capex>=0 if capex is not None else None)
        sustained=conjunction(sustained,industrial,_flag(f,'roic_improving'))
        metrics['fcf_from_capex_cuts']=fcf is not None and fcf>0 and capex is not None and capex<0
    elif signal_id=='SW06':
        if _flag(f,'circular_financing_only') is True:leading=industrial=hardware=False
        else:
            leading=_flag(f,'independent_external_orders');industrial=conjunction(leading,_flag(f,'order_conversion'),_flag(f,'utilization_improving'));hardware=industrial
    elif signal_id=='SW07':
        values=f.get('spreads_bp',[])
        if f.get('spread_type')=='TECH_MATCHED' and _flag(f,'matched_rating') is True and _flag(f,'matched_maturity') is True and len(values)>=21:
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in values):raise ValueError('finite bp spreads required')
            leading=values[-1]<=values[-21];industrial=values[-1]<values[-21]
            sustained=conjunction(industrial,_flag(f,'sustained_credit_stability'))
    elif signal_id=='SW08':
        reactions=f.get('one_day_reactions',[])
        eligible=True
        for r in reactions:
            try:
                event,expected,end,available=(timestamp(r[k]) for k in ('event_time','expectation_available_at','end_time','available_at'))
                if not expected<=event<end<=available<=as_of:eligible=False
            except (KeyError,ValueError,TypeError,AttributeError):eligible=False
        metrics=market_reversal(reactions) if eligible else {'passed':None,'reason':'MRM first-expectation and matured-return timestamps required'}
        leading=metrics['passed']
        def matured(key):
            try:return timestamp(f[key])<=as_of
            except (KeyError,ValueError,TypeError,AttributeError):return None
        industrial=conjunction(leading,_flag(f,'five_day_improving'),matured('five_day_matured_at'))
        sustained=conjunction(industrial,_flag(f,'twenty_day_improving'),matured('twenty_day_matured_at'),_flag(f,'bad_news_muted'))
    elif signal_id=='SW09':
        prices=f.get('sox_closes',[]);ndx=f.get('ndx_closes',[])
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or v<=0 for v in prices+ndx):raise ValueError('finite positive closes required')
        if len(prices)>=30:leading=all(prices[j]>=min(prices[j-19:j]) for j in range(len(prices)-10,len(prices)))
        if len(prices)>=54:
            above=all(prices[j]>=sum(prices[j-49:j+1])/50 for j in range(len(prices)-5,len(prices)))
            relative=(prices[-1]/ndx[-1]>prices[-21]/ndx[-21]) if len(ndx)==len(prices) and len(ndx)>=21 else None
            industrial=conjunction(leading,above,relative,_flag(f,'breadth_improving'))
            sustained=conjunction(industrial,_flag(f,'medium_term_trend'))
    elif signal_id=='SW10' and f.get('scope')=='SEMICONDUCTOR':
        trend=f.get('eps_revision_trend');leading=trend in {'STABILIZING','UP'} if trend in {'DOWN','STABILIZING','UP'} else None
        industrial=conjunction(leading,_flag(f,'orders_improving'))
        sustained=conjunction(industrial,trend=='UP' if trend is not None else None,_flag(f,'margins_improving'),sustained)
        hardware=conjunction(industrial,_flag(f,'margins_improving'))
    if signal_id not in {'SW05','SW07','SW08','SW09','SW10'}:sustained=conjunction(industrial,sustained)
    status='CONFIRMED' if industrial is True else 'IMPROVING' if leading is True else 'NOT_TRIGGERED' if leading is False else 'UNKNOWN'
    return {'status':status,'confirmations':{'leading':leading,'industrial':industrial,'sustained':sustained},
            'application_support':application,'hardware_support':hardware,'quarterly_periods':periods,
            'reason':'derived from explicit audited facts; candidate not validated','metrics':metrics}
