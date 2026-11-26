"""Offline event reaction research. Returns are conservative adjusted close-to-close
windows, never pure post-event intraday returns. All timestamps must be aware.
Callers supply actual exchange sessions (including holidays), adjusted closes and
when each close became available; no calendar or prices are fetched implicitly.
"""
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import math
import sqlite3


def _aware(t):
    if not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')


def _finite(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise ValueError('finite numeric value required')


@dataclass(frozen=True)
class Event:
    event_id: str
    ticker: str
    event_type: str
    event_time: datetime
    expected_value: float
    actual_value: float
    expectation_available_at: datetime
    source_url: str
    quality: str
    economic_event_id: str

    def __post_init__(self):
        _aware(self.event_time); _aware(self.expectation_available_at)
        _finite(self.expected_value); _finite(self.actual_value)
        if self.expectation_available_at > self.event_time:
            raise ValueError('expectation was unavailable at event time')
        if not all(isinstance(v, str) and v.strip() for v in (self.event_id,self.ticker,self.event_type,self.source_url,self.quality,self.economic_event_id)):
            raise ValueError('event identifiers, source and quality are required')


@dataclass(frozen=True)
class Session:
    open: datetime
    close: datetime

    def __post_init__(self):
        _aware(self.open); _aware(self.close)
        if self.open >= self.close: raise ValueError('session open must precede close')


@dataclass(frozen=True)
class AdjustedClose:
    ticker: str
    time: datetime
    value: float
    available_at: datetime

    def __post_init__(self):
        _aware(self.time); _aware(self.available_at); _finite(self.value)
        if not self.ticker or self.value <= 0 or self.available_at < self.time:
            raise ValueError('positive adjusted close and availability at/after close required')


Price = AdjustedClose


@dataclass(frozen=True)
class Reaction:
    event: Event
    horizon: int
    status: str
    anchor_time: datetime | None = None
    end_time: datetime | None = None
    raw_return: float | None = None
    market_return: float | None = None
    sector_return: float | None = None
    excess_return: float | None = None
    contaminated: bool = False
    overlapping_event_ids: tuple = ()
    method: str = 'conservative adjusted close-to-close; includes pre-event exposure'
    reason: str = ''


def event_reactions(events, sessions, prices, decision_cutoff, *, market_ticker='MARKET', sector_ticker=None, market_beta=1.0, sector_beta=0.0, horizons=(1,5,20)):
    """One Reaction per unique (ticker,economic_event_id) and horizon.

    Horizon counts exchange session closes starting with the first session whose
    close is after the event. Anchor is the latest close strictly before event.
    Intraday thus includes the pre-event part of that session. Later event
    contamination is assessed over the entire close-to-close measurement window.
    UNKNOWN means absent calendar, unelapsed endpoint or unavailable input prices.
    Expectations are frozen in Event and never reconstructed from later vintages.
    Beta weights are explicit; sector is disabled by default to avoid subtracting
    the same systematic move twice. Positive surprise means actual > expected;
    callers must normalize metrics where a lower economic value is favorable.
    """
    _aware(decision_cutoff); _finite(market_beta); _finite(sector_beta)
    sessions=sorted(sessions,key=lambda s:s.open)
    if any(a.close >= b.open for a,b in zip(sessions,sessions[1:])):
        raise ValueError('sessions overlap or duplicate')
    horizons=tuple(horizons)
    if any(isinstance(h,bool) or not isinstance(h,int) or h<=0 for h in horizons): raise ValueError('positive integer horizons required')
    valid_closes={s.close for s in sessions}
    lookup={}
    for p in prices:
        if p.time not in valid_closes: raise ValueError('price time is not an exchange session close')
        key=(p.ticker,p.time)
        if key in lookup: raise ValueError('duplicate adjusted close')
        lookup[key]=p
    unique={}; ids={}
    for e in events:
        if e.event_id in ids and ids[e.event_id]!=e: raise ValueError('conflicting immutable event id')
        ids[e.event_id]=e
        key=(e.ticker,e.economic_event_id)
        if key in unique:
            old=unique[key]
            if (old.event_time,old.expected_value,old.actual_value)!=(e.event_time,e.expected_value,e.actual_value):
                raise ValueError('conflicting economic event vintages')
            rank=lambda item: (item.quality.strip().upper() != 'VERIFIED', item.event_id)
            unique[key]=min((old,e),key=rank)
        else: unique[key]=e
    events=sorted(unique.values(),key=lambda e:(e.event_time,e.event_id))
    output=[]
    for e in events:
        if e.event_time>decision_cutoff: continue
        before=[s.close for s in sessions if s.close<e.event_time]
        after=[s.close for s in sessions if s.close>e.event_time]
        anchor=before[-1] if before else None
        for h in horizons:
            end=after[h-1] if len(after)>=h else None
            overlaps=tuple(o.event_id for o in events if o.ticker==e.ticker and o.economic_event_id!=e.economic_event_id and anchor is not None and end is not None and anchor<o.event_time<=min(end,decision_cutoff))
            base=dict(event=e,horizon=h,anchor_time=anchor,end_time=end,contaminated=bool(overlaps),overlapping_event_ids=overlaps)
            if e.quality.strip().upper() != 'VERIFIED':
                output.append(Reaction(**base,status='UNKNOWN',reason='quality_not_verified')); continue
            if anchor is None or end is None or end>decision_cutoff:
                output.append(Reaction(**base,status='UNKNOWN',reason='missing calendar anchor or horizon not elapsed')); continue
            def ret(ticker):
                a=lookup.get((ticker,anchor)); b=lookup.get((ticker,end))
                if a is None or b is None or max(a.available_at,b.available_at)>decision_cutoff: return None
                return b.value/a.value-1
            raw=ret(e.ticker)
            market=ret(market_ticker) if market_beta else 0.0
            sector=ret(sector_ticker) if sector_beta and sector_ticker else (None if sector_beta else 0.0)
            if raw is None or market is None or sector is None:
                output.append(Reaction(**base,status='UNKNOWN',reason='required adjusted prices unavailable')); continue
            output.append(Reaction(**base,status='OK',raw_return=raw,market_return=market,sector_return=sector,excess_return=raw-market_beta*market-sector_beta*sector))
    return output


def _signal_sample(reactions,horizon,positive):
    reactions=list(reactions)
    if len({r.event.ticker for r in reactions}) > 1:
        raise ValueError('signals require a single ticker')
    rows={}
    for r in sorted(reactions,key=lambda r:(r.event.event_time,r.event.event_id)):
        surprise=r.event.actual_value-r.event.expected_value
        if r.horizon==horizon and (surprise>0 if positive else surprise<0):
            rows[(r.event.ticker,r.event.economic_event_id)]=r
    return list(rows.values())[-5:]


def detect_good_news_fatigue(reactions, *, horizon=1):
    """Last five unique positive surprises; >=3 nonpositive excess returns flags.
    Defaults to the one-session reaction horizon for F01.
    Incomplete or contaminated samples return UNKNOWN (never silently skipped).
    Supply a single ticker's reactions for a company-level signal.
    """
    sample=_signal_sample(reactions,horizon,True)
    if len(sample)<5 or any(r.status!='OK' or r.contaminated or r.event.quality.strip().upper() != 'VERIFIED' for r in sample): return dict(status='UNKNOWN',count=len(sample),evidence=[])
    count=sum(r.excess_return<=0 for r in sample)
    return dict(status='FLAG' if count>=3 else 'CLEAR',count=count,evidence=[r.event.event_id for r in sample])


def bad_news_amplification(reactions, *, horizon=5, threshold=0.0):
    """Last five negative surprises; flags >=3 excess returns below threshold.
    This transparent descriptive rule does not infer causality or calibrated risk.
    """
    _finite(threshold)
    sample=_signal_sample(reactions,horizon,False)
    if len(sample)<5 or any(r.status!='OK' or r.contaminated or r.event.quality.strip().upper() != 'VERIFIED' for r in sample): return dict(status='UNKNOWN',count=len(sample),evidence=[])
    count=sum(r.excess_return<threshold for r in sample)
    return dict(status='FLAG' if count>=3 else 'CLEAR',count=count,evidence=[r.event.event_id for r in sample])


def rate_sensitivity_change(rate_changes, returns, *, window=20):
    """OLS slopes (with intercept) for two adjacent, nonoverlapping windows.
    Inputs must be prealigned changes and returns already available at caller's
    decision cutoff. No levels, automatic alignment or future filling is applied.
    """
    x=list(rate_changes); y=list(returns)
    if len(x)!=len(y): raise ValueError('aligned equal length inputs required')
    if isinstance(window,bool) or not isinstance(window,int) or window<2: raise ValueError('window >=2 required')
    for v in x+y: _finite(v)
    if len(x)<2*window: return dict(status='UNKNOWN',reason='insufficient observations')
    def slope(a,b):
        mx=sum(a)/len(a); my=sum(b)/len(b)
        variance=sum((v-mx)**2 for v in a)
        return sum((v-mx)*(w-my) for v,w in zip(a,b))/variance if variance else None
    old=slope(x[-2*window:-window],y[-2*window:-window]); new=slope(x[-window:],y[-window:])
    if old is None or new is None: return dict(status='UNKNOWN',reason='zero rate variance')
    return dict(status='OK',previous_slope=old,current_slope=new,change=new-old,window=window)


class EventStore:
    """SQLite append-only event vintages. Identical inserts are idempotent;
    conflicting event IDs or economic-event values fail. Identical economic
    values may have multiple source IDs; differing revisions need a distinct
    economic_event_id so a historical expectation is never overwritten.
    list_events(cutoff) filters event and expectation availability.
    """
    def __init__(self,path):
        self.connection=sqlite3.connect(path)
        self.connection.execute('CREATE TABLE IF NOT EXISTS mrm_events (event_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        self.connection.execute("CREATE TRIGGER IF NOT EXISTS mrm_no_update BEFORE UPDATE ON mrm_events BEGIN SELECT RAISE(ABORT, 'append-only events'); END")
        self.connection.execute("CREATE TRIGGER IF NOT EXISTS mrm_no_delete BEFORE DELETE ON mrm_events BEGIN SELECT RAISE(ABORT, 'append-only events'); END")
        self.connection.commit()
    def append(self,event):
        data=asdict(event)
        for key in ('event_time','expectation_available_at'): data[key]=data[key].isoformat()
        payload=json.dumps(data,sort_keys=True)
        with self.connection:
            previous=self.connection.execute('SELECT payload FROM mrm_events WHERE event_id=?',(event.event_id,)).fetchone()
            if previous:
                if previous[0]!=payload: raise ValueError('immutable event conflict')
                return
            for existing in self.list_events():
                if (existing.ticker,existing.economic_event_id)==(event.ticker,event.economic_event_id):
                    if (existing.event_time,existing.expected_value,existing.actual_value)!=(event.event_time,event.expected_value,event.actual_value):
                        raise ValueError('conflicting economic event vintages')
            self.connection.execute('INSERT INTO mrm_events VALUES (?,?)',(event.event_id,payload))
    def list_events(self,cutoff=None):
        if cutoff is not None: _aware(cutoff)
        result=[]
        for (payload,) in self.connection.execute('SELECT payload FROM mrm_events'):
            data=json.loads(payload)
            for key in ('event_time','expectation_available_at'): data[key]=datetime.fromisoformat(data[key])
            event=Event(**data)
            if cutoff is None or max(event.event_time,event.expectation_available_at)<=cutoff: result.append(event)
        return sorted(result,key=lambda e:(e.event_time,e.event_id))
    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
