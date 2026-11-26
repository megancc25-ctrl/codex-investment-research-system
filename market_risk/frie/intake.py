"""Explicit offline inputs. Admission is user-provided, never inferred from a URL."""
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from .engine import timestamp
from .mrm import Event, Session, AdjustedClose, EventStore, event_reactions, detect_good_news_fatigue, bad_news_amplification

def admitted(body):
    admission=body.get('admission',{})
    if not isinstance(admission,dict) or admission.get('status')!='ADMITTED' or not isinstance(admission.get('license_ref'),str) or not admission['license_ref'].strip():
        raise ValueError('explicit admitted offline data and license_ref required')

def mrm_report(body,db_path):
    """Import immutable events and compute reactions from supplied session/price file.

    Schema: admission, events (Event fields in ISO), sessions [{open,close}],
    prices [{ticker,time,value,available_at}], decision_cutoff, optional model
    {market_ticker,sector_ticker,market_beta,sector_beta}. No network calls.
    """
    admitted(body)
    events=[]
    event_types={'earnings','capex','order','guidance','financing','industry'}
    for raw in body.get('events',[]):
        raw=dict(raw)
        raw['event_type']=raw['event_type'].strip().lower()
        if raw['event_type'] not in event_types: raise ValueError('unsupported event_type')
        if urlparse(raw['source_url']).scheme not in {'http','https'} or not urlparse(raw['source_url']).netloc:
            raise ValueError('original HTTP/HTTPS event source required')
        for key in ('event_time','expectation_available_at'): raw[key]=timestamp(raw[key])
        events.append(Event(**raw))
    sessions=[Session(timestamp(s['open']),timestamp(s['close'])) for s in body.get('sessions',[])]
    prices=[AdjustedClose(p['ticker'],timestamp(p['time']),p['value'],timestamp(p['available_at'])) for p in body.get('prices',[])]
    cutoff=timestamp(body['decision_cutoff'])
    from datetime import datetime, timezone
    if cutoff>datetime.now(timezone.utc): raise ValueError('future decision cutoff not allowed')
    if any(e.event_time>cutoff for e in events): raise ValueError('cannot import future actual event at historical cutoff')
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    with EventStore(db_path) as store:
        all_events=store.list_events(cutoff)+events
        # Validate the complete proposed batch before any event is persisted.
        reactions=event_reactions(all_events,sessions,prices,cutoff,**body.get('model',{}))
        for event in events: store.append(event)
    signals={}
    for ticker in sorted({r.event.ticker for r in reactions}):
        sample=[r for r in reactions if r.event.ticker==ticker]
        signals[ticker]={'F01':detect_good_news_fatigue(sample,horizon=1),
                         'bad_news_amplification':bad_news_amplification(sample,horizon=1)}
    return {'schema_version':'frie-mrm-1.0','model_status':'NOT_VALIDATED','auto_trading':False,
            'admission':body['admission'],'signals':signals,'reactions':[asdict(r) for r in reactions],
            'limitations':['close-to-close windows include pre-event intraday exposure',
                            'actual > expected defines positive surprise; normalize lower-is-better inputs',
                            'market/sector betas are explicit research parameters, not automatically fitted']}
