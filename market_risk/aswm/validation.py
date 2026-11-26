"""Offline fixed-stage ASWM experiments. Never validates production readiness.

Input: dates=[aware ISO close cutoff], prices=[positive close], snapshots=[null
or {as_of:aware ISO<=cutoff,growth_state:str,stage:'S0'..'S3'|null,data:dict}],
source='SYNTHETIC' or identified historical source, admission={status:'ADMITTED',
license_ref:nonempty}. Caller attests completed aligned exchange sessions and
historical availability of all snapshot data. Optional ablations maps names to
caller-recomputed aligned stage arrays; None stays unknown. No fitting occurs.
"""
from math import isfinite,sqrt
from statistics import mean,stdev
from .budget import _time
from market_risk.frie.backtest import (forward_labels,purged_three_way_split,
    simulate_exposure,moving_average_signals,classification_metrics)


def _stage(value):
    if value is None:return None
    if value not in ('S0','S1','S2','S3'):raise ValueError('stage must be S0..S3 or None')
    return int(value[1:])>=2


def _summary(prices,signals,cost,periods,riskfree):
    if any(x is None for x in signals):return None
    path=simulate_exposure(prices,[float(x) for x in signals],cost)
    returns=path['strategy_returns'];wealth=peak=1.;drawdown=0.
    for value in returns:
        wealth*=1+value;peak=max(peak,wealth);drawdown=max(drawdown,1-wealth/peak)
    excess=[r-((1+riskfree)**(1/periods)-1) for r in returns]
    deviation=stdev(excess) if len(excess)>1 else 0
    path.update(max_drawdown=drawdown,sharpe=mean(excess)/deviation*sqrt(periods) if deviation else None,
                periods_per_year=periods,annual_risk_free_rate=riskfree,
                missed_upside=path['opportunity_cost'])
    return path


