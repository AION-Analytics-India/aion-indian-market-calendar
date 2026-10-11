# Check an Indian market session in Python

A session-aware application needs more than a weekday check. Start with a named market segment, a timestamp carrying its timezone, and a known data-coverage interval. The public package supplies the session-checking interface; this example deliberately runs offline. [Package and usage](https://pypi.org/project/aion-indian-market-calendar/).

Install the tested distribution in a virtual environment:

```sh
python -m pip install aion-indian-market-calendar==1.4.1
```

The distribution declares Python >=3.10. This example was tested with Python 3.14.7 on macOS arm64; other runtimes were not tested here. [Distribution metadata](https://pypi.org/pypi/aion-indian-market-calendar/json).

Save the following as `offline_session_checks.py` and run `python examples/offline_session_checks.py`. Set the cache to a writable local directory before importing. The explicit offline flag prevents the package's normal public-data refresh. Offline results cannot include subsequently announced closures. [Offline configuration](https://pypi.org/project/aion-indian-market-calendar/).

```python
"""Public PyPI 1.4.1: deterministic offline session checks, not live exchange status."""
import os
from pathlib import Path
# Configure before importing the package. Offline is explicit, not the default.
os.environ['AION_IN_CALENDAR_OFFLINE'] = '1'
os.environ.setdefault('AION_IN_CALENDAR_CACHE', str(Path.cwd() / '.calendar-cache'))
from aion_indian_market_calendar import IndiaMarketCalendar, is_market_open

def run():
    cases = [
        ('NSE', '2026-01-27T10:00:00+05:30', True),
        ('NSE', '2026-01-27T04:30:00Z', True),
        ('NSE', '2026-01-26T10:00:00+05:30', False),
        ('NSE', '2026-01-25T10:00:00+05:30', False),
        ('NSE', '2026-01-27T18:00:00+05:30', False),
        ('BSE_EQUITY', '2026-01-27T10:00:00+05:30', True),
        ('MCX', '2026-01-27T10:00:00+05:30', True),
        ('NSE_CURRENCY_DERIVATIVES', '2026-01-27T10:00:00+05:30', True),
    ]
    results = []
    for market, at, expected in cases:
        value = is_market_open(market, at=at, year=2026)
        assert value is expected
        results.append({'market': market, 'at': at, 'open': value})
    cal = IndiaMarketCalendar.bundled(2026)
    assert str(cal.coverage_start) == '2026-01-01'
    assert str(cal.coverage_end) == '2026-12-25'
    assert cal.covers(__import__('datetime').date(2027, 1, 26)) is False
    try:
        is_market_open('NOT_A_MARKET', at=cases[0][1])
    except ValueError:
        pass
    else:
        raise AssertionError('Unknown market must fail')
    return results

if __name__ == '__main__':
    import json
    print(json.dumps(run(), indent=2))
```

## Reading the result

The program checks an ordinary January session, the bundled Republic Day closure, a weekend, an out-of-session time, and equivalent UTC/IST timestamps. The first two results are True and True; the holiday and weekend results are False. BSE_EQUITY, MCX and NSE_CURRENCY_DERIVATIVES each return True at the selected example timestamp. These are deterministic package-data results, not live exchange-status measurements. [Package](https://pypi.org/project/aion-indian-market-calendar/).

## Segment and time pitfalls

The installed distribution exposes NSE, NSE_EQUITY, NSE_EQUITY_FNO_UNDERLYING, NSE_EQUITY_DERIVATIVES, BSE_EQUITY, BSE_EQUITY_FNO_UNDERLYING, BSE_EQUITY_DERIVATIVES, NSE_CURRENCY_DERIVATIVES, NSE_COMMODITY_DERIVATIVES, MCX, NSE_INTEREST_RATE_DERIVATIVES and NSE_CORPORATE_BONDS session definitions. Use the documented segment rather than inventing a shorthand such as NSE_FO. The example tests four named markets only; it does not certify every session rule. [Published package](https://pypi.org/project/aion-indian-market-calendar/).

Timezone-aware inputs are converted to Asia/Kolkata. Naive datetimes are interpreted in that timezone; a date alone becomes midnight and is unsuitable for asking whether an intraday session is open. The bundled coverage observed in this version is 2026-01-01 through 2026-12-25. Check covers before interpreting an out-of-coverage False as a confirmed closure. [Public implementation](https://github.com/AION-Analytics-India/aion-indian-market-calendar).

## FAQ and limits

Does this prove the exchange is reachable? No. Does offline mean the package never networks by default? No, the offline flag is explicit. Does an alias distinguish an auction from continuous trading? Not by itself; select the appropriate public session API and segment. Never turn a calendar boolean into a trading recommendation. Verify current special-session notices with the exchange; the example does not independently certify them. [Package documentation](https://pypi.org/project/aion-indian-market-calendar/), [NSE holidays and notices](https://www.nseindia.com/resources/exchange-communication-holidays).

For questions or a reproducible calendar defect, use the existing repository's contribution process and include the public package version, segment and timezone-aware timestamp. Omit credentials and private account data. [Repository](https://github.com/AION-Analytics-India/aion-indian-market-calendar).
