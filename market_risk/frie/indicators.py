"""Offline numerical candidates. Inputs must already be aligned and completed.

These helpers make no evidence, licensing, historical validity, or model claims.
All percentile inputs use a 0..100 scale, and all thresholds are strict unless
explicitly documented otherwise. Rule version is intentionally NOT_VALIDATED.
"""
from math import isfinite


def _result(flag, reason, value=None):
    return dict(status='UNKNOWN' if flag is None else 'TRIGGERED' if flag else 'NOT_TRIGGERED',
                reason=reason,value=value,rule_version='NOT_VALIDATED')


def _number(value, name, percentile=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value):
        raise ValueError(name+' must be finite numeric')
    if percentile and not 0<=value<=100: raise ValueError(name+' must use 0..100 percentile scale')
    return float(value)


def _series(values,name):
    if values is None: return None
    return [None if x is None else _number(x,name) for x in values]


def f02_valuation_growth(valuation_percentile, growth_excess, *, valuation_threshold, growth_excess_threshold):
    """Joint high valuation and growth excess; excess definition is caller supplied."""
    vt=_number(valuation_threshold,'valuation threshold',True)
    gt=_number(growth_excess_threshold,'growth excess threshold')
    if valuation_percentile is None or growth_excess is None: return _result(None,'missing valuation or growth excess')
    v=_number(valuation_percentile,'valuation percentile',True)
    g=_number(growth_excess,'growth excess')
    return _result(v>=vt and g>=gt,'joint caller-configured thresholds',dict(valuation_percentile=v,growth_excess=g))


def f03_crowding(percentile):
    if percentile is None: return _result(None,'missing crowding percentile')
    value=_number(percentile,'crowding percentile',True)
    return _result(value>=90,'crowding percentile >= 90',value)


def f04_volatility_leverage(volatility_percentile, leverage_percentile):
    if volatility_percentile is None or leverage_percentile is None: return _result(None,'missing percentile')
    v=_number(volatility_percentile,'volatility percentile',True)
    l=_number(leverage_percentile,'leverage percentile',True)
    return _result(v<20 and l>90,'volatility percentile < 20 and leverage percentile > 90',dict(volatility=v,leverage=l))


def f06_fcf_declines(vendors):
    """Each vendor has current/prior_year lists of two consecutive quarter pairs.

    Each pair is (operating cash flow, positive cash capex outflow). FCF is OCF
    minus capex consistently for both periods. Caller verifies quarter alignment,
    comparable currency/accounting scope, and genuine vendor independence.
    """
    if vendors is None or len(vendors)<2: return _result(None,'at least two vendors required')
    values={}
    for vendor,data in vendors.items():
        if data is None: return _result(None,'missing vendor quarters')
        current=data.get('current'); prior=data.get('prior_year')
        if current is None or prior is None or len(current)!=2 or len(prior)!=2:
            return _result(None,'two consecutive paired prior-year quarters required')
        differences=[]
        for now,year in zip(current,prior):
            if now is None or year is None or len(now)!=2 or len(year)!=2 or any(x is None for x in (*now,*year)):
                return _result(None,'missing paired cash-flow input')
            ocf,capex=(_number(x,'cash flow') for x in now)
            old_ocf,old_capex=(_number(x,'cash flow') for x in year)
            if capex<0 or old_capex<0: raise ValueError('capex must be positive cash outflow convention')
            differences.append((ocf-capex)-(old_ocf-old_capex))
        values[vendor]=differences
    qualifying=sum(all(x<0 for x in changes) for changes in values.values())
    return _result(qualifying>=2,'at least two vendors each show two consecutive YoY FCF declines',values)


