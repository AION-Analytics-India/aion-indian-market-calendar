from __future__ import annotations

import json
from datetime import date, datetime
from io import BytesIO

import pytest

from aion_indian_market_calendar import (
    EventCalendar,
    is_continuous_trading,
    is_market_open,
    next_trading_day,
)
from aion_indian_market_calendar import calendar as calendar_module


def test_from_json_loads_events(sample_json_path):
    calendar = EventCalendar.from_json(sample_json_path)
    assert len(calendar) == 3


def test_events_on_filters_by_day_and_exchange(sample_calendar: EventCalendar):
    events = sample_calendar.events_on("2026-01-26", exchange="NSE")
    assert len(events) == 1
    assert events[0].title == "Republic Day Market Holiday"


def test_holidays_returns_only_holiday_events(sample_calendar: EventCalendar):
    holidays = sample_calendar.holidays(exchange="BSE", year=2026)
    assert holidays == [date(2026, 1, 26)]


def test_upcoming_honors_limit(sample_calendar: EventCalendar):
    events = sample_calendar.upcoming(as_of="2026-02-01T00:00:00", limit=1)
    assert len(events) == 1
    assert events[0].event_id == "policy-2026-02-06"


def test_bundled_calendar_loads_placeholder_file():
    calendar = EventCalendar.bundled(2026)
    assert isinstance(calendar, EventCalendar)
    assert len(calendar) > 0
    assert calendar.sources["nse_circulars_rss"] == "https://nsearchives.nseindia.com/content/RSS/Circulars.xml"


def test_policy_and_session_override_are_typed(sample_calendar: EventCalendar):
    event = sample_calendar.by_category("macro")[0]
    assert event.policy.action == "ALLOW_REDUCED_SIZE"
    assert event.policy.size_multiplier == 0.5

    session = sample_calendar.get_session(datetime(2026, 2, 6, 9, 30), market="NSE")
    assert session is not None
    assert len(session) == 1
    assert session[0].close.isoformat() == "13:00:00"


def test_bundled_segment_holidays_and_sessions():
    calendar = EventCalendar.bundled(2026)

    equity_holidays = calendar.holidays(market="NSE_EQUITY", year=2026)
    assert date(2026, 1, 15) in equity_holidays
    assert date(2026, 12, 25) in equity_holidays
    assert len(equity_holidays) == 16
    assert calendar.is_trading_day(datetime(2026, 1, 27, 9, 5), market="NSE_EQUITY")
    equity_session = calendar.get_session(datetime(2026, 1, 27, 9, 5), market="NSE_EQUITY")
    assert equity_session is not None
    assert [(segment.market, segment.open.isoformat(), segment.close.isoformat()) for segment in equity_session] == [("NSE_EQUITY", "09:00:00", "15:30:00")]

    assert calendar.is_trading_day(datetime(2026, 1, 15, 10, 0), market="NSE_COMMODITY_DERIVATIVES")
    commodity_session = calendar.get_session(datetime(2026, 1, 15, 18, 0), market="NSE_COMMODITY_DERIVATIVES")
    assert commodity_session is not None
    assert [(segment.open.isoformat(), segment.close.isoformat()) for segment in commodity_session] == [("17:00:00", "23:30:00")]

    mcx_session = calendar.get_session(datetime(2026, 7, 1, 18, 0), market="MCX")
    assert mcx_session is not None
    assert [(segment.market, segment.open.isoformat(), segment.close.isoformat()) for segment in mcx_session] == [
        ("MCX", "08:45:00", "08:59:00"),
        ("MCX", "09:00:00", "23:30:00"),
    ]
    assert date(2026, 3, 3) not in calendar.holidays(market="MCX", year=2026)
    assert date(2026, 4, 3) in calendar.holidays(market="MCX", year=2026)
    mcx_normal_session = calendar.get_session(datetime(2026, 1, 15, 18, 0), market="MCX")
    assert mcx_normal_session is not None
    assert [(segment.market, segment.open.isoformat(), segment.close.isoformat()) for segment in mcx_normal_session] == [
        ("MCX", "08:45:00", "08:59:00"),
        ("MCX", "09:00:00", "23:30:00"),
    ]
    mcx_partial_session = calendar.get_session(datetime(2026, 3, 3, 18, 0), market="MCX")
    assert mcx_partial_session is not None
    assert [(segment.market, segment.open.isoformat(), segment.close.isoformat()) for segment in mcx_partial_session] == [
        ("MCX", "17:00:00", "23:30:00")
    ]
    assert calendar.is_trading_day(datetime(2026, 3, 3, 18, 0), market="MCX")
    assert not calendar.is_trading_day(datetime(2026, 4, 3, 18, 0), market="MCX")


