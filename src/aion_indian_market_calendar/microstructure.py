"""Settlement days, intraday phases, derivative expiries and Muhurat trading.

Four questions that a holiday list alone does not answer, each built on the same
verified data as the rest of the package. Nothing here fetches anything or reads
a file of its own: every answer comes from :class:`IndiaMarketCalendar`, so a
holiday added through the verified data refresh moves settlement days and
expiry dates without a new release.

Sources, checked 2026-10-25
---------------------------
* **Settlement (clearing) holidays.** NSE publishes one clearing-holiday list per
  segment. For 2026 the lists for CM, F&O, CD, IRD, CBM, COM, MF and SLBS are
  identical and equal, date for date, to the bundled NSE currency-derivatives
  closures (20 dates). Equity therefore has four days that trade but do not
  settle: 19 Feb, 19 Mar, 1 Apr (annual bank closing) and 26 Aug.
* **Expiry days.** NSE circular NSE/FAOP/68747 (25 June 2025): NIFTY weekly on
  the Tuesday of the week; NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY and NIFTYNXT50
  monthly on the last Tuesday of the month. BSE notice 20250623-59 (23 June
  2025): SENSEX weekly on the Thursday of the week, SENSEX monthly on the last
  Thursday. Both apply to contracts expiring from 1 September 2025, and both
  illustrate a holiday expiry moving to the previous trading day.
* **Phases.** The pre-open, closing auction and post-close windows are read
  from the bundled ``market_timings`` and ``session_rules`` (SEBI circulars cited
  there).

What this module will not do
----------------------------
It refuses rather than guesses. A date outside the bundled data range raises
``ValueError`` for settlement and expiry questions, because without holiday
records the honest answer is unknown, not "weekday". An index not listed in
``EXPIRY_RULES`` raises too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache

from .calendar import IndiaMarketCalendar, _attach_timezone, _coerce_datetime, get_ist_timezone
from .models import SESSION_KIND_CLOSING_AUCTION

__all__ = [
    "PRE_OPEN",
    "CONTINUOUS",
    "CLOSING_AUCTION",
    "POST_CLOSE",
    "MUHURAT_TRADING",
    "CLOSED",
    "EXPIRY_RULES",
    "EXPIRY_RULES_EFFECTIVE_FROM",
    "ExpiryRule",
    "MuhuratSession",
    "get_expiry_day",
    "get_market_phase",
    "is_muhurat_trading",
    "is_settlement_day",
    "is_trading_day",
    "muhurat_session",
    "settlement_holidays",
]

PRE_OPEN = "PRE_OPEN"
CONTINUOUS = "CONTINUOUS"
CLOSING_AUCTION = "CLOSING_AUCTION"
POST_CLOSE = "POST_CLOSE"
MUHURAT_TRADING = "MUHURAT_TRADING"
CLOSED = "CLOSED"

#: NSE Clearing's holiday list for every segment equals the closures bundled for
#: this segment (verified for 2026 against NSE's published clearing holidays).
_SETTLEMENT_REFERENCE_SEGMENT = "NSE_CURRENCY_DERIVATIVES"

#: Contracts expiring before this date followed the previous expiry days.
EXPIRY_RULES_EFFECTIVE_FROM = date(2025, 9, 1)

_TUESDAY = 1
_THURSDAY = 3


@dataclass(frozen=True)
class ExpiryRule:
    """When one index's contracts of one periodicity expire."""

    segment: str
    weekday: int
    #: "weekly": that weekday of every week; "monthly": the last one in the month.
    periodicity: str
    source: str


_NSE_SOURCE = "NSE circular NSE/FAOP/68747 dated 2025-06-25"
_BSE_SOURCE = "BSE notice 20250623-59 dated 2025-06-23"

