"""Audited envelope adapter for six modules; never fetches a provider endpoint."""
from types import SimpleNamespace
from .engine import _eligible,timestamp,digest
from .research_modules import rates_regression,funding_pressure,circular_financing,leverage_cycle,commercialization,reaction_paths,cashflow_panel
from market_risk.aswm.signals import market_reversal

MODULES={'market_reaction':('F01','SW08'),'rates':('F05',),'funding':('F06','F07','SW05'),
         'circular_financing':('F09','SW06'),'leverage':('F03','F04','F14','F15'),'commercialization':('F11','SW01','SW02','SW03','SW04','SW05','SW06')}
TTL={'market_reaction':30,'rates':7,'funding':120,'circular_financing':120,'leverage':45,'commercialization':120}

def _independent(evidence,outer,as_of):
    if not isinstance(evidence,dict) or evidence.get('economic_event_id')==outer.get('economic_event_id'):return None
    if evidence.get('status')=='NOT_TRIGGERED':return False
    if evidence.get('status')!='CONFIRMED' or evidence.get('adverse') is not True:return None
    r=dict(evidence,status='CONFIRMED')
    return True if _eligible(r,SimpleNamespace(ttl_days=7),as_of) is None else None

def evaluate_modules(body,as_of):
    as_of=timestamp(as_of);result={};events={}
    for name,ids in MODULES.items():
        envelope=(body.get('modules') or {}).get(name)
        if not envelope:result[name]={'status':'UNKNOWN','quality':'MISSING','signal_ids':ids,'reason':'missing module envelope'};continue
        e=dict(envelope,status='CONFIRMED')
        reason=_eligible(e,SimpleNamespace(ttl_days=TTL[name]),as_of)
        if reason:
            quality='RESTRICTED' if reason=='data_not_admitted' else 'STALE' if reason=='expired' else e.get('quality','MISSING')
            if quality=='VERIFIED':quality='PENDING_RELEASE' if reason=='not_available_as_of' else 'MISSING'
            result[name]={'status':'UNKNOWN','quality':quality,'signal_ids':ids,'reason':reason,'usable':False};continue
        f=e.get('facts',{});values={}
        try:
            if name=='rates':
                for asset,a in f.get('assets',{}).items():
                    dates=[timestamp(t) for t in a.get('session_closes',[])];available=[timestamp(t) for t in a.get('available_at_per_session',[])]
                    if not dates or len(dates)!=len(a.get('returns',[])) or len(available)!=len(dates) or any(x>as_of or y>as_of or y<x for x,y in zip(dates,available)) or any(x>=y for x,y in zip(dates,dates[1:])):raise ValueError('rates require aligned completed PIT session/availability arrays')
                    if a.get('control_excludes_target') is not True:raise ValueError('explicit nonoverlapping control required')
                    for tenor,changes in a.get('rate_changes_bp',{}).items():
                        if tenor not in {'UST2Y','UST10Y','TIPS10Y'}:raise ValueError('unknown yield series')
                        values[asset+':'+tenor]=rates_regression(a['returns'],changes,a['market_returns'],rate_unit=a['unit'],target=asset,market=a['market_id'],independent_risk=_independent(f.get('financing_or_valuation_evidence'),e,as_of))
                computed=any(any('sample_count' in w for w in r['windows'].values()) for r in values.values())
                values={'status':'RESEARCH_COMPUTED' if computed else 'UNKNOWN','regressions':values}
            elif name=='market_reaction':
                reversal=market_reversal(f.get('one_day_reactions',[]))
                rows=f.get('one_day_reactions',[]);last=list({r['economic_event_id']:r for r in rows}.values())[-5:]
                clean=reversal.get('passed') is not None
                from statistics import median
                fatigued=(sum(r['excess_return']<=0 for r in last)>=3 and median(r['excess_return'] for r in last)<=0) if clean else None
                values={'status':'UNKNOWN' if fatigued is None else 'TRIGGERED' if fatigued else 'NOT_TRIGGERED','growth_reversal':reversal,
                        'fatigue':fatigued,'five_day_and_twenty_day':'matured windows remain separate; use MRM event reports',
                        'repair_speed':reaction_paths(f.get('event_paths',[]),as_of,negative_history=f.get('negative_reaction_history',[]))}
            elif name=='funding':
                values=funding_pressure(f.get('vendors'),f.get('coverage_deteriorating',{}),independent_financing=_independent(f.get('financing_evidence'),e,as_of))
                values['financial_panels']={ticker:cashflow_panel(panel,as_of) for ticker,panel in f.get('quarterly_panels',{}).items()}
            elif name=='circular_financing':values=circular_financing(f.get('relationships',[]),f.get('receivables_growth'),f.get('revenue_growth'),_independent(f.get('collection_or_financing_evidence'),e,as_of))
            elif name=='leverage':values=leverage_cycle(f.get('volatility_percentile'),f.get('leverage_percentile'),**{k:f.get(k) for k in ('volatility_jump','liquidity_worse','breadth_worse','forced_selling')})
            else:values=commercialization(f.get('businesses',[]))
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            result[name]={'status':'UNKNOWN','quality':'CONFLICT','signal_ids':ids,'reason':'invalid_module_input_'+type(error).__name__,'usable':False}
            continue
        ev=e['economic_event_id'];owner=events.setdefault(ev,name)
        result[name]={**values,'signal_ids':ids,'quality':'VERIFIED','source_url':e['source_url'],'observed_at':e['observed_at'],
                      'available_at':e['available_at'],'evidence_id':e['evidence_id'],'economic_event_id':ev,
                      'primary_event_owner':owner,'independent_vote':owner==name,'counter_evidence':e.get('counter_evidence'),
                      'usable':values.get('status',values.get('risk_status',values.get('accumulation','UNKNOWN')))!='UNKNOWN'}
    out={'schema_version':'unified-research-1.0','as_of':as_of.isoformat(),'model_status':'NOT_VALIDATED','auto_trading':False,
         'production_scoring':False,'modules':result,'usable_modules':sum(r.get('usable',False) for r in result.values()),
         'total_modules':6,'events':events,'crs_gates':{'G1':'NO_GO','G2':'NOT_STARTED','G3':'NOT_STARTED'},'ust':'REAL_DATA_NOT_AUTHORIZED'}
    out['snapshot_hash']=digest(out);return out
