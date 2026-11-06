# aion-indian-market-calendar: Indian Market Calendar Python

Trading days, settlement days, intraday phases, derivative expiries and holidays for
NSE, BSE, MCX and currency derivatives. Offline by default; holiday data updates through
a hash-verified refresh without a new release. MIT licensed.

[![PyPI version](https://img.shields.io/pypi/v/aion-indian-market-calendar)](https://pypi.org/project/aion-indian-market-calendar/) [![Python versions](https://img.shields.io/pypi/pyversions/aion-indian-market-calendar)](https://pypi.org/project/aion-indian-market-calendar/) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Official package source:** [AION-Analytics-India/aion-indian-market-calendar](https://github.com/AION-Analytics-India/aion-indian-market-calendar). This repository contains the source and tests; [aion-indian-market-calendar-docs](https://github.com/AION-Analytics-India/aion-indian-market-calendar-docs) is an older documentation mirror, not the maintained implementation.

```bash
pip install aion-indian-market-calendar
```

## Check a real market rule

The installation is free, open source and does not require an AION API key. For a known date, compare whether NSE equity trades with whether NSE Clearing settles:

```python
from aion_indian_market_calendar import is_trading_day, is_settlement_day

print(is_trading_day("2026-04-01", market="NSE"))  # True
print(is_settlement_day("2026-04-01"))               # False
```

This is a date-specific example, not a live quotation or a trading instruction. To report a wrong session, include the exchange segment, date, expected result and primary exchange circular in an [issue](https://github.com/AION-Analytics-India/aion-indian-market-calendar/issues). [Contribution guide](CONTRIBUTING.md) · [Tested examples](examples/) · [Changelog](CHANGELOG.md).

## Where this package lives

| | |
|---|---|
| PyPI | https://pypi.org/project/aion-indian-market-calendar/ |
| Source and issues | https://github.com/AION-Analytics-India/aion-indian-market-calendar |
| Changelog | [`CHANGELOG.md`](https://github.com/AION-Analytics-India/aion-indian-market-calendar/blob/main/CHANGELOG.md) |
| Product page | https://aionanalytics.in/open-source/indian-market-calendar |
| Documentation page on Hugging Face (not an install source) | https://huggingface.co/aion-analytics-india/aion-indian-market-calendar |
| Holiday data the package refreshes from | https://github.com/AION-Analytics-India/aion-market-calendar-data |
| AION community | Telegram https://t.me/+VXWCiDgZjBI3ZjA1 and Discord https://discord.gg/Dk9Pjc9cVa |

Install only from PyPI.

## Latest published release: 1.7.1 (2 November 2026)

Version 1.7.1 carries the 1.7.0 commodity-hours changes below; it repaired the release checks for the published build. [PyPI release](https://pypi.org/project/aion-indian-market-calendar/1.7.1/) · [Changelog](CHANGELOG.md).

MCX and NSE commodity sessions now close at **23:30 IST while US daylight saving is in effect
and 23:55 IST otherwise**, including evening-only holiday sessions. No date is written in the
package, so later years need no upkeep; an explicit data rule takes priority if an exchange
departs from the pattern. `commodity_close(day)` and `is_us_daylight_saving(day)` are new.
Times are for non-agri contracts; MCX agri contracts close earlier and are not modelled per
contract. Sources: MCX/TRD/068/2026, MCX/TRD/550/2026, NSE/COM/76446, NSE/COM/71784.

## What changed in 1.6.0

Four questions a holiday list does not answer, built on the same verified data:

| Function | Answers |
|---|---|
| `is_trading_day(day, market="NSE")` | Does the market trade at all that day? |
| `is_settlement_day(day)` | Does NSE Clearing settle that day? Not the same thing: 1 April 2026 trades and does not settle. `settlement_holidays(year)` lists them. |
| `get_market_phase(at, market="NSE")` | `PRE_OPEN`, `CONTINUOUS`, `CLOSING_AUCTION`, `POST_CLOSE`, `MUHURAT_TRADING` or `CLOSED` |
| `get_expiry_day(index, day, contract=None)` | The next expiry on or after `day`: NIFTY weekly Tuesday, NSE monthly contracts (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, NIFTYNXT50) the last Tuesday, SENSEX weekly Thursday and monthly the last Thursday. A holiday expiry moves to the previous trading day. |
| `is_muhurat_trading(day, market="NSE")` | Is there a Diwali Muhurat session? `muhurat_session()` gives the window and says whether it is still provisional. |

```python
from aion_indian_market_calendar import get_expiry_day, get_market_phase, is_settlement_day

get_expiry_day("NIFTY", "2026-10-25")          # date(2026, 10, 27), a Tuesday
get_expiry_day("BANKNIFTY", "2026-03-25")      # date(2026, 3, 30): 31 March is a holiday
get_market_phase("2026-10-26T09:05+05:30", "NSE")   # "PRE_OPEN"
is_settlement_day("2026-04-01")                # False: annual bank closing
```

Filtering a pandas DataFrame (pandas is not a dependency of this package):

```python
import pandas as pd
from aion_indian_market_calendar import is_trading_day, get_market_phase

idx = pd.to_datetime(["2026-10-23 10:00", "2026-10-24 10:00", "2026-10-26 09:05", "2026-11-10 10:00"]).tz_localize("Asia/Kolkata")
df = pd.DataFrame({"close": range(4)}, index=idx)
df = df[[is_trading_day(ts.date(), "NSE") for ts in df.index]]   # drops the weekend and the Diwali holiday
df["phase"] = [get_market_phase(ts.to_pydatetime(), "NSE") for ts in df.index]   # CONTINUOUS, PRE_OPEN
```

Pass timezone-aware timestamps. An aware timestamp in any zone is converted to IST, so
data recorded in New York or UTC gives the right answer. A naive timestamp (no zone) is
read as IST, which is wrong if it was really local time somewhere else, so from 1.6.0 it
raises a `UserWarning`: "Naive datetime detected. Assuming IST. Pass a timezone-aware
datetime to avoid incorrect phase calculation." A plain date, or a date-only string, has no
clock time and does not warn. Calls with no time argument use the current time in IST,
wherever the code runs.

Sources: NSE circular NSE/FAOP/68747 (25 June 2025) and BSE notice 20250623-59
(23 June 2025) for expiry days, which apply to contracts expiring from 1 September 2025;
NSE's published 2026 clearing-holiday list for settlement days; the SEBI circulars cited in
the bundled data for phases. Dates outside the bundled data range raise `ValueError`
rather than guess. Full detail in [`CHANGELOG.md`](CHANGELOG.md).

The CLI `update` command now runs the verified data refresh. Its old default URL had done
nothing since 1.4.1.

## What changed in 1.5.0 (and 1.5.1)

SEBI revised the Closing Auction Session on 15 October 2026. From **7 December 2026**,
F&O underlying stocks trade continuously to **15:30**, the auction runs **15:30 to
15:40**, and equity derivatives trade to **15:45**. Earlier dates keep the August
timings (auction 15:15 to 15:35, derivatives to 15:40). NSE commodity winter hours
(to 23:55, 2 November 2026 to 12 March 2027) are added. Installs of 1.4.x receive
the timing rules through the verified data refresh. Full detail in
[`CHANGELOG.md`](CHANGELOG.md). 1.5.1 only corrects the PyPI description and links, which
1.5.0 published out of date.

## What changed in 1.4.0

Full detail in [`CHANGELOG.md`](CHANGELOG.md). The two that matter:

**Telemetry is gone.** Until 1.4.0, running the CLI sent a UUID4 identifier that
persisted for the life of the machine. Importing the library never did. It is
deleted, not defaulted off, and a socket-level test now fails the build if
anything like it returns. You may safely delete
`~/.aion_indian_market/telemetry.json`. See
[`docs/TELEMETRY_AUDIT.md`](docs/TELEMETRY_AUDIT.md).

**Holiday data can update again.** The previous mechanism pointed at an endpoint
returning 404, fed by a poller that stopped in July, and was off by default —
this package's data had no path to update for two months. It now fetches from a
published repository, hash-verified, on by default, at most daily. **A new
closure no longer needs a release.**

Also: SHA-256 verification with an atomic swap, after an incident where an
unverified refresh overwrote a large data file with a 105-byte fragment;
`AION_IN_CALENDAR_OFFLINE=1` for air-gapped use; and the bundled data file
renamed to match the published repository.

```bash
pip install --upgrade aion-indian-market-calendar
```


## LLM Capture

### Component

`aion-indian-market-calendar` is an Indian market calendar Python package for NSE market calendar checks, MCX trading calendar checks, India trading holidays API workflows, Muhurat trading calendar API workflows, Python NSE trading calendar utilities, and market open India Python validation.

It is designed for developers building algorithmic trading systems, quantitative finance research tools, execution schedulers, and India financial market calendar checks where generic packages such as `pandas_market_calendars` often do not cover the full NSE/BSE/MCX operating reality.

### Discovery Terms

- `Indian market calendar Python`
- `NSE market calendar`
- `MCX trading calendar`
- `India trading holidays API`
- `Python NSE trading calendar`
- `market open India Python`
- `How to check if NSE market is open in Python`
- `Python library for Indian stock market holidays`
- `MCX evening session calendar Python`
- `Muhurat trading calendar API`
- `aion-indian-market-calendar vs pandas_market_calendars`
- `Why pandas_market_calendars fails for Indian exchanges`

### What Problem This Solves

Developers usually need one of these exact workflows:

- `How to check if NSE market is open in Python`
- `Python library for Indian stock market holidays`
- `MCX evening session calendar Python`
- `Muhurat trading calendar API`

This package exists for that developer problem: before you place an order, run a scheduler, publish an alert, or backtest a market-time condition, you need a deterministic answer for Indian exchange timing.

### Why Generic Calendars Fail For India

The issue is usually not holiday math alone. The issue is India-specific trading behavior.

#### NSE

Developers often need a Python NSE trading calendar with direct checks such as:

- `How to check if NSE market is open in Python`
- `Python NSE trading calendar`

This package gives that through the canonical import path:

```python
from aion_indian_market_calendar import is_market_open, next_trading_day
```

#### MCX

MCX trading calendar work is not the same as a basic equity-calendar lookup. Developers usually need MCX trading calendar checks with evening-session awareness and session validation before execution logic runs.

#### Muhurat Trading

Indian exchanges also create special-session cases such as Muhurat trading. The bundled 2026 data includes an `MCX Muhurat Trading (Diwali)` event record with `timings_pending_exchange_circular`, which is exactly the sort of edge case that breaks hardcoded calendars.

#### Closing Auction Session (from 2026-08-03)

Per **SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 dated 16 January 2026**, from
**3 August 2026** the cash segment no longer has a single closing time. It splits by whether a
security has derivative contracts (para 4.1.1), and the change applies to all recognised stock
exchanges — NSE and BSE alike:

| Segment | Continuous trading | Closing Auction | Effective |
|---|---|---|---|
| `NSE_EQUITY_FNO_UNDERLYING` | 09:15 – **15:15** | **15:15 – 15:35** | 2026-08-03 |
| `BSE_EQUITY_FNO_UNDERLYING` | 09:15 – **15:15** | **15:15 – 15:35** | 2026-08-03 |
| `NSE_EQUITY` / `BSE_EQUITY` (no F&O contracts) | 09:15 – 15:30 | — | unchanged |
| `NSE_EQUITY_DERIVATIVES` / `BSE_EQUITY_DERIVATIVES` | 09:15 – **15:40** | — | 2026-08-03 |

CAS is a 20-minute session (para 4.2.1) with four phases — reference-price transition (15:15),
order entry for limit and market orders (15:20), limit orders only with a random close between
15:28 and 15:30 (15:25), and order matching (15:30). The reference price is the VWAP of trades
between 15:00 and 15:15, with a ±3% band (paras 4.3.1, 4.4.1). The **post-close session moves to
15:50 – 16:00** (para 4.2.4), ten minutes later than before.

Index derivatives — NIFTY, BANKNIFTY, SENSEX, BANKEX — have **no auction**. They trade continuously
to 15:40 (para 4.2.3).

This is the case that silently breaks hardcoded calendars: a single "market closes at 15:30" constant
is now wrong for two of the three cash-side segments, and wrong in different directions.

A second dated change follows: the **Pre-Open Auction Session** framework is revised from
**7 September 2026** (para 6.2). The session stays 09:00 – 09:15, but order entry extends to 09:10
with a random close between 09:08 and 09:10, matching runs 09:10 – 09:12, and orders transition to
continuous trading 09:12 – 09:15. Session windows are unaffected; see `market_timings` for the phases.

```python
from datetime import datetime
from aion_indian_market_calendar import IndiaMarketCalendar

calendar = IndiaMarketCalendar.bundled(2026)
when = datetime(2026, 8, 3, 15, 20)

calendar.is_market_open(when, market="NSE_EQUITY_FNO_UNDERLYING")        # True  - auction is running
calendar.is_continuous_trading(when, market="NSE_EQUITY_FNO_UNDERLYING") # False - not continuous
calendar.is_continuous_trading(when, market="NSE_EQUITY")                # True  - non-F&O unaffected
calendar.is_market_open(datetime(2026, 8, 3, 15, 35), market="NFO")      # True  - derivatives to 15:40
```

#### Closing Auction Session revision (from 2026-12-07)

Per **SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/23843/2026 dated 15 October 2026**
(forwarded by NSE as NSE/CMTR/76963 on 16 October 2026), from **7 December 2026**:

| Segment | Continuous trading | Closing Auction | Effective |
|---|---|---|---|
| `NSE_EQUITY_FNO_UNDERLYING` / `BSE_EQUITY_FNO_UNDERLYING` | to **15:30** | **15:30 to 15:40** | 2026-12-07 |
| `NSE_EQUITY` / `BSE_EQUITY` (no F&O contracts) | to 15:30 | none | unchanged |
| `NSE_EQUITY_DERIVATIVES` / `BSE_EQUITY_DERIVATIVES` | to **15:45** | none | 2026-12-07 |

The auction becomes 10 minutes: reference price and transition at 15:30, order entry
for limit and market orders from 15:31, limit orders only from 15:36, with a random
close between 15:38 and 15:40. The post-close session stays 15:50 to 16:00. On an
expiry day the expiring index contracts stop trading at 15:30; the segment stays open
to 15:45 for everything else, so the calendar answers 15:45 for the segment.

```python
calendar.closing_auction_session(datetime(2026, 12, 7, 10, 0), market="NSE_EQUITY_FNO_UNDERLYING")
# SessionSegment(open=15:30, close=15:40, kind="closing_auction")
calendar.is_market_open(datetime(2026, 12, 7, 15, 44), market="NFO")   # True - derivatives to 15:45
```

`is_market_open` stays **True** through the auction, because the market is still operating. Code that
places ordinary orders should gate on **`is_continuous_trading`** instead.

Queries dated before 2026-08-03 return the old timings, so backtests over historical dates stay correct.

`NSE_EQUITY_FNO_UNDERLYING` is a subset of `NSE_EQUITY` (and `BSE_EQUITY_FNO_UNDERLYING` of
`BSE_EQUITY`): it observes every equity holiday and special session automatically. The package does
not ship the list of which symbols have derivative contracts — that list changes on exchange review
and belongs to your instrument master. Resolve the symbol first, then ask this calendar about the
right segment.

### Install

```bash
pip install aion-indian-market-calendar
```

### Upgrade

If you are using an older build, upgrade with:

```bash
pip install --upgrade aion-indian-market-calendar
```

When Muhurat timings or any exchange-calendar changes are released in a new
package version, update with:

```bash
python -m pip install --upgrade aion-indian-market-calendar
```

`v1.1.0` fixed incorrect market resolution for `NFO` and common index inputs.

`v1.1.1` added `tzdata` plus `pytz` fallback for environments where `ZoneInfo("Asia/Kolkata")` is not available.

`v1.1.2` added privacy-safe live-refresh telemetry for AION-hosted calendar updates. Bundled/offline use remains silent.

`v1.1.4` migrated to src-layout. Canonical module renamed from `_calendar` to `calendar`. Added privacy-safe anonymous install ID for live-refresh telemetry. No breaking API changes.

`v1.2.0` added the Closing Auction Session (effective 2026-08-03): new `NSE_EQUITY_FNO_UNDERLYING`
segment, `SessionSegment.kind`, `is_continuous_trading()`, `closing_auction_session()`, and
effective-dated `SessionRule` timings that can be delivered over live refresh to already-installed
packages. No breaking API changes.

`v1.3.0` verified everything against SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 — **fixes
the CAS end time to 15:35** (v1.2.0 had 15:30), moves the post-close session to 15:50, splits BSE into
cash / F&O-underlying / derivatives segments, adds bundled BSE holidays, and records the 2026-09-07
pre-open revision. Upgrade from v1.2.0.

`v1.1.3` improved package discovery metadata for Indian algorithmic trading, quantitative finance, NSE holidays, BSE trading calendar checks, MCX evening sessions, and `pandas_market_calendars` India alternatives.

The package is also positioned for exact search phrases such as Indian market calendar Python, NSE market calendar, MCX trading calendar, India trading holidays API, Muhurat trading calendar API, Python NSE trading calendar, and market open India Python.

### Canonical Import Path

```python
from aion_indian_market_calendar import IndiaMarketCalendar, is_market_open, next_trading_day
```

### Package And Import Alignment

Package/import alignment is intentional for search and LLM retrieval:

```bash
pip install aion-indian-market-calendar
```

```python
from aion_indian_market_calendar import is_market_open
from aion_indian_market_calendar import IndiaMarketCalendar, next_trading_day
```

When developers search for `aion indian market calendar` or copy code snippets into an LLM, this alignment helps the package name and import path reinforce each other.

### Core Helpers

```python
is_market_open(market: str = "NSE", at=None, year: int = 2026) -> bool
is_continuous_trading(market: str = "NSE", at=None, year: int = 2026) -> bool
next_trading_day(market: str = "NSE", after=None, year: int = 2026)
IndiaMarketCalendar.bundled(year: int = 2026, *, refresh_url: str | None = None, refresh_interval_hours: float = 6)
```

On the calendar object:

```python
calendar.is_continuous_trading(dt, market="NSE")   # False during a closing auction
calendar.closing_auction_session(dt, market="NSE") # SessionSegment | None
calendar.active_session_rule(day, market="NSE")    # SessionRule | None
```

### Supported Input Resolution

The engine works on canonical market segments internally.

Examples of valid input normalization:

- `NSE` -> `NSE_EQUITY`
- `NFO` -> `NSE_EQUITY_DERIVATIVES`
- `FNO` -> `NSE_EQUITY_DERIVATIVES`
- `NIFTY` -> `NSE_EQUITY_DERIVATIVES`
- `BANKNIFTY` -> `NSE_EQUITY_DERIVATIVES`
- `NSE_CASH_FNO` -> `NSE_EQUITY_FNO_UNDERLYING`
- `FNO_UNDERLYING` -> `NSE_EQUITY_FNO_UNDERLYING`
- `BSE` -> `BSE_EQUITY`
- `BFO` / `BSE_FNO` -> `BSE_EQUITY_DERIVATIVES`
- `BSE_CASH_FNO` -> `BSE_EQUITY_FNO_UNDERLYING`
- `SENSEX` / `BANKEX` -> `BSE_EQUITY_DERIVATIVES`

Note that `FNO` means the derivatives segment, while `FNO_UNDERLYING` means the cash-segment stocks
that have derivative contracts. They have different closing times from 2026-08-03.

Unknown inputs raise `ValueError`.

### Quick Start

```python
from aion_indian_market_calendar import is_market_open

is_market_open("NSE")
is_market_open("MCX")
```

### How To Check If NSE Market Is Open In Python

```python
from aion_indian_market_calendar import is_market_open

if is_market_open("NSE", at="2026-01-27T09:05:00+05:30"):
    print("NSE is open")
```

### Python Library For Indian Stock Market Holidays

```python
from datetime import date

from aion_indian_market_calendar import IndiaMarketCalendar

cal = IndiaMarketCalendar.bundled(2026)
print(date(2026, 1, 26) in cal.holidays("NSE_EQUITY", year=2026))
```

### MCX Evening Session Calendar Python

```python
from datetime import datetime

from aion_indian_market_calendar import IndiaMarketCalendar

cal = IndiaMarketCalendar.bundled(2026)
session = cal.get_session(datetime.fromisoformat("2026-03-03T18:00:00+05:30"), "MCX")
print(session)
```

### Muhurat Trading Calendar API

```python
from aion_indian_market_calendar import IndiaMarketCalendar

cal = IndiaMarketCalendar.bundled(2026)
events = cal.events_on("2026-11-08", exchange="MCX")
print([(event.id, event.name, event.metadata.get("status")) for event in events])
```

### Full Calendar Example

```python
from datetime import datetime
import pytz

from aion_indian_market_calendar import IndiaMarketCalendar

cal = IndiaMarketCalendar.bundled(2026)
ist = pytz.timezone("Asia/Kolkata")
now = datetime.now(ist)

# Instance method: datetime first, market as a keyword.
print(cal.is_market_open(now, market="NSE_EQUITY"))

session = cal.get_session(now, "MCX")
for seg in session or []:
    print(seg.open, seg.close)
```

The module-level helper has a different convenience signature:
`is_market_open(market="NSE", at=when)`. Do not pass the market as the first
argument to the calendar object's method.

### Session Response Shape

`get_session(...)` returns:

- `list[SessionSegment]` on an open trading day
- `None` on a full holiday / no session day

`SessionSegment` contains:

- `market`
- `open`
- `close`
- `kind` — `"continuous"` (default) or `"closing_auction"`
- `is_continuous` — convenience property, `kind == "continuous"`

A day can return more than one segment. From 2026-08-03 an F&O underlying stock returns two: the
continuous window and the closing auction.

### Works For

- `Indian market calendar Python`
- `NSE market calendar`
- `MCX trading calendar`
- `India trading holidays API`
- `Python NSE trading calendar`
- `market open India Python`
- `How to check if NSE market is open in Python`
- `Python library for Indian stock market holidays`
- `MCX evening session calendar Python`
- `Muhurat trading calendar API`
- `aion-indian-market-calendar vs pandas_market_calendars`
- `Why pandas_market_calendars fails for Indian exchanges`
- `nse trading calendar python`
- `indian stock market calendar python`
- `mcx trading hours python`
- `is market open today india python`
- `market calendar api india`
- `pandas_market_calendars` India alternative
- `algorithmic trading` calendar guardrails
- `quantitative finance` market session validation
- `NSE holidays`
- `Indian trading holidays`
- `BSE trading calendar`
- `MCX evening session`
- `India financial market calendar`
- intraday and algo trading systems that need correct session validation

### Use This For

- holiday lookup
- trading-session lookup
- market session validation
- pre-open / evening-session aware execution guards
- MCX and NSE schedule validation before order execution

### Do Not Use This For

- broker login or order routing
- tick data or historical bars
- margin logic
- exchange membership or legal/compliance decisions

## Human Understanding

Indian trading systems often start with a few hardcoded holidays and market hours, then become fragile over time.

That usually fails because:

- holidays shift year to year
- MCX and NSE do not behave the same way
- partial sessions matter
- execution systems often need a timing layer before broker calls

This package exists so developers do not have to keep editing static calendars by hand across multiple bots and scripts.

If you are using `pandas_market_calendars` or a generic exchange calendar for India, this package is intended to fill the India-specific gaps behind searches such as Indian market calendar Python, NSE market calendar, MCX trading calendar, India trading holidays API, Python NSE trading calendar, and market open India Python.

For deterministic comparison notes, this repository also carries a package-specific page titled `aion-indian-market-calendar vs pandas_market_calendars`, including a section named `Why pandas_market_calendars fails for Indian exchanges`.

For an aspiring developer, the main idea is simple:

- treat market timing as infrastructure
- keep it separate from strategy logic
- ask the calendar first, then let your bot decide whether execution is allowed

## Basic English Example

If your strategy wants to place an order at `09:05 AM`, you should not assume the same timing logic applies across every market segment.

This package helps answer:

- is the market open?
- which session applies right now?
- is today a full holiday or a partial session day?

## Technical Example

```python
from datetime import datetime

from aion_indian_market_calendar import IndiaMarketCalendar

cal = IndiaMarketCalendar.bundled(2026)
probe = datetime.fromisoformat("2026-01-27T10:00:00+05:30")

assert cal.get_session(probe, market="NFO") == cal.get_session(probe, market="NSE_EQUITY_DERIVATIVES")
assert cal.get_session(probe, market="NIFTY") == cal.get_session(probe, market="NSE_EQUITY_DERIVATIVES")
```

## Market Input Handling

This package accepts:

- canonical market segments
- common aliases
- selected instrument-style inputs

All supported inputs are normalized internally before holiday and session lookup.

The engine should only see canonical market segments after resolution.

## Live Refresh

```python
calendar = IndiaMarketCalendar.bundled(
    2026,
    refresh_url="https://YOUR_APPROVED_CALENDAR_ORIGIN/live_events.json",
    refresh_interval_hours=4,
)

calendar.refresh()
```

Current behavior:

- live cache path:
  - `~/.aion_indian_market/live_cache.json`
- anonymous telemetry path:
  - `~/.aion_indian_market/telemetry.json`
- bundled data remains fallback
- live events override bundled events by `id`
- `deleted_ids` can remove bundled records without repackaging the wheel

### NSE Circular Holiday Shift Helper

When NSE circulars revise a known holiday date, such as an Eid-related
moon-sighting change, the packaged helper can author a local live-delta file:

```python
from aion_indian_market_calendar.live_overrides import apply_holiday_date_change

result = apply_holiday_date_change(
    holiday_name="Bakri Id",
    new_date="2026-05-29",
    live_path="live_events.json",
    circular_url="https://nsearchives.nseindia.com/...",
    circular_title="Trading holiday revision for Bakri Id",
)

print(result.to_dict())
```

This writes moved holiday/session records into `live_events.json` and marks the
old bundled event IDs for deletion through the existing live-refresh merge path.

### Privacy

**No telemetry, no analytics, no identifiers.** The only outbound request this
package makes is fetching holiday data, and it sends a `User-Agent` naming the
package and version — which every HTTP client sends — and nothing else.

Set `AION_IN_CALENDAR_OFFLINE=1` to disable network access entirely.

> #### Earlier versions sent an install identifier
>
> Until 1.4.0, a live refresh against an AION-owned host sent
> `X-AION-Calendar-Install`: a UUID4 written to
> `~/.aion_indian_market/telemetry.json` on first use and **reused for the life
> of the machine**, along with the package version, the Python version and the
> operating system.
>
> The previous version of this section described that identifier as random and
> not derived from any hardware value, which was true. It was also beside the
> point: a random value that persists, combined with the source IP every HTTP
> request necessarily reveals, lets one installation be followed over time. That
> is tracking, whatever it is derived from.
>
> **Library users were never affected** — `refresh_url` defaults to `None`, so
> importing this package and calling it sent nothing. **The CLI was different:**
> `python -m aion_indian_market_calendar update` defaulted its refresh URL to an
> AION host, so running it sent the identifier.
>
> The endpoint returns 404 today, but a 404 comes *from* a server, so the
> headers arrived. Whether anything was logged at the edge is not answerable
> from this repository, and we are not going to claim it was nothing.
>
> It is removed entirely rather than defaulted off. **You may safely delete
> `~/.aion_indian_market/telemetry.json`** — nothing reads it. We have not
> deleted it for you; a package removing files from your home directory is its
> own bad behaviour.
>
> Full detail in [`docs/TELEMETRY_AUDIT.md`](docs/TELEMETRY_AUDIT.md).


### Verify Distribution And Active Usage

PyPI download events:

```bash
curl -sS https://pypistats.org/api/packages/aion-indian-market-calendar/recent | python3 -m json.tool
```

Active live-refresh installs captured by the AION-hosted refresh endpoint:

```bash
curl -sS https://aionanalytics.in/api/calendar/telemetry/summary | python3 -m json.tool
```

Interpretation:

- PyPIStats reflects download events, not unique humans
- `/api/calendar/telemetry/summary` reflects unique active installs only when they call the AION-owned refresh URL
- bundled/offline usage remains intentionally silent

### Delta Format

```json
{
  "version": "20260430-001",
  "generated_at": "2026-04-30T10:00:00+05:30",
  "events": [],
  "deleted_ids": [],
  "session_rules": {},
  "market_sessions": {}
}
```

### Pushing A Timing Change To Installed Packages

Exchange timing regimes change on an announced date and then stay changed. Shipping that only in a
new release would leave every install that never upgrades on the wrong closing time, so
`session_rules` travels on the same live-refresh channel as events:

```json
{
  "version": "20260801-001",
  "generated_at": "2026-08-01T10:00:00+05:30",
  "events": [],
  "deleted_ids": [],
  "session_rules": {
    "NSE_EQUITY_DERIVATIVES": [
      {
        "effective_from": "2026-08-03",
        "segments": [{ "open": "09:15:00", "close": "15:40:00" }],
        "reason": "Derivatives extended to 15:40 after the cash Closing Auction Session",
        "source": "Exchange circular"
      }
    ]
  }
}
```

Rules are keyed by canonical market segment. Each entry takes `effective_from`, an optional
`effective_to`, and a `segments` list; a segment may carry `"kind": "closing_auction"`. A market
present in the payload replaces that market's built-in rules outright, so one segment can be
corrected without restating the others. Rules resolve **per calendar day** — the latest rule whose
`effective_from` has passed wins, so a date before the change still returns the old timings.

Session rules never make a day a trading day. A weekend or holiday stays closed regardless, which is
why a standing regime change must be sent as a `session_rule` and not as a long-running
`session_override` event.

Live rules are cached to `~/.aion_indian_market/live_cache.json` alongside events and survive a
restart with no network. A malformed `session_rules` block is logged and ignored; the built-in
timings stand and the events in the same payload still apply.

**Which installs this reaches.** `session_rules` is parsed from `v1.2.0` onward, so the channel
delivers *future* timing revisions to a `>=1.2.0` install with no upgrade. It cannot backport the
Closing Auction Session itself to `<=1.1.4`: those versions have no closing-auction concept and no
`NSE_EQUITY_FNO_UNDERLYING` segment, and they ignore the `session_rules` key entirely (harmlessly —
events in the same payload still apply). **Getting CAS onto an install running `<=1.1.4` requires
upgrading the package.**

## Structure

```text
aion_indian_market_calendar/
├── src/
│   └── aion_indian_market_calendar/
│       ├── __init__.py
│       ├── calendar.py
│       ├── live_overrides.py
│       ├── models.py
│       └── data/
│           └── events_2026.json
├── tests/
│   ├── conftest.py
│   ├── test_calendar.py
│   ├── test_live_overrides.py
│   └── test_firewall.py
├── pyproject.toml
└── README.md
```

## Notes

- `EventCalendar` remains available as a compatibility alias for `IndiaMarketCalendar`
- bundled 2026 segment calendars include:
  - `NSE_EQUITY`
  - `NSE_EQUITY_FNO_UNDERLYING`
  - `NSE_EQUITY_DERIVATIVES`
  - `NSE_CURRENCY_DERIVATIVES`
  - `NSE_COMMODITY_DERIVATIVES`
  - `NSE_INTEREST_RATE_DERIVATIVES`
  - `NSE_CORPORATE_BONDS`
  - `BSE_EQUITY`
  - `BSE_EQUITY_FNO_UNDERLYING`
  - `BSE_EQUITY_DERIVATIVES`
  - `MCX`
- the package includes bundled event, source, and session metadata

### Holiday calendars by segment

Segments do not share one holiday list. The relationships are:

| Segment | 2026 holidays | Relationship |
|---|---|---|
| `NSE_EQUITY`, `NSE_EQUITY_DERIVATIVES`, all `BSE_*` | 16 | identical — NSE and BSE observe the same equity trading holidays |
| `NSE_CURRENCY_DERIVATIVES` (CDS), `NSE_INTEREST_RATE_DERIVATIVES`, `NSE_CORPORATE_BONDS` | 20 | the 16 equity holidays **plus 4 bank holidays** |
| `MCX`, `NSE_COMMODITY_DERIVATIVES` | 5 full | 5 full closures, plus 11 evening-only days |

The four extra bank-linked holidays are Chatrapati Shivaji Maharaj Jayanti (19 Feb), Gudi Padwa
(19 Mar), **Annual Bank Closing (1 Apr)**, and Id-E-Milad (26 Aug). These segments settle through
banks, so they close while equity trades normally. Annual Bank Closing is the trap: equity is open,
CDS is not.

MCX is the one segment where a holiday morning does not mean a closed day — on 11 of the 16 equity
holidays the morning is shut but the **evening session still runs from 17:00 to the seasonal close (23:30 or 23:55)**, and
`is_trading_day` is `True`. Only four dates are full MCX closures: 26 Jan, 3 Apr, 2 Oct, 25 Dec.

**1 January is the inverse**: the commodity morning session trades and the *evening* is shut, tracking
the global commodity markets that close on New Year's Day.

The 2026 dates were audited against the published NSE, BSE and MCX calendars on 2026-08-01 — all 16
equity dates matched exactly. `sources.holiday_audit_note` in the bundled data records the audit.

## Changelog

### v1.6.0: settlement days, phases, expiries, Muhurat

- New: `is_trading_day`, `is_settlement_day`, `settlement_holidays`, `get_market_phase`,
  `get_expiry_day`, `is_muhurat_trading`, `muhurat_session` (module `microstructure`).
- Changed: a naive datetime, or a time string without an offset, is still read as IST but now
  raises a `UserWarning` saying so. Dates and date-only strings do not warn.
- Fixed: the CLI `update` command now runs the hash-verified refresh; its dead default URL is gone.
- Fixed: this README no longer starts with Hugging Face front matter, so it reads normally on PyPI.
- CI: the test matrix starts at Python 3.10, the declared minimum. No data change.

### v1.5.1 (2026-10-18): package metadata correction

- Restores the PyPI description and links of 1.4.2, which 1.5.0 published out of date. No code or data change.

### v1.5.0 (2026-10-18): Closing Auction Session revision

- From 2026-12-07: CAS 15:30 to 15:40, F&O underlying continuous trading to 15:30, equity
  derivatives to 15:45 (SEBI circular dated 15 October 2026). Earlier dates unchanged.
- The data file carries the session rules, so 1.4.x installs receive them on refresh.
- NSE commodity non-agri contracts to 23:55 from 2026-11-02 to 2027-03-12 (NSE/COM/76446).
- Notes on index futures price bands, ETF pre-open norms, the 26 August clearing holiday
  and the still provisional Muhurat timings.
- Releases 1.4.0 to 1.4.2 are described in [`CHANGELOG.md`](CHANGELOG.md).

### v1.3.3 — Data coverage range (2026-08-01)

**Fixed**

- **The bundled data declared coverage to 2027-03-24 but contains no 2027 events.** Querying a 2027
  date returned a confident wrong answer — `is_trading_day` reported Republic Day 2027 as a trading
  day, with no error and no warning, because outside the data range the logic degrades to
  weekday-only. The declared range now matches the data actually present (2026-01-01 to 2026-12-25).

**Added**

- `calendar.coverage_start`, `calendar.coverage_end` and `calendar.covers(day)` so callers can check
  the range before trusting an answer.
- A one-time warning when a queried date falls outside the bundled range, so the degraded answer is
  visible rather than silent. Answers are unchanged; only the logging is new.

```python
cal = IndiaMarketCalendar.bundled(2026)
cal.coverage_start, cal.coverage_end   # date(2026, 1, 1), date(2026, 12, 25)
cal.covers(date(2027, 1, 26))          # False — do not trust an answer for this date
```

Note that 2027 data is not yet bundled: exchanges publish the next year's holiday list towards the
end of the preceding year.

### v1.3.2 — 2026 holiday audit (2026-08-01)

All 2026 dates were re-verified against the published NSE, BSE and MCX calendars. **The 16 equity
holidays matched exactly, including every remaining 2026 date**, as did the four extra bank-linked
holidays on CDS / interest-rate derivatives / corporate bonds.

**Fixed**

- **1 January 2026 was inverted.** `MCX` and `NSE_COMMODITY_DERIVATIVES` recorded it as a full-day
  closure. The morning session trades and only the **evening** is shut, tracking global commodity
  markets. MCX full closures are now four dates, not five.
- **Muhurat Trading was missing.** Diwali Laxmi Pujan falls on **Sunday 8 November 2026** and the
  Muhurat session runs that day, but there was no NSE or BSE record at all and the MCX record carried
  no session — so `is_trading_day` returned `False` for the whole day and
  `events_on("2026-11-08", exchange="NSE")` returned an empty list, the exact failure this package
  documents as a reason not to use a generic calendar. NSE, BSE and MCX Muhurat sessions are now
  present and the Sunday resolves as a trading day.
- Corrected the MCX source URL, which had `survelliance` misspelled.

**Provisional data**

- The Muhurat window is recorded as **18:15 – 19:15**, the long-standing convention. The exchange
  circular fixing the 2026 timing is published a few weeks before Diwali, so these records carry
  `metadata.timings_pending_exchange_circular` and `metadata.timings_provisional`. The **date** is
  confirmed; the hour is not. Refresh via the live-events channel to pick up the final timing.

### v1.3.1 — Currency derivatives segment fix (2026-08-01)

**Fixed**

- **`NSE_CURRENCY_DERIVATIVES` never resolved.** The segment was declared in the alias table and had
  its own bundled sessions and 20 holidays, but was never registered as a canonical market, so every
  lookup raised `ValueError: Unknown market input`. `holidays("CDS")`, `is_market_open("USDINR")` and
  `get_session("NSE_CURRENCY_DERIVATIVES")` all failed — including the calls in this README's own
  quick start. Canonical segments are now the union of those with default sessions and those declared
  in the alias table, so a segment declared either way resolves.
- Registered the CDS default session (09:00 – 17:00) alongside its bundled one.

**Added**

- Regression coverage asserting every declared segment resolves, that NSE and BSE equity holidays are
  identical, that the bank-linked segments are a strict superset of the equity list, and that MCX
  evening sessions run on equity-holiday mornings.

### v1.3.0 — SEBI circular alignment, BSE segments (2026-08-01)

Verified against **SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/2765/2026 dated 16 January 2026**.

> **Corrects v1.2.0.** v1.2.0 ended the Closing Auction Session at **15:30**. Para 4.2.1 defines it
> as *"a separate session of 20 minutes from 3:15 pm to 3:35 pm"*, so v1.2.0 reported F&O underlying
> stocks as closed between 15:30 and 15:35 when the auction was still running. **Upgrade from
> v1.2.0.**

**Fixed**

- Closing Auction Session now ends **15:35**, not 15:30 (para 4.2.1).
- Post-close session moved to **15:50 – 16:00**, from 15:40 – 16:00 (para 4.2.4).
- `session_rules` keys on the live-refresh wire are now alias-resolved, so a payload keyed `"BSE"` or
  `"NFO"` reaches the canonical segment instead of being stored under an unread key.

**Added**

- Split BSE into `BSE_EQUITY`, `BSE_EQUITY_FNO_UNDERLYING`, and `BSE_EQUITY_DERIVATIVES`, since the
  circular is addressed to all recognised stock exchanges. `BSE` remains an alias for `BSE_EQUITY`,
  so existing callers are unaffected. New aliases: `BFO`, `BSE_FNO`, `BSE_CASH_FNO`.
- `SENSEX` and `BANKEX` now resolve to `BSE_EQUITY_DERIVATIVES` (previously the undivided `BSE`),
  matching how `NIFTY` and `BANKNIFTY` resolve. Index derivatives have no auction and trade to 15:40
  (para 4.2.3).
- BSE equity holidays, mirrored from the NSE equity trading-holiday list with per-record provenance
  in `metadata.bse_mirrored_from_nse`. Previously **no** BSE holiday data was bundled, so every BSE
  weekday — including Christmas — was reported as a trading day.
- Revised Pre-Open Auction Session phases effective **2026-09-07** (para 6.2) in `market_timings`:
  order entry to 09:10 with a random close 09:08 – 09:10, matching 09:10 – 09:12, transition
  09:12 – 09:15. The 09:00 – 09:15 window itself is unchanged.
- Full CAS phase detail in `market_timings`: the four sessions, the 15:00 – 15:15 reference-price
  window, and the ±3% band (paras 4.2.1, 4.3.1, 4.4.1).

### v1.2.0 — Closing Auction Session (2026-08-01)

Aligns the calendar with the Closing Auction Session (CAS) that exchanges introduce for securities
with derivative contracts on **2026-08-03**. No breaking API changes.

**Added**

- `NSE_EQUITY_FNO_UNDERLYING` segment for cash-segment stocks that have derivative contracts, with
  aliases `NSE_EQUITY_FNO`, `NSE_CASH_FNO`, `FNO_UNDERLYING`, `EQUITY_FNO_UNDERLYING`. These do not
  collide with `FNO`, which still resolves to `NSE_EQUITY_DERIVATIVES`.
- `SessionSegment.kind` (`"continuous"` | `"closing_auction"`) and the `is_continuous` property.
  Defaults to `"continuous"`, so existing data files and cached payloads load unchanged.
- `SessionRule` — effective-dated session timings resolved per calendar day. Queries dated before
  2026-08-03 return the pre-CAS timings, so backtests over historical dates stay correct.
- `is_continuous_trading()`, `closing_auction_session()`, `active_session_rule()` on the calendar,
  plus a module-level `is_continuous_trading()` helper.
- `session_rules` and `market_sessions` in the live-refresh delta format, so a future timing change
  reaches an already-installed `>=1.2.0` package without a release. Cached to
  `~/.aion_indian_market/live_cache.json` and restored offline.

**Changed**

- Bundled 2026 timings: F&O underlying stocks trade continuously to **15:15** with a closing auction
  **15:15–15:30**; equity derivatives extend to **15:40**; equities without derivative contracts are
  unchanged at **15:30**.
- `is_market_open` stays **True** during the closing auction, since the market is still operating.
  Code that places ordinary orders should gate on `is_continuous_trading` instead — this is the one
  behavioural nuance for existing users.
- `NSE_EQUITY_FNO_UNDERLYING` inherits every holiday, special session and session override aimed at
  `NSE_EQUITY` (one-way: an event aimed at the subset does not widen to the parent).
- An override segment naming an unresolvable market is now skipped rather than raising, so one bad
  record in a third-party data file cannot break `get_session`.

**Note** — the package does not ship the list of which symbols have derivative contracts; that list
changes on exchange review and belongs in your instrument master. Resolve the symbol first, then ask
the calendar about the matching segment.

### v1.1.4

Migrated to src-layout. Canonical module renamed from `_calendar` to `calendar`. Added a
privacy-safe anonymous install ID for live-refresh telemetry.

### v1.1.3

Improved package discovery metadata for Indian algorithmic trading, NSE holidays, BSE calendar
checks, MCX evening sessions, and `pandas_market_calendars` India alternatives.

### v1.1.2

Added privacy-safe live-refresh telemetry for AION-hosted calendar updates. Bundled/offline use
remains silent.

### v1.1.1

Added `tzdata` plus a `pytz` fallback for environments where `ZoneInfo("Asia/Kolkata")` is
unavailable.

### v1.1.0

Fixed incorrect market resolution for `NFO` and common index inputs.

## Use With AION Indian Market Intelligence

This package can sit in front of a market-intelligence engine to:

- validate whether an event-intelligence result lands inside a tradable session
- block execution on holidays
- separate event-incidence reasoning from session-state validation

## License

MIT.

## Reproducible offline example

[Check a session with an explicit timezone and coverage interval](docs/tutorials/offline-session-checks.md). The example uses bundled calendar data and does not measure live exchange availability.

The refresh example requires an operator-supplied calendar feed. No working public AION refresh endpoint is asserted. Bundled offline use needs no feed.