def test_is_market_open_is_session_aware():
    calendar = EventCalendar.bundled(2026)

    assert calendar.is_market_open(datetime(2026, 1, 27, 9, 5), market="NSE_EQUITY")
    assert not calendar.is_market_open(datetime(2026, 1, 27, 8, 55), market="NSE_EQUITY")
    assert calendar.is_market_open(datetime(2026, 3, 3, 18, 0), market="MCX")
    assert not calendar.is_market_open(datetime(2026, 4, 3, 18, 0), market="MCX")


def test_module_level_is_market_open_helper():
    assert is_market_open("NSE", at="2026-01-27T09:05:00+05:30")
    assert not is_market_open("NSE", at="2026-01-27T08:55:00+05:30")


def test_market_aliases_and_instruments_resolve_to_canonical_segments():
    calendar = EventCalendar.bundled(2026)
    probe = datetime(2026, 1, 27, 10, 0)

    canonical_session = calendar.get_session(probe, market="NSE_EQUITY_DERIVATIVES")
    nfo_session = calendar.get_session(probe, market="NFO")
    fno_session = calendar.get_session(probe, market="FNO")
    nifty_session = calendar.get_session(probe, market="NIFTY")
    banknifty_session = calendar.get_session(probe, market="BANKNIFTY")

    assert canonical_session is not None
    assert nfo_session == canonical_session
    assert fno_session == canonical_session
    assert nifty_session == canonical_session
    assert banknifty_session == canonical_session


def test_unknown_market_inputs_raise_value_error():
    calendar = EventCalendar.bundled(2026)

    with pytest.raises(ValueError, match="Unknown market input"):
        calendar.get_session(datetime(2026, 1, 27, 10, 0), market="UNKNOWN")

    with pytest.raises(ValueError, match="Unknown market input"):
        is_market_open("UNKNOWN", at="2026-01-27T10:00:00+05:30")


def test_timezone_fallback_uses_pytz_for_ist(monkeypatch):
    def raising_zoneinfo(name: str):
        raise RuntimeError("zoneinfo unavailable")

    monkeypatch.setattr(calendar_module, "ZoneInfo", raising_zoneinfo)

    calendar = EventCalendar.from_records([], timezone="Asia/Kolkata")
    probe = calendar_module._coerce_datetime("2026-01-27T09:05:00", calendar.tz)

    assert getattr(calendar.tz, "zone", None) == "Asia/Kolkata"
    assert probe.utcoffset().total_seconds() == 19800


def test_timezone_fallback_preserves_non_ist_timezone(monkeypatch):
    def raising_zoneinfo(name: str):
        raise RuntimeError("zoneinfo unavailable")

    monkeypatch.setattr(calendar_module, "ZoneInfo", raising_zoneinfo)

    calendar = EventCalendar.from_records([], timezone="UTC")
    probe = calendar_module._coerce_datetime("2026-01-27T09:05:00", calendar.tz)

    assert getattr(calendar.tz, "zone", None) == "UTC"
    assert probe.utcoffset().total_seconds() == 0


def test_next_trading_day_helper():
    calendar = EventCalendar.bundled(2026)
    assert calendar.next_trading_day("2026-01-26T10:00:00+05:30", market="NSE_EQUITY") == date(2026, 1, 27)
    assert next_trading_day("NSE_EQUITY", after="2026-01-26T10:00:00+05:30") == date(2026, 1, 27)




@pytest.mark.parametrize(
    "cash_market, derivatives_market, cash_open",
    [
        ("NSE_EQUITY_FNO_UNDERLYING", "NSE_EQUITY_DERIVATIVES", "09:00:00"),
        ("BSE_EQUITY_FNO_UNDERLYING", "BSE_EQUITY_DERIVATIVES", "09:15:00"),
    ],
)
def test_closing_auction_splits_the_cash_segment_from_effective_date(cash_market, derivatives_market, cash_open):
    """SEBI HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 para 4.2.1: CAS is 15:15-15:35."""
    calendar = EventCalendar.bundled(2026)
    before = datetime(2026, 7, 31, 10, 0)
    after = datetime(2026, 8, 3, 10, 0)

    def windows(dt, market):
        return [
            (segment.open.isoformat(), segment.close.isoformat(), segment.kind)
            for segment in calendar.get_session(dt, market=market)
        ]

    assert windows(before, cash_market) == [(cash_open, "15:30:00", "continuous")]
    assert windows(after, cash_market) == [
        (cash_open, "15:15:00", "continuous"),
        ("15:15:00", "15:35:00", "closing_auction"),
    ]

    # Para 4.2.3 — the derivatives segment operates up to 15:40.
    assert windows(before, derivatives_market) == [("09:15:00", "15:30:00", "continuous")]
    assert windows(after, derivatives_market) == [("09:15:00", "15:40:00", "continuous")]


