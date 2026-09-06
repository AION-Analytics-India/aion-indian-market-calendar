# AION India Market Calendar

[![PyPI](https://img.shields.io/pypi/v/aion-indian-market-calendar)](https://pypi.org/project/aion-indian-market-calendar/)
[![Downloads](https://img.shields.io/pypi/dm/aion-indian-market-calendar)](https://pypi.org/project/aion-indian-market-calendar/)
[![Python](https://img.shields.io/pypi/pyversions/aion-indian-market-calendar)](https://pypi.org/project/aion-indian-market-calendar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**One question, answered cleanly across every Indian exchange segment: is this market open right now, on this date, at this time?**

Over **7,400 downloads** on PyPI. No API key. Works offline.

```bash
pip install aion-indian-market-calendar
```

```python
from aion_indian_market_calendar import is_market_open, next_trading_day

is_market_open("NSE")                       # right now
is_market_open("MCX", "2026-01-26")         # Republic Day, so False
next_trading_day("NSE", "2026-01-23")       # the next session
```

## Why this exists

Indian exchanges do not share one clock. NSE equity opens at 09:00, F&O at
09:15, and Currency Derivatives runs until 17:00, ninety minutes past the equity
close. Muhurat is a single ceremonial session on a date that moves every year.

Most calendar libraries flatten all of that into one set of hours, and are
quietly wrong for a third of the trading day.

## Segments covered

| Segment | Session, IST |
|---|---|
| NSE Equity | 09:00 to 15:30 |
| NSE F&O | 09:15 to 15:30 |
| NSE Currency Derivatives (CDS) | 09:00 to 17:00 |
| BSE | 09:15 to 15:30 |
| MCX | 09:00 to 23:30 |
| NSE Commodity Derivatives | covered |
| Muhurat trading | covered, date moves annually |

**CDS is the differentiator.** Currency Derivatives is the segment most market
calendar packages miss or get wrong, and it is ninety minutes longer than the
equity session that libraries tend to assume.

## API

```python
is_market_open(segment, datetime)      # is trading live at this instant
is_trading_day(datetime, market)       # is this a session day at all
is_continuous_trading(...)             # true only during continuous matching,
                                       # false during a closing auction
next_trading_day(market, after)
holidays(segment)
IndiaMarketCalendar.bundled(year)      # full calendar object
```

Dates accept a `date`, a `datetime`, or an ISO string.

## Details

- MIT licensed, Python 3.8 and above
- No API key, no account, no network call at runtime
- Holiday data is bundled, so it works offline
- Distinguishes continuous trading from the closing auction, which matters if
  you are timing order submission rather than just checking the date

## Documentation

Full write-up, including a comparison against `pandas_market_calendars`:
[dashboard.aiondashboard.site/open-source/indian-market-calendar](https://dashboard.aiondashboard.site/open-source/indian-market-calendar)

## Contributing

Holiday corrections are the most useful contribution and need no code. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Related

- [aion-lithuanian-market-calendar](https://github.com/AION-Analytics-India/aion-lithuanian-market-calendar) — the Lithuanian sibling
- [aion-indian-market-intelligence](https://github.com/AION-Analytics-India/aion-indian-market-intelligence) — macro event to sector impact

## Licence

MIT. See [LICENSE](LICENSE).

---

Built by [AION Analytics (India)](https://dashboard.aiondashboard.site).
India-native market-intelligence and execution-integrity infrastructure.
Information, not advice.

If this saves you an afternoon of exchange-timing edge cases, a star is
appreciated.

---

**We're hiring a communication architect.** We don't read CVs — we read code. The challenge *is* the application: read this package, then explain it to someone who has never heard of us. [The full challenge](https://dashboard.aiondashboard.site/careers).
