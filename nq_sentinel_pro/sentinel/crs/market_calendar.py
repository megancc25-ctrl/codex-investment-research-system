"""NYSE session-date utilities for scheduled CRS reports."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import exchange_calendars as xcals


def latest_completed_xnys_session(now=None):
    """Return the latest fully closed XNYS session as YYYY-MM-DD.

    A market holiday resolves to the preceding session. A manual run before
    today's close also resolves to the preceding completed session.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)
    local_today = now_utc.astimezone(timezone.utc).date()
    start = local_today - timedelta(days=14)
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(start.isoformat(), local_today.isoformat())
    for session in reversed(sessions):
        close = calendar.session_close(session).to_pydatetime()
        if close.tzinfo is None:
            close = close.replace(tzinfo=timezone.utc)
        if close.astimezone(timezone.utc) <= now_utc:
            return session.date().isoformat()
    raise RuntimeError("No completed XNYS session found in the preceding 14 calendar days")


def main():
    print(latest_completed_xnys_session())


if __name__ == "__main__":
    main()
