# Telemetry audit — aion-indian-market-calendar

*Audited 2026-09-12, against the source at version 1.3.3.*

## Summary

The package sends five HTTP headers identifying the installation, the package
version, the Python version and the operating system, **on every live-refresh
request to an AION-owned host**. One of those headers is a UUID persisted to disk
that survives restarts and upgrades.

It is off for library users, because the refresh URL they would have to supply
defaults to `None`. It is **on by default for anyone running the CLI**, because
`python -m aion_indian_market_calendar update` defaults its `--refresh-url` to an
AION host.

This contradicts the published privacy position and is removed in 1.4.0.

## What is sent

`calendar.py::_refresh_headers`, on the refresh request:

| header | value | notes |
| --- | --- | --- |
| `User-Agent` | `aion-indian-market-calendar/<version>` | always, telemetry or not |
| `X-AION-Calendar-Telemetry` | `live-refresh` | marker |
| `X-AION-Calendar-Install` | **UUID4 hex, persisted** | see below |
| `X-AION-Calendar-Version` | package version | |
| `X-AION-Calendar-Python` | `platform.python_version()` | |
| `X-AION-Calendar-System` | `platform.system()` | e.g. `Darwin`, `Linux` |

### The install identifier

`calendar.py::_anonymous_install_id` generates a `uuid4().hex` on first use and
writes it to `~/.aion_indian_market/telemetry.json`. It is reused for the life of
the machine, across upgrades and reinstalls, unless that file is deleted.

It is **not** derived from hardware, so it is not a fingerprint. It is,
unambiguously, a **persistent pseudonymous identifier**. Combined with the source
IP that any HTTP request necessarily reveals, it allows one installation to be
followed over time. Calling it "anonymous" in the source is generous.

## When it fires

`calendar.py::_telemetry_enabled` requires all of:

1. `AION_CALENDAR_TELEMETRY` not set to a falsey value, **and**
2. `telemetry` not explicitly `False`, **and**
3. `refresh_url` set, **and**
4. the refresh host is AION-owned (`_refresh_host_is_aion_owned`).

Condition 4 is good design and worth keeping in mind: the install ID is never
leaked to a third-party refresh URL. The problem is conditions 1–3, not 4.

## Who is affected

| path | `refresh_url` default | telemetry |
| --- | --- | --- |
| Library — `IndiaMarketCalendar(...)` | `None` | **off** |
| CLI — `python -m ... update` | `https://api.aiondashboard.site/v1/calendar/live` | **on** |

So the exposed population is CLI users, not importers. Given the CLI is a
maintainer-facing update command, that population is probably very small and may
be zero outside this machine — but it cannot be verified from here, and "probably
zero" is not a privacy position.

## Did it ever reach a server?

**Partly, and the honest answer is "we cannot fully know."**

`api.aiondashboard.site` resolves (172.67.189.7, Cloudflare) and
`/v1/calendar/live` returns **404**. A 404 is returned *by* a server, which means
the request — and its headers — arrived. Whether anything was logged depends on
the edge configuration, which is not in this repository.

So the claim "it never fired" is wrong. The accurate claim is: **requests
carrying the install ID would have reached the edge whenever a CLI user ran
`update`, and the application behind it returned 404.** The local logs on this
machine show the poller failing with `No route to host` on 2026-07-05, which is a
different failure (no route at all), so at least some attempts never left.

## Release exposure

Telemetry is present in the source at 1.3.3. The published history:

```
0.1.0, 0.1.1   2026-04-29
1.1.0          2026-05-01
1.1.2-1.1.4    2026-05-12 / 05-17
1.2.0-1.3.3    2026-08-01
```

Which of these first contained the telemetry code could not be established from
the git history available here (the string does not appear in any recorded
commit, so the file was likely added wholesale). **Assume every published version
may contain it** and say so publicly rather than claiming a narrower window that
cannot be evidenced.

## Related finding: the refresh mechanism does not work

Not a privacy issue, but found in the same pass and relevant to the fix:

- The maintainer poller `com.aion.indian-market-calendar-nse-poller` is **not
  loaded** in launchd. Its last recorded run was **2026-07-05**, and it failed
  then with `No route to host`.
- `/v1/calendar/live` returns 404.
- `refresh_url` defaults to `None`, so auto-update is opt-in and off.

The holiday data in this package has therefore had **no path to update since
July**, which is the thing users actually rely on.

## Related finding: the 2026-06-26 incident

`calendar.py:37` records that a hash-less refresh wrote a 105-byte live-events
delta over `taxonomy_india_v2_calibrated.yaml`, wiping the IMI sector engine. The
fix was a structural guard — a size floor plus four required top-level keys.

That guard stops *that* payload. It does not stop a correctly-shaped but wrong
file, and it is not integrity verification. The 1.4.0 fix is SHA-256 per file
from a manifest, with an atomic swap, keeping the structural check as a second
line.

## Actions taken in 1.4.0

1. **Telemetry deleted**, not defaulted off. A code path that can send an
   identifier is a liability in a published wheel even when it never fires.
2. The install-ID file is no longer written. An existing
   `~/.aion_indian_market/telemetry.json` is left alone rather than deleted —
   silently removing files from a user's home directory is its own bad behaviour
   — but nothing reads or transmits it, and the README says how to delete it.
3. A test asserts that a refresh sends **no** `X-AION-*` header.
4. The refresh mechanism moves to GitHub raw with SHA-256 verification, removing
   both the dead endpoint and the reason a bespoke server existed.

## Still to check, outside this repository

- Whether the edge in front of `api.aiondashboard.site` logged the headers, and
  for how long those logs are retained.
- Whether `aiondashboard.site` marketing pages run third-party analytics. That is
  a separate question from the package, but the privacy policy covers both and
  should be accurate about each.
