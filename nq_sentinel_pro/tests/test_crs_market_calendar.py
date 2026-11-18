import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from sentinel.crs.market_calendar import latest_completed_xnys_session


class CRSMarketCalendarTests(unittest.TestCase):
    def test_market_holiday_uses_previous_xnys_session(self):
        now=datetime(2026,11,26,18,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-11-25")

    def test_weekend_uses_latest_session_instead_of_weekend_date(self):
        now=datetime(2026,11,28,12,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-11-27")

    def test_before_market_close_does_not_select_incomplete_session(self):
        now=datetime(2026,11,18,15,59,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-11-17")

    def test_after_market_close_selects_current_session_across_dst(self):
        now=datetime(2026,11,18,16,1,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-11-18")

    def test_utc_next_day_does_not_advance_before_new_york_midnight(self):
        now=datetime(2026,11,18,0,30,tzinfo=ZoneInfo("UTC"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-11-17")

    def test_summer_session_close_uses_daylight_saving_offset(self):
        now=datetime(2026,6,15,16,1,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-06-15")

    def test_good_friday_uses_previous_xnys_session(self):
        now=datetime(2026,4,3,18,0,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(now),"2026-04-02")

    def test_early_close_uses_calendar_close_time(self):
        before_close=datetime(2026,11,27,12,59,tzinfo=ZoneInfo("America/New_York"))
        after_close=datetime(2026,11,27,13,1,tzinfo=ZoneInfo("America/New_York"))
        self.assertEqual(latest_completed_xnys_session(before_close),"2026-11-25")
        self.assertEqual(latest_completed_xnys_session(after_close),"2026-11-27")


if __name__ == "__main__":
    unittest.main()
