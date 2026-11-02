import sys as _sys
from datetime import date, datetime
from functools import lru_cache

try:
    from importlib.metadata import version as _pkg_version
    __version__: str = _pkg_version("aion-indian-market-calendar")
except Exception:
    __version__ = "1.7.0"


from . import calendar
from .calendar import (
    CLOSING_AUCTION_EFFECTIVE_FROM,
    EventCalendar,
    IndiaMarketCalendar,
    commodity_close,
    get_ist_timezone,
    is_us_daylight_saving,
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
from . import microstructure
from .microstructure import (
    CLOSED,
    CLOSING_AUCTION,
    CONTINUOUS,
    MUHURAT_TRADING,
    POST_CLOSE,
    PRE_OPEN,
    get_expiry_day,
    get_market_phase,
    is_muhurat_trading,
    is_settlement_day,
    is_trading_day,
    muhurat_session,
    settlement_holidays,
)

# calendar submodule is now the canonical module name (was _calendar)

__all__ = [
    "commodity_close",
    "is_us_daylight_saving",
    "CLOSED",
    "CLOSING_AUCTION",
    "CONTINUOUS",
    "MUHURAT_TRADING",
    "POST_CLOSE",
    "PRE_OPEN",
    "get_expiry_day",
    "get_market_phase",
    "is_muhurat_trading",
    "is_settlement_day",
    "is_trading_day",
    "microstructure",
    "muhurat_session",
    "settlement_holidays",
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
    """Return whether *market* is open using the module-level API.

    This helper is market-first; an ``IndiaMarketCalendar`` instance instead
    uses ``calendar.is_market_open(at, market=market)``.
    """
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
