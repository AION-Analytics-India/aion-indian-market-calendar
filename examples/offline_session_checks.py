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