def test_non_fno_equity_is_untouched_by_cas():
    """Para 4.1.2 — remaining securities keep the 30-minute CTS VWAP close."""
    calendar = EventCalendar.bundled(2026)
    after = datetime(2026, 8, 3, 10, 0)

    for market in ("NSE_EQUITY", "BSE_EQUITY"):
        session = calendar.get_session(after, market=market)
        assert [(s.close.isoformat(), s.kind) for s in session] == [("15:30:00", "continuous")]


def test_is_continuous_trading_is_false_during_closing_auction():
    calendar = EventCalendar.bundled(2026)

    assert calendar.is_continuous_trading(datetime(2026, 8, 3, 15, 10), market="NSE_EQUITY_FNO_UNDERLYING")
    # The market is still open through CAS, but it is not continuous trading.
    for minute in (15, 20, 30, 34):
        probe = datetime(2026, 8, 3, 15, minute)
        assert calendar.is_market_open(probe, market="NSE_EQUITY_FNO_UNDERLYING")
    assert not calendar.is_continuous_trading(datetime(2026, 8, 3, 15, 20), market="NSE_EQUITY_FNO_UNDERLYING")
    assert not calendar.is_continuous_trading(datetime(2026, 8, 3, 15, 34), market="NSE_EQUITY_FNO_UNDERLYING")
    # CAS ends 15:35, so the cash segment is shut at 15:36.
    assert not calendar.is_market_open(datetime(2026, 8, 3, 15, 36), market="NSE_EQUITY_FNO_UNDERLYING")

    # Non-F&O equity keeps matching continuously right up to 15:30.
    assert calendar.is_continuous_trading(datetime(2026, 8, 3, 15, 20), market="NSE_EQUITY")
    assert not calendar.is_market_open(datetime(2026, 8, 3, 15, 31), market="NSE_EQUITY")

    assert is_continuous_trading("NSE_EQUITY_FNO_UNDERLYING", at="2026-08-03T15:10:00+05:30")
    assert not is_continuous_trading("NSE_EQUITY_FNO_UNDERLYING", at="2026-08-03T15:20:00+05:30")


def test_closing_auction_session_accessor():
    calendar = EventCalendar.bundled(2026)

    for market in ("NSE_EQUITY_FNO_UNDERLYING", "BSE_EQUITY_FNO_UNDERLYING"):
        auction = calendar.closing_auction_session(datetime(2026, 8, 3, 10, 0), market=market)
        assert auction is not None
        assert (auction.open.isoformat(), auction.close.isoformat()) == ("15:15:00", "15:35:00")

    assert calendar.closing_auction_session(datetime(2026, 7, 31, 10, 0), market="NSE_EQUITY_FNO_UNDERLYING") is None
    assert calendar.closing_auction_session(datetime(2026, 8, 3, 10, 0), market="NSE_EQUITY") is None


def test_index_derivatives_have_no_auction_and_run_to_1540():
    """Para 4.2.3 — index derivatives keep continuous trading to 15:40, no CAS."""
    calendar = EventCalendar.bundled(2026)
    probe = datetime(2026, 8, 3, 15, 35)

    for index, segment in [
        ("NIFTY", "NSE_EQUITY_DERIVATIVES"),
        ("BANKNIFTY", "NSE_EQUITY_DERIVATIVES"),
        ("FINNIFTY", "NSE_EQUITY_DERIVATIVES"),
        ("SENSEX", "BSE_EQUITY_DERIVATIVES"),
        ("BANKEX", "BSE_EQUITY_DERIVATIVES"),
    ]:
        assert calendar.get_session(probe, market=index) == calendar.get_session(probe, market=segment)
        # Still continuously trading at 15:35, when the cash auction has just ended.
        assert calendar.is_continuous_trading(probe, market=index), index
        assert calendar.closing_auction_session(probe, market=index) is None, index
        assert not calendar.is_market_open(datetime(2026, 8, 3, 15, 41), market=index), index


