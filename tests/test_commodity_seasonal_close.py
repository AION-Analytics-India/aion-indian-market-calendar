"""Commodity close follows US daylight saving, with no date typed anywhere.

Sources: MCX/TRD/068/2026 (23:30 from 9 March 2026), MCX/TRD/550/2026 (23:55 from
2 November 2026 to 12 March 2027), NSE/COM/76446 (same window), NSE/COM/71784
(evening session "5 PM to 11:30/11:55 PM" on partial holidays).
"""
from datetime import date, datetime, time

import pytest

from aion_indian_market_calendar import IndiaMarketCalendar, commodity_close, get_market_phase, is_us_daylight_saving
from aion_indian_market_calendar.calendar import SessionRule, SessionSegment

MARKETS = ("MCX", "NSE_COMMODITY_DERIVATIVES")


@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2026, 3, 6), time(23, 55)),   # last Friday before the 8 March 2026 change
        (date(2026, 3, 9), time(23, 30)),   # MCX/TRD/068/2026 effective date
        (date(2026, 10, 30), time(23, 30)),
        (date(2026, 11, 2), time(23, 55)),  # MCX/TRD/550/2026 first day
        (date(2027, 3, 12), time(23, 55)),  # MCX/TRD/550/2026 last day
        (date(2027, 3, 15), time(23, 30)),  # first trading day after the 14 March 2027 change
        (date(2027, 11, 8), time(23, 55)),  # a later year works with no upkeep
    ],
)
def test_close_matches_the_circular_windows(day, expected):
    assert commodity_close(day) == expected


def test_daylight_saving_flag():
    assert is_us_daylight_saving(date(2026, 7, 1)) is True
    assert is_us_daylight_saving(date(2026, 12, 1)) is False


@pytest.mark.parametrize("market", MARKETS)
def test_session_and_open_state_today_and_before(market):
    cal = IndiaMarketCalendar.bundled(2026)
    assert cal.is_market_open(datetime(2026, 11, 2, 23, 45), market=market)
    assert cal.is_market_open(datetime(2026, 11, 2, 23, 55), market=market)
    assert not cal.is_market_open(datetime(2026, 11, 2, 23, 56), market=market)
    assert not cal.is_market_open(datetime(2026, 10, 30, 23, 45), market=market)
    assert cal.get_session(datetime(2026, 11, 2, 12, 0), market)[-1].close == time(23, 55)


def test_mcx_keeps_its_morning_window():
    segments = IndiaMarketCalendar.bundled(2026).get_session(datetime(2026, 11, 2, 12, 0), "MCX")
    assert [(s.open, s.close) for s in segments] == [(time(8, 45), time(8, 59)), (time(9, 0), time(23, 55))]


@pytest.mark.parametrize("market", MARKETS)
@pytest.mark.parametrize("day", [date(2026, 11, 10), date(2026, 11, 24)])
def test_evening_only_holiday_uses_the_seasonal_close(market, day):
    segments = IndiaMarketCalendar.bundled(2026).get_session(datetime(day.year, day.month, day.day, 18), market)
    assert [(s.open, s.close) for s in segments] == [(time(17, 0), time(23, 55))]


def test_evening_only_holiday_in_daylight_saving_keeps_2330():
    segments = IndiaMarketCalendar.bundled(2026).get_session(datetime(2026, 5, 1, 18), "MCX")
    assert [(s.open, s.close) for s in segments] == [(time(17, 0), time(23, 30))]


def test_full_closure_and_muhurat_are_not_touched():
    cal = IndiaMarketCalendar.bundled(2026)
    assert cal.get_session(datetime(2026, 12, 25, 18), "MCX") is None
    assert all(s.close < time(23, 0) for s in cal.get_session(datetime(2026, 11, 8, 15), "MCX"))


def test_phase_follows_the_close():
    assert get_market_phase(datetime(2026, 11, 2, 23, 40), "MCX") == "CONTINUOUS"
    assert get_market_phase(datetime(2026, 10, 30, 23, 40), "MCX") == "CLOSED"


def test_an_explicit_exchange_rule_takes_priority():
    cal = IndiaMarketCalendar.bundled(2026)
    day = date(2026, 12, 1)
    cal.session_rules.setdefault("MCX", []).append(
        SessionRule(
            market="MCX",
            segments=(SessionSegment(market="MCX", open=time(9, 0), close=time(23, 40)),),
            effective_from=day,
            effective_to=day,
        )
    )
    assert cal.get_session(datetime(2026, 12, 1, 12), "MCX")[-1].close == time(23, 40)