EXPIRY_RULES: dict[str, dict[str, ExpiryRule]] = {
    "NIFTY": {
        "weekly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "weekly", _NSE_SOURCE),
        "monthly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "monthly", _NSE_SOURCE),
    },
    "BANKNIFTY": {"monthly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "monthly", _NSE_SOURCE)},
    "FINNIFTY": {"monthly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "monthly", _NSE_SOURCE)},
    "MIDCPNIFTY": {"monthly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "monthly", _NSE_SOURCE)},
    "NIFTYNXT50": {"monthly": ExpiryRule("NSE_EQUITY_DERIVATIVES", _TUESDAY, "monthly", _NSE_SOURCE)},
    "SENSEX": {
        "weekly": ExpiryRule("BSE_EQUITY_DERIVATIVES", _THURSDAY, "weekly", _BSE_SOURCE),
        "monthly": ExpiryRule("BSE_EQUITY_DERIVATIVES", _THURSDAY, "monthly", _BSE_SOURCE),
    },
}

_INDEX_ALIASES = {
    "NIFTY50": "NIFTY",
    "NIFTY 50": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "NIFTY BANK": "BANKNIFTY",
    "NIFTYBANK": "BANKNIFTY",
    "NIFTY NEXT 50": "NIFTYNXT50",
    "NIFTY FINANCIAL SERVICES": "FINNIFTY",
    "NIFTY MIDCAP SELECT": "MIDCPNIFTY",
}


@dataclass(frozen=True)
class MuhuratSession:
    """The Diwali Muhurat session for one market on one day."""

    market: str
    open: time
    close: time
    #: True while the exchange has not yet notified the timings.
    provisional: bool
    event_id: str


@lru_cache(maxsize=4)
def _calendar(year: int) -> IndiaMarketCalendar:
    return IndiaMarketCalendar.bundled(year)


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _noon(cal: IndiaMarketCalendar, day: date) -> datetime:
    return _attach_timezone(datetime.combine(day, time(12, 0)), cal.tz)


def _require_coverage(cal: IndiaMarketCalendar, day: date, question: str) -> None:
    if not cal.covers(day):
        raise ValueError(
            f"{day.isoformat()} is outside the bundled data range "
            f"({cal.coverage_start} to {cal.coverage_end}); there are no holiday records "
            f"there, so the {question} is unknown rather than a weekday guess"
        )


# --- trading and settlement days ---------------------------------------------

def is_trading_day(
    day: date | datetime | str,
    market: str = "NSE",
    *,
    calendar: IndiaMarketCalendar | None = None,
) -> bool:
    """Does *market* trade at all on this calendar day?

    Weekends are closed unless a special session (Muhurat) is scheduled; exchange
    holidays are closed. Accepts a date, a datetime or an ISO string.
    """
    when = _as_date(day)
    cal = calendar or _calendar(when.year)
    return cal.is_trading_day(_noon(cal, when), market=market)


def settlement_holidays(year: int = 2026, *, calendar: IndiaMarketCalendar | None = None) -> list[date]:
    """NSE Clearing's settlement holidays for *year* (weekdays only).

    The same list applies to every segment. On these days nothing settles, even
    in segments that trade (equity trades on four of them in 2026).
    """
    cal = calendar or _calendar(year)
    return cal.holidays(market=_SETTLEMENT_REFERENCE_SEGMENT, year=year)


def is_settlement_day(
    day: date | datetime | str,
    *,
    calendar: IndiaMarketCalendar | None = None,
) -> bool:
    """True if NSE Clearing settles on this day.

    Not the same as a trading day: 1 April 2026 (annual bank closing) is a
    trading day for equity and not a settlement day. Raises ``ValueError``
    outside the bundled data range.
    """
    when = _as_date(day)
    cal = calendar or _calendar(when.year)
    _require_coverage(cal, when, "settlement status")
    if when.weekday() >= 5:
        return False
    return when not in set(settlement_holidays(when.year, calendar=cal))


# --- Muhurat trading -----------------------------------------------------------

def _is_muhurat_event(event) -> bool:
    tags = {str(tag).lower() for tag in (event.tags or [])}
    return "muhurat" in tags or "MUHURAT" in event.id.upper() or "MUHRAT" in event.id.upper()


def muhurat_session(
    day: date | datetime | str,
    market: str = "NSE",
    *,
    calendar: IndiaMarketCalendar | None = None,
) -> MuhuratSession | None:
    """The Muhurat session for *market* on *day*, or ``None`` if there is none."""
    when = _as_date(day)
    cal = calendar or _calendar(when.year)
    key = cal._resolve_market_key(market)
    lineage = set(cal._market_lineage(key))
    for event in cal.all_events():
        if not _is_muhurat_event(event) or not cal._event_active_on_day(event, when):
            continue
        for segment in event.session_override or []:
            try:
                segment_key = cal._resolve_market_key(segment.market)
            except ValueError:
                continue
            if segment_key in lineage:
                metadata = event.metadata or {}
                return MuhuratSession(
                    market=segment_key,
                    open=segment.open,
                    close=segment.close,
                    provisional=bool(metadata.get("timings_provisional")),
                    event_id=event.id,
                )
    return None


def is_muhurat_trading(
    day: date | datetime | str,
    market: str = "NSE",
    *,
    calendar: IndiaMarketCalendar | None = None,
) -> bool:
    """True if *market* holds a Muhurat (Diwali) session on *day*.

    The date is confirmed by the exchange well ahead; the timings often are
    not. Use :func:`muhurat_session` to see the window and whether it is still
    provisional.
    """
    return muhurat_session(day, market, calendar=calendar) is not None


# --- intraday phases ------------------------------------------------------------

def _clock(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(str(value))


def _window(block: dict | None) -> tuple[time, time] | None:
    if not isinstance(block, dict):
        return None
    start, end = _clock(block.get("open")), _clock(block.get("close"))
    if start is None or end is None:
        return None
    return start, end


def _timings_for(cal: IndiaMarketCalendar, key: str) -> dict:
    for candidate in cal._market_lineage(key):
        block = cal.market_timings.get(candidate)
        if isinstance(block, dict):
            return block
    return {}


def _pre_open_window(timings: dict, day: date) -> tuple[time, time] | None:
    revised = timings.get("pre_open_revised")
    if isinstance(revised, dict):
        effective = revised.get("effective_from")
        if effective and day >= date.fromisoformat(effective):
            first = _window(revised.get("session_1_order_entry_limit_and_market"))
            last = _window(revised.get("session_4_transition_to_cts"))
            if first and last:
                return first[0], last[1]
    # MCX publishes an order-cancellation window before the open instead.
    return _window(timings.get("pre_open")) or _window(timings.get("special_session"))


def _post_close_window(timings: dict, day: date) -> tuple[time, time] | None:
    for key, block in timings.items():
        if key.startswith("revised_from_") and isinstance(block, dict) and "post_close" in block:
            effective = block.get("effective_from")
            if effective and day >= date.fromisoformat(effective):
                return _window(block["post_close"])
    post = timings.get("post_close")
    if not isinstance(post, dict):
        return None
    effective = post.get("effective_from")
    if effective and day < date.fromisoformat(effective):
        return _window(post.get("previous"))
    return _window(post)


def get_market_phase(
    at: date | datetime | str | None = None,
    market: str = "NSE",
    *,
    calendar: IndiaMarketCalendar | None = None,
) -> str:
    """Which phase *market* is in at *at*.

    Returns one of ``PRE_OPEN``, ``CONTINUOUS``, ``CLOSING_AUCTION``,
    ``POST_CLOSE``, ``MUHURAT_TRADING`` or ``CLOSED``. Windows are half-open:
    a phase owns its start minute, not its end minute, so 15:15 in an F&O
    underlying stock is ``CLOSING_AUCTION``, not ``CONTINUOUS``.

    A naive datetime is read as IST, as everywhere else in this package. Phases
    are only as detailed as the data: segments without published pre-open or
    post-close windows (derivatives, currency) go straight from ``CLOSED`` to
    ``CONTINUOUS``.
    """
    when = at if at is not None else datetime.now(get_ist_timezone())
    cal = calendar or _calendar(_as_date(when).year)
    local = _coerce_datetime(when, cal.tz)
    day, clock = local.date(), local.timetz().replace(tzinfo=None)
    key = cal._resolve_market_key(market)

    muhurat = muhurat_session(day, key, calendar=cal)
    if muhurat is not None:
        return MUHURAT_TRADING if muhurat.open <= clock < muhurat.close else CLOSED
    if not cal.is_trading_day(local, market=key):
        return CLOSED

    timings = _timings_for(cal, key)
    pre_open = _pre_open_window(timings, day)
    if pre_open and pre_open[0] <= clock < pre_open[1]:
        return PRE_OPEN

    for segment in cal.get_session(local, market=key) or []:
        if segment.open <= clock < segment.close:
            return CLOSING_AUCTION if segment.kind == SESSION_KIND_CLOSING_AUCTION else CONTINUOUS

    post_close = _post_close_window(timings, day)
    if post_close and post_close[0] <= clock < post_close[1]:
        return POST_CLOSE
    return CLOSED


# --- derivative expiries ------------------------------------------------------

def _resolve_index(index_name: str) -> str:
    name = " ".join(index_name.strip().upper().replace("_", " ").split())
    name = _INDEX_ALIASES.get(name, name.replace(" ", ""))
    name = _INDEX_ALIASES.get(name, name)
    if name not in EXPIRY_RULES:
        raise ValueError(
            f"No sourced expiry rule for {index_name!r}. Supported: {', '.join(sorted(EXPIRY_RULES))}"
        )
    return name


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    cursor = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    while cursor.weekday() != weekday:
        cursor -= timedelta(days=1)
    return cursor


def _adjust_for_holiday(rule: ExpiryRule, scheduled: date, cal_for) -> date:
    """Move a holiday expiry to the previous trading day, as both exchanges do."""
    cursor = scheduled
    for _ in range(10):
        cal = cal_for(cursor)
        _require_coverage(cal, cursor, "expiry day")
        if cal.is_trading_day(_noon(cal, cursor), market=rule.segment):
            return cursor
        cursor -= timedelta(days=1)
    raise ValueError(f"no trading day within ten days before {scheduled.isoformat()}; the holiday data is wrong")


def get_expiry_day(
    index_name: str,
    day: date | datetime | str | None = None,
    *,
    contract: str | None = None,
    calendar: IndiaMarketCalendar | None = None,
) -> date:
    """The expiry date of the nearest *index_name* contract expiring on or after *day*.

    ``contract`` is ``"weekly"`` or ``"monthly"``. It defaults to weekly where a
    weekly contract exists (NIFTY, SENSEX) and monthly otherwise. BANKNIFTY has
    no weekly contract since November 2024.

    Rules: NIFTY weekly Tuesday; NSE monthly contracts the last Tuesday; SENSEX
    weekly Thursday and monthly the last Thursday. A scheduled expiry that falls
    on a trading holiday moves to the previous trading day. Raises ``ValueError``
    for dates before 1 September 2025, for unknown indices, and when the date
    needed is outside the bundled holiday data.

    >>> get_expiry_day("NIFTY", "2026-10-25")          # doctest: +SKIP
    datetime.date(2026, 10, 27)
    """
    name = _resolve_index(index_name)
    rules = EXPIRY_RULES[name]
    periodicity = (contract or ("weekly" if "weekly" in rules else "monthly")).strip().lower()
    if periodicity not in rules:
        raise ValueError(f"{name} has no {periodicity} contract. Available: {', '.join(sorted(rules))}")
    rule = rules[periodicity]

    start = _as_date(day) if day is not None else datetime.now(get_ist_timezone()).date()
    if start < EXPIRY_RULES_EFFECTIVE_FROM:
        raise ValueError(
            f"expiry rules here apply from {EXPIRY_RULES_EFFECTIVE_FROM.isoformat()} "
            f"({rule.source}); earlier contracts followed different expiry days"
        )

    def cal_for(when: date) -> IndiaMarketCalendar:
        return calendar or _calendar(when.year)

    if rule.periodicity == "weekly":
        scheduled = start + timedelta(days=(rule.weekday - start.weekday()) % 7)
        step = lambda d: d + timedelta(days=7)  # noqa: E731
    else:
        scheduled = _last_weekday_of_month(start.year, start.month, rule.weekday)

        def step(d: date) -> date:
            return _last_weekday_of_month(d.year + (d.month == 12), d.month % 12 + 1, rule.weekday)

    for _ in range(3):
        expiry = _adjust_for_holiday(rule, scheduled, cal_for)
        if expiry >= start:
            return expiry
        scheduled = step(scheduled)
    raise RuntimeError("expiry search did not converge")  # pragma: no cover