def test_bse_alias_still_resolves_after_the_segment_split():
    calendar = EventCalendar.bundled(2026)
    probe = datetime(2026, 8, 3, 10, 0)

    # Legacy callers passing "BSE" get the cash segment, unchanged by CAS.
    assert calendar.get_session(probe, market="BSE") == calendar.get_session(probe, market="BSE_EQUITY")
    assert [s.close.isoformat() for s in calendar.get_session(probe, market="BSE")] == ["15:30:00"]

    # BSE holidays still resolve, and both new segments inherit them.
    bse_holidays = calendar.holidays(market="BSE", year=2026)
    assert bse_holidays
    assert calendar.holidays(market="BSE_EQUITY_FNO_UNDERLYING", year=2026) == bse_holidays
    assert calendar.holidays(market="BSE_EQUITY_DERIVATIVES", year=2026) == bse_holidays


def test_session_rules_never_create_trading_days():
    """A standing timing regime must not turn weekends or holidays into trading days."""
    calendar = EventCalendar.bundled(2026)

    saturday = datetime(2026, 8, 8, 10, 0)
    assert not calendar.is_trading_day(saturday, market="NSE_EQUITY_FNO_UNDERLYING")
    assert calendar.get_session(saturday, market="NSE_EQUITY_FNO_UNDERLYING") is None

    holiday = calendar.holidays(market="NSE_EQUITY", year=2026)[-1]
    probe = datetime(holiday.year, holiday.month, holiday.day, 10, 0)
    assert not calendar.is_trading_day(probe, market="NSE_EQUITY_FNO_UNDERLYING")


def test_fno_underlying_inherits_cash_segment_events_one_way():
    """The new segment is a subset of NSE_EQUITY, so it observes every equity holiday."""
    calendar = EventCalendar.bundled(2026)
    assert calendar.holidays(market="NSE_EQUITY_FNO_UNDERLYING", year=2026) == calendar.holidays(
        market="NSE_EQUITY", year=2026
    )

    # ...but an event aimed at the subset must not close the whole cash segment.
    calendar._live_events = {
        "subset-only": calendar._normalize_event(
            {
                "id": "subset-only",
                "name": "Subset Only Holiday",
                "category": "EXCHANGE_HOLIDAY",
                "impact": "EXTREME",
                "applies_to": ["NSE_EQUITY_FNO_UNDERLYING"],
                "start": "2026-09-09T00:00:00+05:30",
            }
        )
    }
    probe = datetime(2026, 9, 9, 10, 0)
    assert not calendar.is_trading_day(probe, market="NSE_EQUITY_FNO_UNDERLYING")
    assert calendar.is_trading_day(probe, market="NSE_EQUITY")


def test_fno_underlying_aliases_resolve_without_colliding_with_derivatives():
    calendar = EventCalendar.bundled(2026)
    probe = datetime(2026, 8, 3, 10, 0)

    canonical = calendar.get_session(probe, market="NSE_EQUITY_FNO_UNDERLYING")
    assert calendar.get_session(probe, market="NSE_CASH_FNO") == canonical
    assert calendar.get_session(probe, market="FNO_UNDERLYING") == canonical

    # "FNO" still means the derivatives segment, not the cash underlyings.
    assert calendar.get_session(probe, market="FNO") != canonical
    assert calendar.get_session(probe, market="FNO") == calendar.get_session(probe, market="NSE_EQUITY_DERIVATIVES")


def test_day_specific_session_override_beats_a_standing_rule():
    """A one-off circular for a single day wins over the standing timing regime."""
    calendar = EventCalendar.bundled(2026)
    calendar._live_events = {
        event.id: event
        for event in [
            calendar._normalize_event(
                {
                    "id": "muhurat-2026-08-03",
                    "name": "Special Trading Session",
                    "category": "SPECIAL_SESSION",
                    "impact": "LOW",
                    "applies_to": ["NSE_EQUITY_FNO_UNDERLYING"],
                    "start": "2026-08-03T00:00:00+05:30",
                    "end": "2026-08-03T23:59:59+05:30",
                    "session_override": [
                        {"market": "NSE_EQUITY_FNO_UNDERLYING", "open": "18:00:00", "close": "19:00:00"}
                    ],
                }
            )
        ]
    }

    session = calendar.get_session(datetime(2026, 8, 3, 18, 30), market="NSE_EQUITY_FNO_UNDERLYING")
    assert [(s.open.isoformat(), s.close.isoformat()) for s in session] == [("18:00:00", "19:00:00")]


