import sys as _sys
from datetime import date, datetime
from functools import lru_cache

try:
    from importlib.metadata import version as _pkg_version
    __version__: str = _pkg_version("aion-indian-market-calendar")
except Exception:
    __version__ = "1.3.3"


from . import calendar
from .calendar import (
    CLOSING_AUCTION_EFFECTIVE_FROM,
    EventCalendar,
    IndiaMarketCalendar,
    get_ist_timezone,
)
from .models import (
    SESSION_KIND_CLOSING_AUCTION,
    SESSION_KIND_CONTINUOUS,
    Event,
    EventPolicy,
    MarketEvent,
    SessionRule,
    SessionSegment,
)

# calendar submodule is now the canonical module name (was _calendar)

__all__ = [
    "CLOSING_AUCTION_EFFECTIVE_FROM",
    "SESSION_KIND_CLOSING_AUCTION",
    "SESSION_KIND_CONTINUOUS",
    "Event",
    "EventCalendar",
    "EventPolicy",
    "IndiaMarketCalendar",
    "MarketEvent",
    "SessionRule",
    "SessionSegment",
    "calendar",
    "get_ist_timezone",
    "is_continuous_trading",
    "is_market_open",
    "next_trading_day",
]


@lru_cache(maxsize=4)
def _bundled_calendar(year: int = 2026) -> IndiaMarketCalendar:
    return IndiaMarketCalendar.bundled(year)


def is_market_open(
    market: str = "NSE",
    at: date | datetime | str | None = None,
    *,
    year: int = 2026,
) -> bool:
    calendar = _bundled_calendar(year)
    when = at if at is not None else datetime.now(calendar.tz)
    return calendar.is_market_open(when, market=market)


def is_continuous_trading(
    market: str = "NSE",
    at: date | datetime | str | None = None,
    *,
    year: int = 2026,
) -> bool:
    """True only during continuous order matching, False during a closing auction."""
    calendar = _bundled_calendar(year)
    when = at if at is not None else datetime.now(calendar.tz)
    return calendar.is_continuous_trading(when, market=market)


def next_trading_day(
    market: str = "NSE",
    after: date | datetime | str | None = None,
    *,
    year: int = 2026,
) -> date:
    calendar = _bundled_calendar(year)
    when = after if after is not None else datetime.now(calendar.tz)
    return calendar.next_trading_day(when, market=market)
