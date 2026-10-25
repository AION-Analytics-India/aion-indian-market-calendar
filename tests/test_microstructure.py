"""Settlement days, phases, expiries and Muhurat, pinned to the bundled 2026 data.

Every test passes an explicit calendar built from the bundled file, so a data
refresh on the test machine cannot change the expected answers.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import pytest

import aion_indian_market_calendar as pkg
from aion_indian_market_calendar import IndiaMarketCalendar, microstructure as ms

BUNDLED = Path(pkg.__file__).resolve().parent / "data" / "holidays_2026.json"


@pytest.fixture(scope="module")
def cal() -> IndiaMarketCalendar:
    return IndiaMarketCalendar(events_json_path=str(BUNDLED))


# --- exports --------------------------------------------------------------------

def test_new_functions_are_exported_from_the_package_root():
    for name in ("is_trading_day", "is_settlement_day", "settlement_holidays", "get_market_phase",
                 "get_expiry_day", "is_muhurat_trading", "muhurat_session"):
        assert name in pkg.__all__ and callable(getattr(pkg, name))


# --- trading vs settlement ------------------------------------------------------

def test_settlement_holidays_match_nse_clearing_list_2026(cal):
    expected = {
        "2026-01-15", "2026-01-26", "2026-02-19", "2026-03-03", "2026-03-19", "2026-03-26",
        "2026-03-31", "2026-04-01", "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
        "2026-06-26", "2026-08-26", "2026-09-14", "2026-10-02", "2026-10-20", "2026-11-10",
        "2026-11-24", "2026-12-25",
    }
    assert {d.isoformat() for d in ms.settlement_holidays(2026, calendar=cal)} == expected


@pytest.mark.parametrize("day", ["2026-02-19", "2026-03-19", "2026-04-01", "2026-08-26"])
def test_equity_trades_but_does_not_settle(cal, day):
    assert ms.is_trading_day(day, "NSE", calendar=cal) is True
    assert ms.is_settlement_day(day, calendar=cal) is False


def test_ordinary_weekday_trades_and_settles(cal):
    assert ms.is_trading_day("2026-10-26", calendar=cal) is True
    assert ms.is_settlement_day(date(2026, 10, 26), calendar=cal) is True


def test_weekend_neither_trades_nor_settles(cal):
    assert ms.is_trading_day("2026-10-25", calendar=cal) is False
    assert ms.is_settlement_day("2026-10-25", calendar=cal) is False


def test_holiday_neither_trades_nor_settles(cal):
    assert ms.is_trading_day("2026-10-20", calendar=cal) is False
    assert ms.is_settlement_day("2026-10-20", calendar=cal) is False


def test_settlement_outside_data_range_refuses(cal):
    with pytest.raises(ValueError, match="outside the bundled data range"):
        ms.is_settlement_day("2027-01-05", calendar=cal)


# --- phases ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "clock, expected",
    [
        ("08:59", ms.CLOSED),
        ("09:00", ms.PRE_OPEN),
        ("09:14", ms.PRE_OPEN),
        ("09:15", ms.CONTINUOUS),
        ("15:29", ms.CONTINUOUS),
        ("15:30", ms.CLOSED),
        ("15:50", ms.POST_CLOSE),
        ("15:59", ms.POST_CLOSE),
        ("16:00", ms.CLOSED),
    ],
)
def test_nse_cash_phases_on_a_normal_day(cal, clock, expected):
    assert ms.get_market_phase(f"2026-10-26T{clock}", "NSE", calendar=cal) == expected


@pytest.mark.parametrize(
    "when, expected",
    [
        ("2026-10-26T15:14", ms.CONTINUOUS),
        ("2026-10-26T15:15", ms.CLOSING_AUCTION),
        ("2026-10-26T15:34", ms.CLOSING_AUCTION),
        ("2026-10-26T15:35", ms.CLOSED),
        # Revised timings from 7 December 2026.
        ("2026-12-08T15:29", ms.CONTINUOUS),
        ("2026-12-08T15:30", ms.CLOSING_AUCTION),
        ("2026-12-08T15:40", ms.CLOSED),
    ],
)
def test_fno_underlying_closing_auction(cal, when, expected):
    assert ms.get_market_phase(when, "NSE_EQUITY_FNO_UNDERLYING", calendar=cal) == expected


def test_derivatives_have_no_pre_open(cal):
    assert ms.get_market_phase("2026-10-26T09:05", "NIFTY", calendar=cal) == ms.CLOSED
    assert ms.get_market_phase("2026-10-26T09:15", "NIFTY", calendar=cal) == ms.CONTINUOUS


def test_mcx_order_cancellation_window_is_pre_open(cal):
    assert ms.get_market_phase("2026-10-26T08:50", "MCX", calendar=cal) == ms.PRE_OPEN
    assert ms.get_market_phase("2026-10-26T20:00", "MCX", calendar=cal) == ms.CONTINUOUS


def test_holiday_and_weekend_are_closed_all_day(cal):
    assert ms.get_market_phase("2026-10-20T11:00", "NSE", calendar=cal) == ms.CLOSED
    assert ms.get_market_phase("2026-10-25T11:00", "NSE", calendar=cal) == ms.CLOSED


def test_aware_datetime_is_converted_to_ist(cal):
    from zoneinfo import ZoneInfo
    utc = datetime(2026, 10, 26, 4, 0, tzinfo=ZoneInfo("UTC"))  # 09:30 IST
    assert ms.get_market_phase(utc, "NSE", calendar=cal) == ms.CONTINUOUS


# --- naive datetimes (UserWarning from 1.6.0) ------------------------------------

NAIVE_MESSAGE = ("Naive datetime detected. Assuming IST. "
                 "Pass a timezone-aware datetime to avoid incorrect phase calculation.")


def test_naive_datetime_warns_and_is_read_as_ist(cal):
    with pytest.warns(UserWarning) as caught:
        phase = ms.get_market_phase(datetime(2026, 10, 26, 9, 30), "NSE", calendar=cal)
    assert phase == ms.CONTINUOUS
    assert str(caught[0].message) == NAIVE_MESSAGE


def test_naive_time_string_warns(cal):
    with pytest.warns(UserWarning, match="Naive datetime detected"):
        cal.is_market_open("2026-10-26T09:30")


def test_new_york_time_gives_the_right_answer_only_when_aware(cal):
    from zoneinfo import ZoneInfo
    import warnings as _w
    aware = datetime(2026, 10, 26, 0, 30, tzinfo=ZoneInfo("America/New_York"))  # 10:00 IST
    with _w.catch_warnings():
        _w.simplefilter("error")
        assert ms.get_market_phase(aware, "NSE", calendar=cal) == ms.CONTINUOUS
    with pytest.warns(UserWarning):
        # The same wall clock, naive: read as 00:30 IST, so the answer is wrong, and it says so.
        assert ms.get_market_phase(datetime(2026, 10, 26, 0, 30), "NSE", calendar=cal) == ms.CLOSED


@pytest.mark.parametrize("value", [date(2026, 10, 26), "2026-10-26", "2026-10-26T09:30+05:30",
                                   "2026-10-26T04:00Z"])
def test_dates_and_aware_values_do_not_warn(cal, value):
    import warnings as _w
    with _w.catch_warnings():
        _w.simplefilter("error")
        cal.is_trading_day(value)
        ms.is_trading_day(value, calendar=cal)
        ms.is_settlement_day(value, calendar=cal)
        ms.get_expiry_day("NIFTY", value, calendar=cal)


# --- Muhurat ----------------------------------------------------------------------

def test_muhurat_on_a_sunday(cal):
    assert ms.is_muhurat_trading("2026-11-08", "NSE", calendar=cal) is True
    assert ms.is_muhurat_trading("2026-11-08", "BSE", calendar=cal) is True
    assert ms.is_muhurat_trading("2026-11-09", "NSE", calendar=cal) is False
    session = ms.muhurat_session("2026-11-08", "NSE", calendar=cal)
    assert (session.open, session.close) == (time(18, 15), time(19, 15))
    assert session.provisional is True


def test_muhurat_phase(cal):
    assert ms.get_market_phase("2026-11-08T18:30", "NSE", calendar=cal) == ms.MUHURAT_TRADING
    assert ms.get_market_phase("2026-11-08T09:30", "NSE", calendar=cal) == ms.CLOSED
    assert ms.get_market_phase("2026-11-08T19:15", "NSE", calendar=cal) == ms.CLOSED


# --- expiries -----------------------------------------------------------------

@pytest.mark.parametrize(
    "index, day, contract, expected",
    [
        ("NIFTY", "2026-10-25", None, date(2026, 10, 27)),        # weekly, Tuesday
        ("NIFTY", "2026-10-27", None, date(2026, 10, 27)),        # expiry day itself
        ("NIFTY", "2026-10-28", None, date(2026, 11, 3)),
        ("NIFTY", "2026-03-01", None, date(2026, 3, 2)),          # Tue 3 Mar is Holi: Monday
        ("NIFTY", "2026-03-03", None, date(2026, 3, 10)),         # moved expiry already past
        ("NIFTY", "2026-10-25", "monthly", date(2026, 10, 27)),   # last Tuesday
        ("BANKNIFTY", "2026-10-25", None, date(2026, 10, 27)),    # monthly only
        ("BANKNIFTY", "2026-03-25", None, date(2026, 3, 30)),     # 31 Mar is a holiday
        ("Bank Nifty", "2026-03-25", None, date(2026, 3, 30)),    # alias
        ("SENSEX", "2026-10-25", None, date(2026, 10, 29)),       # weekly, Thursday
        ("SENSEX", "2026-10-25", "monthly", date(2026, 10, 29)),  # last Thursday
        ("SENSEX", "2026-03-26", None, date(2026, 4, 2)),         # Thu 26 Mar is a holiday
        ("FINNIFTY", "2026-09-01", None, date(2026, 9, 29)),
    ],
)
def test_expiry_days(cal, index, day, contract, expected):
    assert ms.get_expiry_day(index, day, contract=contract, calendar=cal) == expected


def test_expiry_is_a_trading_day_in_its_segment(cal):
    for day in ("2026-01-05", "2026-04-07", "2026-08-10", "2026-11-02"):
        expiry = ms.get_expiry_day("NIFTY", day, calendar=cal)
        assert expiry.weekday() <= 1
        assert ms.is_trading_day(expiry, "NIFTY", calendar=cal)


@pytest.mark.parametrize(
    "index, day, contract, message",
    [
        ("BANKNIFTY", "2026-10-25", "weekly", "no weekly contract"),
        ("BANKEX", "2026-10-25", None, "No sourced expiry rule"),
        ("NIFTY", "2025-08-01", None, "apply from 2025-09-01"),
        ("NIFTY", "2026-12-28", None, "outside the bundled data range"),
    ],
)
def test_expiry_refusals(cal, index, day, contract, message):
    with pytest.raises(ValueError, match=message):
        ms.get_expiry_day(index, day, contract=contract, calendar=cal)
