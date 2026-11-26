"""Deterministic offline scheduling. No threads, sleeps, network, or trading.

Callbacks are authorized only for one declared capability; they remain trusted
application code, not a sandbox. All authorization gates default closed.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
import sqlite3


def _aware(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')


@dataclass(frozen=True)
class Authorization:
    collection: bool = False
    cache: bool = False
    publication: bool = False


class LicensedMinuteAdapter(Protocol):
    """Application adapter must attest its current minute-data entitlement."""
    def is_licensed(self, now: datetime) -> bool: ...
    def collect(self, now: datetime): ...


class OfflineScheduler:
    intervals={'daily':timedelta(days=1),'weekly':timedelta(days=7),
               'monthly':timedelta(days=31),'quarterly':timedelta(days=93),
               'minute':timedelta(minutes=1),'event':timedelta(0)}

    def __init__(self, authorization=None):
        self.authorization=authorization or Authorization()
        self.last_success={}
        self.heartbeat={}
        self.auto_trade=False

    def due(self, kind, now):
        """Daily/weekly use elapsed intervals; monthly/quarterly use UTC periods.

        Event calls are always due; event alert dedup is handled separately.
        """
        _aware(now)
        if kind not in self.intervals: raise ValueError('unknown schedule')
        previous=self.last_success.get(kind)
        if previous is None: return True
        if now<previous: raise ValueError('time cannot move backwards')
        current=now.astimezone(timezone.utc)
        prior=previous.astimezone(timezone.utc)
        if kind=='monthly': return (current.year,current.month)!=(prior.year,prior.month)
        if kind=='quarterly': return (current.year,(current.month-1)//3)!=(prior.year,(prior.month-1)//3)
        return now-previous>=self.intervals[kind]

    def is_stale(self, kind, now, max_age=None):
        _aware(now)
        if kind not in self.intervals: raise ValueError('unknown schedule')
        previous=self.last_success.get(kind)
        age=max_age if max_age is not None else self.intervals[kind]*2
        if age<timedelta(0): raise ValueError('negative maximum age')
        if previous and now<previous: raise ValueError('time cannot move backwards')
        return previous is None or now-previous>=age

    def run(self, kind, now, callback, capability='collection', max_attempts=3, minute_adapter=None):
        _aware(now)
        if kind not in self.intervals: raise ValueError('unknown schedule')
        if capability not in ('collection','cache','publication'): raise ValueError('unknown capability')
        if not isinstance(max_attempts,int) or isinstance(max_attempts,bool) or not 1<=max_attempts<=10:
            raise ValueError('attempt limit must be between one and ten')
        self.heartbeat[kind]=now
        if getattr(self.authorization,capability) is not True:
            return dict(status='denied',attempts=0,auto_trade=False)
        # Minute collection cannot substitute an unrestricted arbitrary callback.
        if kind=='minute':
            if minute_adapter is None or minute_adapter.is_licensed(now) is not True:
                return dict(status='denied',attempts=0,auto_trade=False)
            if capability=='collection': callback=lambda:minute_adapter.collect(now)
        if not self.due(kind,now): return dict(status='not_due',attempts=0,auto_trade=False)
        delays=[]
        for attempt in range(1,max_attempts+1):
            try:
                value=callback()
            except Exception as error:
                if attempt==max_attempts:
                    return dict(status='failed',attempts=attempt,retry_delays=delays,
                                error_type=type(error).__name__,auto_trade=False)
                delays.append(2**(attempt-1))
            else:
                self.last_success[kind]=now
                return dict(status='success',attempts=attempt,retry_delays=delays,value=value,auto_trade=False)


class AlertTransitions:
    """SQLite transaction dedup of consecutive states, persisted across restarts.

    Recording is local only and grants no permission to publish. Re-entry into a
    prior state is a new transition and returns True.
    """
    def __init__(self,path):
        self.connection=sqlite3.connect(str(path))
        self.connection.execute('CREATE TABLE IF NOT EXISTS frie_alert_state (alert_key TEXT PRIMARY KEY, state TEXT NOT NULL, observed_at TEXT NOT NULL)')
        self.connection.commit()

    def record(self,key,state,now):
        _aware(now)
        if not isinstance(key,str) or not key or not isinstance(state,str) or not state:
            raise ValueError('nonempty key and state required')
        with self.connection:
            self.connection.execute('BEGIN IMMEDIATE')
            row=self.connection.execute('SELECT state, observed_at FROM frie_alert_state WHERE alert_key=?',(key,)).fetchone()
            if row and now<datetime.fromisoformat(row[1]): raise ValueError('out-of-order alert')
            if row and row[0]==state: return False
            self.connection.execute('INSERT INTO frie_alert_state VALUES (?,?,?) ON CONFLICT(alert_key) DO UPDATE SET state=excluded.state, observed_at=excluded.observed_at',
                                    (key,state,now.isoformat()))
        return True

    def close(self): self.connection.close()
    def __enter__(self): return self
    def __exit__(self,*args): self.close()