def test_currency_derivatives_segment_resolves():
    """CDS was declared in SEGMENT_ALIASES but never registered as canonical, so
    every CDS lookup raised "Unknown market input" — including the documented
    quick-start calls."""
    calendar = EventCalendar.bundled(2026)
    probe = datetime(2026, 1, 27, 10, 0)

    for market in ("CDS", "USDINR", "EURINR", "CURRENCY_DERIVATIVES", "NSE_CURRENCY_DERIVATIVES"):
        session = calendar.get_session(probe, market=market)
        assert [(s.open.isoformat(), s.close.isoformat()) for s in session] == [("09:00:00", "17:00:00")]
        assert calendar.holidays(market=market, year=2026)

    # CDS runs to 17:00, well after the equity segment has shut.
    assert calendar.is_market_open(datetime(2026, 1, 27, 16, 30), market="CDS")
    assert not calendar.is_market_open(datetime(2026, 1, 27, 16, 30), market="NSE_EQUITY")


def test_every_declared_segment_resolves():
    """Guards the class of bug above: a segment declared anywhere must resolve."""
    calendar = EventCalendar.bundled(2026)
    declared = set(calendar_module.DEFAULT_SESSIONS) | set(calendar_module.SEGMENT_ALIASES)
    for market in declared:
        assert calendar_module.resolve_market_key(market) in declared, market
        calendar.holidays(market=market, year=2026)


def test_equity_holidays_are_shared_across_nse_and_bse():
    """BSE observes the same equity trading holidays as NSE."""
    calendar = EventCalendar.bundled(2026)
    nse = calendar.holidays(market="NSE_EQUITY", year=2026)

    assert len(nse) == 16
    for market in ("BSE", "BSE_EQUITY", "BSE_EQUITY_FNO_UNDERLYING", "BSE_EQUITY_DERIVATIVES", "NSE_EQUITY_DERIVATIVES"):
        assert calendar.holidays(market=market, year=2026) == nse, market


def test_bank_linked_segments_add_holidays_on_top_of_equity():
    """CDS, IRD and corporate bonds settle through banks, so they close on bank
    holidays that the equity segments trade through — Annual Bank Closing is the
    clearest case."""
    calendar = EventCalendar.bundled(2026)
    equity = set(calendar.holidays(market="NSE_EQUITY", year=2026))

    for market in ("CDS", "NSE_INTEREST_RATE_DERIVATIVES", "NSE_CORPORATE_BONDS"):
        segment = set(calendar.holidays(market=market, year=2026))
        assert equity < segment, market
        assert segment - equity == {date(2026, 2, 19), date(2026, 3, 19), date(2026, 4, 1), date(2026, 8, 26)}

    # Annual Bank Closing: equity trades, CDS does not.
    annual_bank_closing = datetime(2026, 4, 1, 10, 0)
    assert calendar.is_trading_day(annual_bank_closing, market="NSE_EQUITY")
    assert not calendar.is_trading_day(annual_bank_closing, market="CDS")


def test_mcx_evening_session_runs_on_equity_holiday_mornings():
    """MCX is the one segment that diverges: on most equity holidays the morning
    is shut but the evening session still runs from 17:00."""
    calendar = EventCalendar.bundled(2026)
    evening_only = [
        date(2026, 3, 3), date(2026, 3, 26), date(2026, 3, 31), date(2026, 4, 14),
        date(2026, 5, 1), date(2026, 5, 28), date(2026, 6, 26), date(2026, 9, 14),
        date(2026, 10, 20), date(2026, 11, 10), date(2026, 11, 24),
    ]
    for day in evening_only:
        assert day in calendar.holidays(market="NSE_EQUITY", year=2026), day
        assert calendar.is_trading_day(datetime(day.year, day.month, day.day, 18, 0), market="MCX"), day
        session = calendar.get_session(datetime(day.year, day.month, day.day, 18, 0), market="MCX")
        assert [(s.open.isoformat(), s.close.isoformat()) for s in session] == [("17:00:00", "23:30:00")], day
        # Morning is shut even though the evening runs.
        assert not calendar.is_market_open(datetime(day.year, day.month, day.day, 10, 0), market="MCX"), day
        assert calendar.is_market_open(datetime(day.year, day.month, day.day, 18, 0), market="MCX"), day

    # Full MCX holidays stay shut all day.
    for day in [date(2026, 1, 26), date(2026, 4, 3), date(2026, 10, 2), date(2026, 12, 25)]:
        assert not calendar.is_trading_day(datetime(day.year, day.month, day.day, 18, 0), market="MCX"), day