def f07_capex_debt(operating_cash_flow, cash_capex, net_debt):
    ocf=_series(operating_cash_flow,'OCF'); capex=_series(cash_capex,'capex'); debt=_series(net_debt,'net debt')
    if any(x is None for x in (ocf,capex,debt)): return _result(None,'missing cash-flow or debt series')
    if len(ocf)!=len(capex) or len(ocf)!=len(debt): raise ValueError('aligned series required')
    if len(ocf)<2 or any(x is None for seq in (ocf,capex,debt) for x in seq): return _result(None,'two complete observations required')
    if any(x<0 for x in capex): raise ValueError('capex must be positive cash outflow convention')
    if any(x<=0 for x in ocf): return _result(None,'nonpositive OCF makes ratio uninterpretable')
    ratios=[c/o for c,o in zip(capex,ocf)]
    return _result(ratios[-1]>ratios[-2] and debt[-1]>debt[-2],
                   'latest capex/positive OCF ratio and net debt both rising',dict(ratios=ratios,net_debt=debt))


def f08_hy_oas(oas, *, unit):
    """OAS expressed in basis points; widening uses exactly 20 session intervals."""
    if unit!='bp': raise ValueError('explicit bp unit required; convert percent upstream')
    values=_series(oas,'HY OAS bp')
    if not values or values[-1] is None: return _result(None,'missing current HY OAS')
    widening=values[-1]-values[-21] if len(values)>=21 and values[-21] is not None else None
    flag=True if values[-1]>400 or (widening is not None and widening>=100) else (False if widening is not None else None)
    return _result(flag,'OAS > 400 bp OR 20-session widening >= 100 bp; missing alternative stays unknown',
                   dict(current_bp=values[-1],widening_20_sessions_bp=widening))


def f15_vix_term(vix, vix3m, *, ratio_threshold, persistence):
    threshold=_number(ratio_threshold,'VIX ratio threshold')
    if threshold<=0: raise ValueError('positive ratio threshold required')
    if not isinstance(persistence,int) or isinstance(persistence,bool) or persistence<1: raise ValueError('positive explicit persistence required')
    short=_series(vix,'VIX'); long=_series(vix3m,'VIX3M')
    if short is None or long is None: return _result(None,'missing volatility inputs')
    if len(short)!=len(long): raise ValueError('aligned sessions required')
    if any(x is not None and x<=0 for x in short+long): raise ValueError('volatility levels must be positive')
    if len(short)<persistence or any(x is None for x in short[-persistence:]+long[-persistence:]): return _result(None,'insufficient complete sessions')
    ratios=[a/b for a,b in zip(short[-persistence:],long[-persistence:])]
    return _result(all(x>threshold for x in ratios),'ratio exceeds explicit threshold for explicit consecutive sessions',ratios)


def f18_breadth(inputs, *, thresholds):
    """Explicit candidate: all named breadth percentages <= their configured cuts.

    Requires at least two inputs, each measured on a 0..100 percentage scale.
    """
    if thresholds is None or len(thresholds)<2: raise ValueError('at least two explicit breadth thresholds required')
    cuts={k:_number(v,'breadth threshold',True) for k,v in thresholds.items()}
    if inputs is None or any(inputs.get(k) is None for k in cuts): return _result(None,'missing breadth component')
    values={k:_number(inputs[k],'breadth percentage',True) for k in cuts}
    return _result(all(values[k]<=cuts[k] for k in cuts),'all explicitly configured breadth components <= thresholds',values)


def o09_relative_strength(relative_ratio, *, earnings_support):
    """Latest 20 completed sessions must each exceed their own trailing 200 mean.

    Means include that completed session; ratio must be positive. The earnings
    support judgment is an explicit external boolean, never inferred from price.
    """
    if earnings_support is not None and type(earnings_support) is not bool: raise ValueError('earnings_support must be explicit boolean or None')
    values=_series(relative_ratio,'relative ratio')
    if values is None or earnings_support is None: return _result(None,'missing ratio or explicit earnings support')
    if any(x is not None and x<=0 for x in values): raise ValueError('relative ratios must be positive')
    if len(values)<219 or any(x is None for x in values[-219:]): return _result(None,'219 complete sessions required for twenty 200-session means')
    comparisons=[values[j]>sum(values[j-199:j+1])/200 for j in range(len(values)-20,len(values))]
    return _result(all(comparisons) and earnings_support,'20 consecutive ratios above 200-session mean and earnings support',dict(consecutive_passes=sum(comparisons),earnings_support=earnings_support))
