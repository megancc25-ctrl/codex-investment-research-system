"""Offline evaluation only; no fitted model, market claims, or trading integration.

A horizon H label uses closes t through t+H inclusive (H future sessions).
Maximum drawdown is the largest peak-to-subsequent-trough decline on that path.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Callable, Mapping, Sequence


def _prices(prices):
    values = [float(x) for x in prices]
    if any(not isfinite(x) or x <= 0 for x in values):
        raise ValueError('prices must be finite and positive')
    return values


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')


@dataclass(frozen=True)
class ForwardLabel:
    index: int
    horizon: int
    drawdown: float
    events: Mapping[float, bool]


def forward_labels(prices, horizons=(20, 60, 120), thresholds=(.1, .2, .3)):
    values = _prices(prices)
    if any(not isinstance(h, int) or isinstance(h, bool) or h <= 0 for h in horizons):
        raise ValueError('horizons must be positive integers')
    if any(not isfinite(t) or not 0 < t < 1 for t in thresholds):
        raise ValueError('thresholds must be between zero and one')
    labels = []
    for horizon in horizons:
        for index in range(len(values) - horizon):
            peak = values[index]
            drawdown = 0.0
            for price in values[index:index+horizon+1]:
                peak = max(peak, price)
                drawdown = max(drawdown, 1-price/peak)
            labels.append(ForwardLabel(index, horizon, drawdown,
                                       {t: drawdown + 1e-12 >= t for t in thresholds}))
    return labels


def purged_split(n_samples, test_start, horizon):
    """Training label endpoints must be strictly before the first test observation.

    Caller must fit transformations/models on returned training indices only.
    """
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in (n_samples,test_start,horizon)):
        raise ValueError('integer split parameters required')
    if not 0 <= test_start <= n_samples or horizon < 1:
        raise ValueError('invalid split')
    return list(range(max(0,test_start-horizon))), list(range(test_start,n_samples))


def classification_metrics(actual, predicted, lead_times=()):
    """Lead times are caller supplied session gaps to an independently dated event.

    Empty denominators and absent lead observations are None, never zero.
    """
    if len(actual) != len(predicted):
        raise ValueError('aligned labels required')
    if any(type(x) is not bool for x in list(actual)+list(predicted)):
        raise ValueError('boolean labels required')
    tp=sum(a and p for a,p in zip(actual,predicted))
    fp=sum(not a and p for a,p in zip(actual,predicted))
    tn=sum(not a and not p for a,p in zip(actual,predicted))
    fn=sum(a and not p for a,p in zip(actual,predicted))
    lead_times=list(lead_times)
    if any(not isfinite(x) or x < 0 for x in lead_times):
        raise ValueError('lead times must be finite nonnegative session counts')
    ratio=lambda x,y: x/y if y else None
    return dict(tp=tp,fp=fp,tn=tn,fn=fn,precision=ratio(tp,tp+fp),recall=ratio(tp,tp+fn),
                accuracy=ratio(tp+tn,len(actual)),fpr=ratio(fp,fp+tn),fnr=ratio(fn,fn+tp),
                lead_time=ratio(sum(lead_times),len(lead_times)))


def simulate_exposure(prices, signals, cost_bps=0):
    """Signals after close t execute at close t+1; returns then accrue t+1 -> t+2.

    Initial exposure is one. Costs apply to turnover at execution close. Last
    execution costs are included even when no subsequent return is observed.
    Opportunity cost is buy-and-hold wealth minus net strategy wealth.
    """
    values=_prices(prices)
    if len(values)!=len(signals) or not values:
        raise ValueError('nonempty aligned prices and signals required')
    if any(not isfinite(x) or not 0<=x<=1 for x in signals) or not isfinite(cost_bps) or cost_bps<0:
        raise ValueError('invalid exposure or cost')
    exposure=[1.0]+list(signals[:-1])
    wealth=baseline=1.0
    returns=[]
    turnover=[]
    for i in range(len(values)):
        change=abs(exposure[i]-(exposure[i-1] if i else 1.0))
        cost=change*cost_bps/10000
        ret=(values[i+1]/values[i]-1) if i+1<len(values) else 0
        net=exposure[i]*ret-cost
        returns.append(net)
        turnover.append(change)
        wealth*=1+net
        baseline*=1+ret
    return dict(executed_exposure=exposure,strategy_returns=returns,turnover=turnover,
                net_return=wealth-1,buy_hold_return=baseline-1,opportunity_cost=baseline-wealth,auto_trade=False)


def moving_average_signals(prices, window=20):
    values=_prices(prices)
    if not isinstance(window,int) or window<1: raise ValueError('positive integer window required')
    return [1.0 if i+1<window or p>=sum(values[i-window+1:i+1])/window else 0.0
            for i,p in enumerate(values)]


def evaluate_ablations(module_scores: Mapping[str, Sequence[float]], evaluator: Callable):
    """Invoke an injected evaluator with all modules, then omit each module once.

    No hidden recomputation or invented historical scores. Evaluator owns fitting
    and must respect chronological splits; returned results are unvalidated.
    """
    if not module_scores: raise ValueError('module scores required')
    lengths={len(v) for v in module_scores.values()}
    if len(lengths)!=1 or any(not isfinite(x) for v in module_scores.values() for x in v):
        raise ValueError('aligned finite module scores required')
    return {'all':evaluator(dict(module_scores)), **{
        'without_'+name:evaluator({k:v for k,v in module_scores.items() if k!=name})
        for name in module_scores}}


HISTORICAL_WINDOWS=(('2000','2000-01-01','2000-12-31'),('2007-2009','2007-01-01','2009-12-31'),
 ('2018','2018-01-01','2018-12-31'),('2020','2020-01-01','2020-12-31'),
 ('2022','2022-01-01','2022-12-31'),('2024-08','2024-08-01','2024-08-31'))


def historical_coverage(dates, horizon=120):
    """Admission inventory only, not empirical validation or a trading calendar.

    Requires endpoints spanning the named window and H later observations for
    every in-window observation. Caller must verify exchange-session completeness.
    """
    for value in dates: _aware(value)
    if any(a>=b for a,b in zip(dates,dates[1:])): raise ValueError('strict chronological dates required')
    if not isinstance(horizon,int) or horizon<1: raise ValueError('positive horizon required')
    days=[d.astimezone(timezone.utc).date().isoformat() for d in dates]
    result=[]
    for name,start,end in HISTORICAL_WINDOWS:
        indices=[i for i,d in enumerate(days) if start<=d<=end]
        admitted=bool(indices and days[0]<=start and days[-1]>=end and indices[-1]+horizon<len(days))
        result.append(dict(window=name,status='coverage_only' if admitted else 'unavailable',
                           observations=len(indices),validated=False,
                           reason='session completeness and empirical evaluation not established' if admitted else 'missing full window or forward horizon'))
    return result


def purged_three_way_split(n_samples, train_end, validation_end, horizon):
    """Exclusive segment boundaries; purge H labels before both boundaries.

    Test labels still require separately checking the available future tail.
    Model selection uses validation only; test data never enters fitted state.
    """
    if not all(isinstance(x,int) and not isinstance(x,bool) for x in (n_samples,train_end,validation_end,horizon)):
        raise ValueError('integer split parameters required')
    if not 0<=train_end<=validation_end<=n_samples or horizon<1:
        raise ValueError('invalid chronological split')
    return (list(range(max(0,train_end-horizon))),
            list(range(train_end,max(train_end,validation_end-horizon))),
            list(range(validation_end,n_samples)))
