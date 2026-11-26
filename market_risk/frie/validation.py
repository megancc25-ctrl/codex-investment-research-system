"""Offline research validation runner; no fetching, fitting, or trading.

Input schema: {dates: [aware ISO close-cutoff timestamps], prices: [positive
closes], exchange_sessions: true (caller attestation of complete exchange
sessions), source: 'SYNTHETIC' or an identified historical source,
admission: {status: 'ADMITTED', license_ref: nonempty string}, snapshots:
[null or {as_of: aware ISO <= corresponding cutoff, risk: {score: null or
0..100, blockers: [], modules: {name: {weight: 0..100,intensity: 0..1|null}}}}]}.

Admission is caller supplied provenance, not independently verified by this
runner. Snapshots must already carry the engine's historical availability and
evidence gates. Null snapshots/scores and nonempty blockers remain unknown.
Report contains integer index partitions, all 27 horizon/threshold/partition
metric rows, coverage, cost-aware research paths, module-omission experiments,
and historical coverage inventory. NOT_VALIDATED is unconditional.
"""
from datetime import datetime, timezone
from math import isfinite
from .backtest import (forward_labels,purged_three_way_split,classification_metrics,
                       simulate_exposure,moving_average_signals,historical_coverage)


def _time(value):
    if not isinstance(value,str): raise ValueError('ISO timestamp string required')
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset() is None: raise ValueError('aware timestamps required')
    return result.astimezone(timezone.utc)


def _finite(value,low,high,name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not low<=value<=high:
        raise ValueError('invalid '+name)
    return float(value)


def _metric_rows(labels,scores,partitions,boundaries):
    rows=[]
    for name,indices in partitions.items():
        index_set=set(indices)
        for horizon in (20,60,120):
            eligible=[label for label in labels if label.horizon==horizon and label.index in index_set
                      and label.index+horizon<boundaries[name]]
            usable=[label for label in eligible if scores[label.index] is not None]
            for threshold in (.1,.2,.3):
                metrics=classification_metrics([x.events[threshold] for x in usable],
                                               [scores[x.index]>=45 for x in usable])
                rows.append(dict(partition=name,horizon=horizon,drawdown_threshold=threshold,
                                 eligible_labels=len(eligible),evaluated_labels=len(usable),
                                 missing_scores=len(eligible)-len(usable),**metrics))
    return rows


def run_validation(data, *, purge_horizon=120, ma_window=200, trend_window=60, cost_bps=0):
    """60/20/20 chronological experiment, with no estimated parameters.

    Every metric additionally enforces its actual horizon at partition boundaries,
    even if a smaller purge is explicitly chosen. Score >=45 is fixed research
    classification. Exposure is zero on that alert, one otherwise; execution is
    next-session close. This mapping is a research experiment only. Unknown FRIE
    scores omit its whole strategy path rather than manufacturing positions.
    Baseline windows use only completed observations and initially hold exposure
    one until sufficient observations (see moving_average_signals).
    """
    if not isinstance(data,dict): raise ValueError('plain input mapping required')
    admission=data.get('admission') or {}
    if admission.get('status')!='ADMITTED' or not isinstance(admission.get('license_ref'),str) or not admission['license_ref'].strip():
        raise ValueError('input data must be explicitly admitted with license_ref')
    if data.get('exchange_sessions') is not True: raise ValueError('explicit complete exchange-session attestation required')
    source=data.get('source')
    if not isinstance(source,str) or not source.strip(): raise ValueError('identified source required')
    dates=[_time(x) for x in data.get('dates',[])]
    prices=data.get('prices',[]); snapshots=data.get('snapshots',[])
    n=len(dates)
    if n<5 or len(prices)!=n or len(snapshots)!=n: raise ValueError('at least five aligned dates/prices/snapshots required')
    if any(a>=b for a,b in zip(dates,dates[1:])): raise ValueError('strictly increasing close timestamps required')
    # forward_labels validates finite positive prices before any scoring.
    labels=forward_labels(prices)
    scores=[]; modules=[]
    for cutoff,snapshot in zip(dates,snapshots):
        if snapshot is None:
            scores.append(None); modules.append({}); continue
        if not isinstance(snapshot,dict) or _time(snapshot.get('as_of'))>cutoff:
            raise ValueError('snapshot must be available at or before close cutoff')
        risk=snapshot.get('risk')
        if not isinstance(risk,dict): raise ValueError('risk mapping required')
        score=risk.get('score')
        if score is not None: score=_finite(score,0,100,'risk score')
        # Engine blockers cannot be bypassed by a numeric score in a supplied row.
        if risk.get('blockers') != []: score=None
        factor=risk.get('modules',{})
        if not isinstance(factor,dict): raise ValueError('risk modules mapping required')
        for item in factor.values():
            if not isinstance(item,dict): raise ValueError('module mapping required')
            _finite(item.get('weight'),0,100,'module weight')
            if item.get('intensity') is not None: _finite(item['intensity'],0,1,'module intensity')
        scores.append(score); modules.append(factor)
    train_end=int(n*.6); validation_end=int(n*.8)
    train,validation,test=purged_three_way_split(n,train_end,validation_end,purge_horizon)
    partitions=dict(train=train,validation=validation,test=test)
    boundaries=dict(train=train_end,validation=validation_end,test=n)
    metrics=_metric_rows(labels,scores,partitions,boundaries)
    strategies={
        'moving_average':simulate_exposure(prices,moving_average_signals(prices,ma_window),cost_bps),
        'trend':simulate_exposure(prices,moving_average_signals(prices,trend_window),cost_bps),
        'frie':simulate_exposure(prices,[0.0 if s>=45 else 1.0 for s in scores],cost_bps) if all(s is not None for s in scores) else None}
    ablations={}
    for name in sorted({k for row in modules for k in row}):
        omitted=[]
        for score,row in zip(scores,modules):
            item=row.get(name)
            # Preserve source score gates and missing module gates, fixed weights.
            if score is None or item is None or any(v.get('intensity') is None for v in row.values()):
                omitted.append(None)
            else:
                omitted.append(max(0.0,score-item['weight']*item['intensity']))
        ablations['without_'+name]=dict(metrics=_metric_rows(labels,omitted,partitions,boundaries),
                                       available_scores=sum(x is not None for x in omitted),
                                       method='subtract module weighted intensity; no redistribution; source gates retained')
    return dict(status='synthetic_only' if source.upper()=='SYNTHETIC' else 'offline_research_only',
                source=source,model_status='NOT_VALIDATED',empirical_validation=False,auto_trade=False,
                score_threshold=45,partitions=partitions,metrics=metrics,strategies=strategies,
                strategy_scope='full supplied path; fixed rules, no fitting; partitioned metrics separately reported',
                coverage=dict(observations=n,available_scores=sum(x is not None for x in scores),
                              missing_scores=sum(x is None for x in scores)),
                ablations=ablations,historical_coverage=historical_coverage(dates),
                admission=dict(admission),purge_horizon=purge_horizon,
                limitations=['caller attests session completeness and licenses',
                             'overlapping forward labels are dependent',
                             'lead time unavailable without independent event dating',
                             'research exposure mapping is not production authorization'])