def test_new_year_day_closes_the_commodity_evening_not_the_morning():
    """2026-01-01 is the inverse of the usual pattern: the morning trades and the
    evening is shut, tracking global commodity markets."""
    calendar = EventCalendar.bundled(2026)

    for market in ("MCX", "NSE_COMMODITY_DERIVATIVES"):
        assert calendar.is_market_open(datetime(2026, 1, 1, 10, 0), market=market), market
        assert not calendar.is_market_open(datetime(2026, 1, 1, 20, 0), market=market), market
        # A partial day is not a holiday.
        assert date(2026, 1, 1) not in calendar.holidays(market=market, year=2026), market


def test_out_of_range_dates_are_reported_not_answered_silently(caplog):
    """The bundled range once claimed coverage to 2027-03-24 with no 2027 data, so
    Republic Day 2027 came back as a trading day with no signal at all."""
    calendar = EventCalendar.bundled(2026)

    assert calendar.coverage_start == date(2026, 1, 1)
    assert calendar.coverage_end == date(2026, 12, 25)
    assert calendar.covers(date(2026, 11, 8))
    assert not calendar.covers(date(2027, 1, 26))

    with caplog.at_level("WARNING"):
        calendar.is_trading_day(datetime(2027, 1, 26, 10, 0), market="NSE_EQUITY")
    assert "outside the bundled calendar range" in caplog.text

    # In-range queries stay quiet.
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert not calendar.is_trading_day(datetime(2026, 12, 25, 10, 0), market="NSE_EQUITY")
    assert "outside the bundled calendar range" not in caplog.text


def test_muhurat_trading_makes_a_sunday_a_trading_day():
    """Diwali Laxmi Pujan falls on Sunday 2026-11-08; the Muhurat session runs anyway."""
    calendar = EventCalendar.bundled(2026)
    evening = datetime(2026, 11, 8, 18, 30)

    for market in ("NSE_EQUITY", "NSE_EQUITY_FNO_UNDERLYING", "BSE_EQUITY", "MCX"):
        assert calendar.is_trading_day(evening, market=market), market
        assert calendar.is_market_open(evening, market=market), market
        # Only the ceremonial window trades — the rest of the Sunday is shut.
        assert not calendar.is_market_open(datetime(2026, 11, 8, 12, 0), market=market), market

    events = calendar.events_on("2026-11-08", exchange="NSE_EQUITY")
    assert [e.name for e in events] == ["NSE Muhurat Trading (Diwali Laxmi Pujan)"]
    # Timings are provisional until the exchange circular lands.
    assert events[0].metadata["timings_pending_exchange_circular"] is True


def _fake_refresh(monkeypatch, tmp_path, payload):
    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

    monkeypatch.setattr(
        calendar_module,
        "urlopen",
        lambda request, timeout=10: FakeResponse(json.dumps(payload).encode("utf-8")),
    )
    monkeypatch.setattr(calendar_module.IndiaMarketCalendar, "_cache_path", lambda self: tmp_path / "live_cache.json")














# The three telemetry tests that stood here until 1.4.0 have been deleted along
# with the feature they covered. They asserted that a refresh against an
# AION-owned host sent X-AION-Calendar-Install -- a UUID4 persisted to the user's
# home directory and reused for the life of the machine -- and that it was not
# sent to third-party hosts.
#
# They are worth a note rather than a silent deletion, because their existence
# shows the identifier was deliberate and tested rather than accidental. What
# replaces them is tests/test_no_telemetry.py, which asserts the opposite: that
# no such header can be produced, that no identifier file is written, and that
# the helper functions are gone from the source.
#
# See docs/TELEMETRY_AUDIT.md.


# Four tests stood here until 1.4.1, covering the legacy live-events refresh:
# merging a remote delta, applying session rules from it, surviving an offline
# restart from its cache, and tolerating a malformed payload.
#
# They are removed with the feature. That path fetched from whatever URL it was
# given and merged the result into live answers with no integrity check of any
# kind, while its default endpoint had returned 404 since before 1.4.0 -- so it
# logged an error and did nothing, which is why it survived unnoticed.
#
# What replaces it is the hash-verified store: tests/test_incident_20260626.py
# covers rejection of an unverified payload, and tests/test_no_egress.py covers
# what may reach the network at all.
