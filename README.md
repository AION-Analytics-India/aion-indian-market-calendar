# AION Indian Market Calendar

MIT-licensed Python software for scheduled trading days, supported settlement
holidays, intraday phases and selected derivative expiries in India. No API key
is required. This is not a live exchange-status feed, broker interface, order
execution service or compliance guarantee. Exchange notices remain authoritative.

## Release state

Current gate authority: [RELEASE_STATUS.md](RELEASE_STATUS.md). This is an
unreleased review branch. Native package and managed-updater checks have run
on GitHub; exact dated results and scope are in RELEASE_STATUS.md. Actual
reboot acceptance and production signing/channel activation remain blocked.

This branch prepares **1.8.0**. It has not been published. The latest verified
PyPI release is **1.7.1**, published 2 November 2026. Existing installations do
not acquire Python fixes merely because another version is published.

```bash
python -m pip install aion-indian-market-calendar
```

Install from [PyPI](https://pypi.org/project/aion-indian-market-calendar/).
[Canonical source](https://github.com/AION-Analytics-India/aion-indian-market-calendar),
[issues](https://github.com/AION-Analytics-India/aion-indian-market-calendar/issues),
[contribution guide](CONTRIBUTING.md), [release history](CHANGELOG.md),
[website](https://aionanalytics.in/open-source/indian-market-calendar) and
[shared data](https://github.com/AION-Analytics-India/aion-market-calendar-data).
The older documentation mirror is not the maintained implementation.

## Software updates require one-time owner setup

Ordinary pip installation does not register a service or enable software
installation. Older users must manually bootstrap once to the reviewed
`aion-indian-market-calendar[updates]` release. The original pip environment is
then left unchanged. Only applications launched through the explicitly adopted
managed runtime receive its compatible, approved Python patches.

The staged `update_lifecycle setup` command detects the current version and
runtime dependencies, requires consent, verifies an owner-provided trust policy
and bootstrap artifacts, creates isolated controller/runtime environments, and
registers a user-scoped launchd job on macOS or systemd timer on Linux. A
Windows Task Scheduler adapter has passed the actual scheduled-update lifecycle
on Windows Server 2022 x64 with Python 3.10-3.14. This is not Windows 11 desktop
or real reboot acceptance. The
`--enable-auto-install` flag is separate from consent to notifications. Nothing
is enabled by importing the calendar or refreshing calendar data.

This lifecycle supports status, start, stop, disable, uninstall and verified
rollback. It recovers protocol-2 interrupted-update locks after all holders
have exited. Windows automatic installation is not approved for use. User jobs resume at
login/user-manager startup, not necessarily before login. Linux pre-login
operation requires an already approved lingering user manager; setup never
changes that setting.

Production signing identity, HTTPS channels and their operational availability
still require release-owner verification. Disposable-key tests are not a
production-ready service. See [setup, ownership and trust](docs/UPDATE_CONTRACT.md).
Calendar-data refresh is independent. No 2027 calendar coverage is added.

## Covered dates and markets

The candidate bundles Indian dataset 2026.11.14, with declared coverage
**2026-01-01 through 2026-12-25**. No Indian 2027 holiday payload is available
in this candidate. Unsupported session/date questions raise, including
next-trading-day searches that exhaust coverage. A calculated seasonal time
extending into another year is not holiday coverage for that year.

| Market scope | Scheduled behavior and limits |
| --- | --- |
| NSE/BSE cash | Choose generic cash or the separate F&O-underlying cash subset for CAS. This is not a symbol-membership master. |
| NSE/BSE equity derivatives | Segment schedules, not a determination of the trading cutoff for a particular expiring contract. |
| NSE CDS | USDINR, EURINR, GBPINR and JPYINR, 09:00-17:00 IST, with separate currency holidays. No BSE CDS or cross-currency contracts. |
| Non-agri commodity schedules | MCX/NSE seasonal close at 23:30 during US daylight saving and 23:55 otherwise, subject to sourced overrides. Agricultural contract hours are not modeled. |
| Settlement | NSE Clearing-style date utility, distinct from trading. Not a universal BSE/MCX/banking settlement service. |
| Expiries | NIFTY weekly Tuesday; listed NSE monthly indices last Tuesday; SENSEX Thursday. Covered holidays shift to the preceding trading day. No currency expiry or arbitrary contract master. |
| Muhurat | Separate NSE non-CAS cash, CAS cash and F&O windows from CMTR/76941 and FAOP/76940. BSE/MCX timings retain their existing provisional label. Unknown NSE F&O special schedules refuse. |

CDS aliases include `CDS`, `CURRENCY_DERIVATIVES`,
`NSE_CURRENCY_DERIVATIVES` and the four INR symbols above. A trading day can be
a settlement holiday: equity trades on 1 April 2026 while CDS and settlement
are closed.

### Currency derivatives (CDS) have a different session

| Supported NSE INR pair | Regular session (IST) | Calendar |
| --- | --- | --- |
| USDINR, EURINR, GBPINR, JPYINR | 09:00-17:00 | Separate currency-specific holidays |

This is not the equity session: regular equity pre-open is 09:00-09:15,
followed by continuous matching at 09:15-15:30, subject to dated special-session
and closing-auction rules. Currency trading and settlement days are distinct.
For example, CDS is closed on 1 April 2026 while NSE equity trades; settlement
is also closed. BSE CDS, cross-currency contracts, currency expiry calculation
and individual contract cutoffs are outside the supported contract.
[NSE market timings](https://www.nseindia.com/resources/exchange-communication-market-timings)
and the versioned bundle supply scope and provenance; exchange notices prevail.

## Effective 7 December 2026

[SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/23843/2026, 15 October 2026](https://www.sebi.gov.in/sebi_data/attachdocs/oct-2026/1792079571420.pdf)
is represented as an effective-dated rule already in the candidate:

- F&O-underlying cash continuous matching ends at 15:30 IST; CAS is 15:30-15:40.
- The general equity-derivatives segment continues until 15:45.
- Expiring index contracts stop at 15:30 on their expiry day. The generic
  segment query cannot identify an individual contract's expiry cutoff.
- Cash post-close is 15:50-16:00.

Earlier dates retain the applicable earlier schedule. CAS output describes a
scheduled envelope; it cannot observe system-driven random order-entry closure
or actual auction completion. The February 2027 order-transition provision is
not a new holiday calendar or a supported 2027 session claim.

## Offline examples

Set the offline policy before importing or using the package:

```python
import os
os.environ["AION_IN_CALENDAR_OFFLINE"] = "1"

from datetime import date
from aion_indian_market_calendar import (
    IndiaMarketCalendar, get_market_phase, get_expiry_day,
    is_trading_day, is_settlement_day,
)

cal = IndiaMarketCalendar.bundled(2026)
assert cal.covers(date(2026, 11, 13))
assert cal.is_market_open("2026-11-13T16:30:00+05:30", market="CDS")
assert not cal.is_continuous_trading("2026-11-13T09:05:00+05:30", market="NSE")
assert get_market_phase("2026-12-07T15:30:00+05:30",
                        "NSE_EQUITY_FNO_UNDERLYING", calendar=cal) == "CLOSING_AUCTION"
assert is_trading_day("2026-04-01", calendar=cal)
assert not is_settlement_day("2026-04-01", calendar=cal)
assert str(get_expiry_day("NIFTY", "2026-10-19", calendar=cal)) == "2026-10-19"
```

Class methods are datetime-first (`cal.is_market_open(at, market=...)`).
Module convenience functions are market-first (`is_market_open("CDS", at=...)`).
Aware date-taking and timestamp-taking helpers convert to IST before choosing
the calendar date. Naive clocks retain the compatibility assumption of IST,
with a warning. A plain date has no clock and does not warn.

`get_market_phase` returns `PRE_OPEN`, `CONTINUOUS`, `CLOSING_AUCTION`,
`POST_CLOSE`, `MUHURAT_TRADING` or `CLOSED`. Its windows and continuous-matching
checks are half-open. The legacy `is_market_open` activity envelope retains its
inclusive close edge for compatibility; it is not an ordinary-order gate.
Use the phase or continuous-matching helper to distinguish matching from other
operations. No function observes real-time halts.

`from_json` accepts a caller-owned explicit calendar. `from_records` and legacy
custom files without a range establish only dates with supplied holiday or
session facts; intervening weekdays and empty calendars remain unknown.
The caller remains responsible for completeness of custom records.
`holidays(year=...)` is a list for the covered portion, not a claim of a full
calendar year. `covers()` reports the precise interval.

## Two independent update mechanisms

**Calendar data:** ordinary online loads may check compatible approved public
data, with a daily check throttle and a bounded synchronization check in loaded
readers. Set `AION_IN_CALENDAR_OFFLINE=1` to prohibit package network refresh,
including explicit refresh and RSS polling. Offline uses verified cache or
bundle. A failed check keeps validated data, not fabricated future answers.

`python -m aion_indian_market_calendar update --force` explicitly checks data.
Exit 0 means current/updated, 1 means failed, 2 means offline/not attempted.
`AION_IN_CALENDAR_URL` selects the data origin; `refresh_url` remains an ignored
legacy argument. Manifest schema, metadata, payload structure and SHA-256 must
verify before an atomic generation switch. HTTPS transfer is required except
explicit loopback fixture origins. These manifests are not digitally signed.
`store.status()` reports coverage, generation, freshness, review due and the
last refresh. A review reminder is separate from the supported-date boundary.

**Python software:** no import, normal API call or data refresh runs pip.
Version discovery is an explicit authorized operation against an approval
manifest whose SHA-256 the deployment owner provides independently. A separate
opt-in supervisor verifies the complete wheel closure, creates an isolated
candidate environment, installs without an index, runs compatibility checks,
and atomically promotes an environment pointer. It retains the previous
accepted environment for explicit rollback. It does not restart an application.

External PyPI users can explicitly adopt the supported managed lifecycle or
use their own authorized package automation. AION-protected deployments require
their independently approved controller and cannot use customer-mode admission. **Existing 1.7.1 installations cannot retroactively gain it.**
See [the complete update contract](docs/UPDATE_CONTRACT.md).

## Safety, history and license

No persistent installation identifier, telemetry service, model code or private
data is included. The retired non-calendar update entry point performs no
updates. The historical [telemetry audit](docs/TELEMETRY_AUDIT.md) and all prior
[release notes](CHANGELOG.md) are retained; newer behavior does not repair old
installations automatically. Code and documentation are MIT licensed.

### Explicit managed-runtime onboarding

These commands require release-owner-provided policy, approved bootstrap
manifest/hash and a platform-compatible local wheel closure. Those production
inputs are not bundled, and the candidate is not yet a public release.

This is an engineering template, not a ready customer quick-start. The
production policy, independent root fingerprint, signed bootstrap distribution
and approved wheel closure are not yet supplied. Do not attempt to install an
unpublished 1.8.0 from PyPI. For isolated review use the exact built local wheel:

```bash
python -m pip install "/reviewed/path/aion_indian_market_calendar-1.8.0-py3-none-any.whl[updates]"
python -m aion_indian_market_calendar.update_lifecycle setup \
  --root /user-owned/calendar-managed --consent --enable-auto-install \
  --policy approved-policy.json --bootstrap-manifest bootstrap.json \
  --approved-sha256 INDEPENDENT_APPROVED_SHA256 --wheelhouse approved-wheels
python -m aion_indian_market_calendar.update_lifecycle status \
  --root /user-owned/calendar-managed
python -m aion_indian_market_calendar.update_lifecycle run \
  --root /user-owned/calendar-managed -- -I -c 'import importlib.metadata as m; print(m.version("aion-indian-market-calendar"))'
python -m aion_indian_market_calendar.update_lifecycle stop \
  --root /user-owned/calendar-managed
python -m aion_indian_market_calendar.update_lifecycle start \
  --root /user-owned/calendar-managed --consent
python -m aion_indian_market_calendar.update_lifecycle disable \
  --root /user-owned/calendar-managed
python -m aion_indian_market_calendar.update_lifecycle uninstall \
  --root /user-owned/calendar-managed
```

Omit `--enable-auto-install` during setup for notifications only. `stop` pauses
the current schedule; `disable` also prevents resumption after login/reboot.
Uninstall removes the owned supervisor, retaining managed versions and receipts
for recovery. Plain `pip uninstall` does not unregister an OS service: run the
lifecycle uninstall first. No package command changes another Python environment.

The release channel is separate from PyPI. Uploading a wheel alone does not
announce it to managed devices. Only signed, non-revoked, unexpired releases in
the owner-approved major/minor series and exact dependency lock are eligible.
`run` holds a workload lease; automatic updates defer while that runtime is
active. Applications outside this launcher are not managed or restarted.
Protected AION deployments also require a hash-pinned admission controller.

The low-level `automatic_updates check/watch` and `managed_updater` commands
remain for existing operator integrations. They do not register persistent
supervision and must not be presented as the customer onboarding lifecycle.


### Windows staged contract

The adapter uses a current interactive user token, least privilege, no stored
password and no S4U/SYSTEM fallback. It proposes periodic checks while signed
in and catch-up at logon. It does not promise network checks while logged out.
Native locks, ACL/reparse protection and worker process-tree cleanup require
Windows execution. Native CI exercises leases, process-tree termination and complete signed
scheduled upgrade/recovery/teardown. Windows 11 normal-user and real reboot/logon
acceptance remain pending. Portable XML
checks and a Windows runner tag are not substitutes for those tests.

The installed library and optional updater have separate platform gates.
Python 3.9 is unsupported by metadata. Python 3.10-3.14 is the candidate library
matrix; see RELEASE_STATUS.md for actual tested scope. No ordinary pip install
registers an OS task. No automatic installation is production-approved yet.

Matching setup repeats return actual status without changing consent or
re-enabling disabled jobs. Changed/legacy roots require owner reconciliation.
Notification-only mode records local availability; no email or desktop toast
is implemented. Runtime patches do not replace the pinned updater controller,
which needs a separate reviewed bootstrap. Arbitrary application dependencies
are not copied into the managed runtime. The inline version command above is
the tested application example; application integration is separately owned.
