"""Private, confirmed mathematical loss budgets; never execution permission."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
from math import isfinite
import json


def _time(value):
    if not isinstance(value,(datetime,str)):raise ValueError('aware timestamp required')
    result=value if isinstance(value,datetime) else datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None or result.utcoffset() is None: raise ValueError('aware time required')
    return result.astimezone(timezone.utc)


def load_private_config(path):
    """Read JSON only beneath repo data/aswm, or an explicitly absolute external path.

    External means outside this repository. Relative outside paths are rejected;
    symlinks are resolved before enforcing containment. Never writes config.
    """
    root=Path(__file__).resolve().parents[2]
    supplied=Path(path)
    resolved=supplied.resolve()
    allowed=root/'data'/'aswm'
    if not resolved.is_relative_to(allowed) and (not supplied.is_absolute() or resolved.is_relative_to(root)):
        raise ValueError('private config must be data/aswm or absolute external private path')
    with resolved.open(encoding='utf-8') as stream: return json.load(stream)


def risk_budget(config,as_of,*,max_confirmation_days=90):
    """Fractions of account NAV. TOTAL_ACCOUNT reserves all configured stress;
    INCREMENTAL_ADDITIONAL reserves refer to additional loss, not current stress.
    completed_reductions is an audit record only: current weights must already
    reflect them. Account NAV/currency are user-confirmed, never inferred.
    """
    result=dict(status='UNKNOWN',auto_trade=False,actionable_eligibility=False,model_status='NOT_VALIDATED')
    now=_time(as_of)
    if not isinstance(max_confirmation_days,int) or not 1<=max_confirmation_days<=90: raise ValueError('confirmation TTL must be 1..90 days')
    if not isinstance(config,dict) or config.get('schema_version')!='aswm-private-1.0': return dict(result,reason='missing private schema')
    try:
        confirmed=_time(config['confirmed_at']); expiry=_time(config['expires_at'])
    except (KeyError,ValueError,TypeError,AttributeError): return dict(result,reason='missing aware confirmation/expiry')
    if confirmed>now or expiry<=now or expiry<=confirmed or now-confirmed>=timedelta(days=max_confirmation_days):
        return dict(result,status='BLOCKED',reason='confirmation future, expired, or stale')
    p=config.get('portfolio') or {}; b=config.get('risk_budget') or {}
    keys=('remaining_loss_budget','semiconductor_stress_loss','other_assets_loss','fx_loss','fees_loss','uncertainty_buffer','liquidity_limit')
    if any(b.get(k) is None for k in keys) or any(p.get(k) is None for k in ('semiconductor_weight','cash_weight','account_nav','currency','leverage','completed_reductions')):
        return dict(result,reason='explicit reserves and confirmed portfolio required')
    def fraction(value):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not isfinite(value) or not 0<=value<=1: raise ValueError('finite unlevered fractions required')
        return float(value)
    values={k:fraction(b[k]) for k in keys}
    current=fraction(p['semiconductor_weight']);cash=fraction(p['cash_weight'])
    if p['leverage'] is not False or abs(current+cash-1)>1e-8: return dict(result,status='BLOCKED',reason='unlevered two-asset weights must sum to one')
    nav=p['account_nav']
    if isinstance(nav,bool) or not isinstance(nav,(int,float)) or not isfinite(nav) or nav<=0: raise ValueError('positive finite account NAV required')
    if not isinstance(p['currency'],str) or not p['currency'].strip() or not isinstance(p['completed_reductions'],list): raise ValueError('currency and reduction audit list required')
    scope=config.get('budget_scope')
    if scope not in ('TOTAL_ACCOUNT','INCREMENTAL_ADDITIONAL'): return dict(result,reason='explicit budget_scope required')
    stress=values['semiconductor_stress_loss']
    if stress<=0: return dict(result,status='BLOCKED',reason='positive semiconductor stress required')
    reserves=sum(values[k] for k in ('other_assets_loss','fx_loss','fees_loss','uncertainty_buffer'))
    available=values['remaining_loss_budget']-reserves
    raw=(current if scope=='INCREMENTAL_ADDITIONAL' else 0)+available/stress
    ceiling=max(0,min(1,values['liquidity_limit'],raw))
    room=ceiling-current
    return dict(result,status='MATHEMATICAL_ONLY',reason='theoretical bound; no execution eligibility',budget_scope=scope,
                theoretical_ceiling=ceiling,unclipped_ceiling=raw,current_stress_loss=current*stress+reserves,
                reserved_loss=reserves,available_loss_after_reserves=available,current_room=room,
                new_space=max(0,room),new_space_nav=max(0,room)*nav,current_room_nav=room*nav,
                account_nav=nav,currency=p['currency'],confirmed_at=confirmed.isoformat(),
                semantics='total account ceiling' if scope=='TOTAL_ACCOUNT' else 'incremental additional budget above current exposure')