def run_validation(data,*,upside_threshold,horizons=(20,60,120),purge_horizon=120,
                   ma_window=200,trend_window=60,periods_per_year=252,risk_free_rate=0,
                   cost_bps=0,ablations=None,independent_events=None,rolling_folds=2):
    """Fixed 50/20/15/15 train/validation/test/untouched holdout experiment.

    Labels are max future close/start - 1 over H sessions, not drawdown. Explicit
    upside_threshold is a candidate, not fitted or historically validated. Stage
    >=S2 means research exposure only. Lead time uses independent event timestamps
    and first prior active snapshot (calendar days); no events => None.
    """
    if isinstance(upside_threshold,bool) or not isinstance(upside_threshold,(int,float)) or not isfinite(upside_threshold) or upside_threshold<=0: raise ValueError('positive explicit upside threshold required')
    if isinstance(periods_per_year,bool) or not isinstance(periods_per_year,int) or periods_per_year<1 or not isfinite(risk_free_rate) or risk_free_rate<=-1:raise ValueError('explicit positive periods and finite annual risk-free rate required')
    if data.get('exchange_sessions') is not True:raise ValueError('exchange_sessions true attestation required')
    if isinstance(rolling_folds,bool) or not isinstance(rolling_folds,int) or rolling_folds<2:raise ValueError('at least two rolling folds required')
    admission=data.get('admission') or {}
    if admission.get('status')!='ADMITTED' or not isinstance(admission.get('license_ref'),str) or not admission['license_ref'].strip():raise ValueError('admitted licensed input required')
    if not isinstance(data.get('source'),str) or not data['source'].strip():raise ValueError('source required')
    dates=[_time(x) for x in data.get('dates',[])];prices=data.get('prices',[]);snapshots=data.get('snapshots',[])
    n=len(dates)
    if n<10 or len(prices)!=n or len(snapshots)!=n:raise ValueError('aligned ten or more observations required')
    if any(a>=b for a,b in zip(dates,dates[1:])):raise ValueError('strictly increasing dates required')
    forward_labels(prices,horizons=horizons)  # reuse finite positive prices/horizon validation
    signals=[]
    for date,snapshot in zip(dates,snapshots):
        if snapshot is None:signals.append(None);continue
        if not isinstance(snapshot,dict) or _time(snapshot.get('as_of'))>date:raise ValueError('future or invalid snapshot')
        if _time(snapshot.get('as_of'))!=date and _time(snapshot.get('revalidated_at'))!=date:raise ValueError('snapshot must be fresh or explicitly revalidated at cutoff')
        native=snapshot.get('growth')
        known=native.get('state') if isinstance(native,dict) else snapshot.get('growth_state')
        stage=snapshot.get('stage')
        if known in ('S0','S1','S2','S3'):
            if stage is not None and stage!=known:raise ValueError('stage contradicts native growth state')
            stage=known
        if isinstance(native,dict) and native.get('blockers')!=[]:known='UNKNOWN'
        if not known or str(known).upper() in ('UNKNOWN','BLOCKED','CONFLICT') or not (isinstance(snapshot.get('data'),dict) or isinstance(native,dict) and isinstance(snapshot.get('signals'),list)):signals.append(None)
        else:signals.append(_stage(stage))
    train_end=int(n*.5);val_end=int(n*.7);holdout_start=int(n*.85)
    train,val,test=purged_three_way_split(holdout_start,train_end,val_end,purge_horizon)
    test=[x for x in test if x+purge_horizon<holdout_start]
    partitions=dict(train=train,validation=val,test=test,holdout=list(range(holdout_start,n)))
    boundaries=dict(train=train_end,validation=val_end,test=holdout_start,holdout=n)
    def metrics(sequence,parts=None,limits=None):
        result=[]
        for name,indices in (parts or partitions).items():
            for h in horizons:
                eligible=[j for j in indices if j+h<(limits or boundaries)[name]]
                usable=[j for j in eligible if sequence[j] is not None]
                truth=[max(prices[j+1:j+h+1])/prices[j]-1>=upside_threshold for j in usable]
                result.append(dict(partition=name,horizon=h,eligible=len(eligible),evaluated=len(usable),
                                   missing=len(eligible)-len(usable),**classification_metrics(truth,[sequence[j] for j in usable])))
        return result
    folds=[]
    # Expand train; each fold has fresh contiguous validation/test segments.
    # Cutoffs are deterministic and never depend on returns or measured scores.
    segment=max(1,holdout_start//(rolling_folds+3))
    for fold_index in range(rolling_folds):
        a=holdout_start-(rolling_folds-fold_index+1)*segment
        b=a+segment;c=b+segment
        purge=max(purge_horizon,max(horizons))
        ft,fv,fx=purged_three_way_split(c,a,b,purge)
        fx=[j for j in fx if j+purge<c]
        folds.append(dict(fold=fold_index,cutoffs=dict(train_end=a,validation_end=b,test_end=c,holdout_start=holdout_start),
                          partitions=dict(train=ft,validation=fv,test=fx),
                          metrics=metrics(signals,dict(train=ft,validation=fv,test=fx),dict(train=a,validation=b,test=c)),
                          insufficient_complete_windows=not all((ft,fv,fx))))
    strategies={'aswm':_summary(prices,signals,cost_bps,periods_per_year,risk_free_rate),
                'buy_hold':_summary(prices,[True]*n,cost_bps,periods_per_year,risk_free_rate),
                'sma':_summary(prices,moving_average_signals(prices,ma_window),cost_bps,periods_per_year,risk_free_rate),
                'trend':_summary(prices,moving_average_signals(prices,trend_window),cost_bps,periods_per_year,risk_free_rate)}
    omitted={}
    for name,stages in (ablations or {}).items():
        if len(stages)!=n:raise ValueError('aligned caller-recomputed ablation stages required')
        seq=[_stage(s) if original is not None else None for s,original in zip(stages,signals)]
        omitted[name]=dict(metrics=metrics(seq),strategy=_summary(prices,seq,cost_bps,periods_per_year,risk_free_rate))
    leads=[]
    for event in independent_events or []:
        at=_time(event)
        prior=[d for d,s in zip(dates,signals) if s is True and d<=at]
        if prior:leads.append((at-prior[0]).total_seconds()/86400)
    return dict(status='synthetic_only' if data['source'].upper()=='SYNTHETIC' else 'offline_research_only',
                model_status='NOT_VALIDATED',validated=False,auto_trade=False,execution_eligible=False,
                partitions=partitions,walk_forward_folds=folds,metrics=metrics(signals),strategies=strategies,ablations=omitted,
                missing_signals=sum(x is None for x in signals),upside_threshold=upside_threshold,
                lead_time_calendar_days=mean(leads) if leads else None,
                holdout_policy='untouched by parameter selection; all candidate rules fixed before report',
                partition_policy='multiple expanding train folds; horizon-purged; no model fitting',
                strategy_scope='full supplied path; per-partition label metrics separate',
                assumptions={'annual_risk_free_rate':risk_free_rate,'periods_per_year':periods_per_year,
                             'execution':'next-session close; costs on turnover','no_fitting':True})
