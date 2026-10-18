# Changelog

## 1.5.1 (2026-10-18): package metadata correction

1.5.0 was built from a working copy that predated the 1.4.2 metadata update, so its
PyPI page showed the old description and links (an old website domain and a GitLab
source). 1.5.1 restores the 1.4.2 description and links: homepage
aionanalytics.in, source, issues and changelog on GitHub. The calendar code and data
are identical to 1.5.0.

## 1.5.0 (2026-10-18): Closing Auction Session revision, from 7 December 2026

### Changed: CAS timings from 2026-12-07

SEBI circular HO/47/11/11(3)2025-MRD-POD2/I/23843/2026 dated 15 October 2026
("Review of certain aspects of the Closing Auction Session, market timings and
settlement methodology for derivatives contracts") modifies the January 2026 CAS
framework. NSE forwarded it on 16 October 2026 (NSE/CMTR/76963). From
**7 December 2026**:

| Segment | Until 2026-12-06 | From 2026-12-07 |
|---|---|---|
| `NSE_EQUITY_FNO_UNDERLYING`, `BSE_EQUITY_FNO_UNDERLYING` continuous trading | to 15:15 | to **15:30** |
| Closing Auction Session (same segments) | 15:15 to 15:35 (20 min) | **15:30 to 15:40** (10 min) |
| `NSE_EQUITY_DERIVATIVES`, `BSE_EQUITY_DERIVATIVES` | to 15:40 | to **15:45** |
| Cash post-close session | 15:50 to 16:00 | 15:50 to 16:00 (unchanged) |
| `NSE_EQUITY`, `BSE_EQUITY` (no derivative contracts) | to 15:30 | to 15:30 (unchanged) |

The new CAS phases (para 4.2.1): reference price and transition 15:30, order entry
for limit and market orders 15:31, limit orders only 15:36, with order entry closing
at random between 15:38 and 15:40 (para 4.2.2). The reference price becomes the VWAP
of the last 15 minutes of continuous trading (para 4.3.1). All of it is in
`market_timings` under `revised_from_2026_12_07`.

On an expiry day, trading in the **expiring index derivatives contracts** stops at
15:30 (para 4.2.4). The segment itself stays open to 15:45 for other contracts and
for stock derivatives, expiring ones included (para 4.2.5), so the calendar reports
the segment as open to 15:45. The contract-level stop is in `market_timings`; the
calendar does not know which contracts expire on a given day.

Queries dated before 2026-12-07 return the August regime, so backtests stay correct.
The carry-forward of unexecuted limit and iceberg orders into CAS (para 4.8, from
8 February 2027) changes no session time and is documented only.

### Changed: the data file carries the session rules

`holidays_2026.json` now includes `session_rules`. Installs of 1.4.x read rules from
the verified data refresh, so they receive the 7 December change without upgrading.
Upgrading is still recommended: 1.5.0 has the rules built in, which matters offline
(`AION_IN_CALENDAR_OFFLINE=1`) or when the refresh cannot reach the data repository.

### Added: NSE commodity winter hours

NSE/COM/76446 dated 21 September 2026: internationally reference-able non-agri
commodities trade 09:00 to 23:55 from 2 November 2026 to 12 March 2027.
`NSE_COMMODITY_DERIVATIVES` sessions now run to 23:55 in that window. Agri contracts
keep their earlier close inside the segment. Evening-only holiday sessions keep the
times in their own records. MCX is unchanged: no MCX circular for the winter switch
had been published on 2026-10-18.

### Documented, no session change

- From 7 September 2026 the CAS-aligned futures price band also covers index futures
  (NSE/CMTR/76170, 3 September 2026).
- From 7 September 2026 the SEBI norms for ETF base price, price bands, pre-open call
  auction and close-out apply (circular of 15 June 2026; start moved from
  1 September by the circular of 28 August 2026).
- 26 August 2026 (Id-E-Milad) was a clearing holiday: equity trading open; currency,
  interest rate derivatives and corporate bonds closed. The bundled data already
  had this right; the source is now recorded.
- Muhurat Trading on Sunday 8 November 2026 is confirmed, but its timings are still
  not notified (NSE/FAOP/71777 says they "shall be notified subsequently"). The
  bundled 18:15 to 19:15 stays marked provisional.

### Fixed

- The rule-only warning no longer mentions "computed Lithuanian public holidays",
  text carried over from the sibling package.

### Not covered yet

- 2027 holidays: the exchanges have not published the 2027 lists. Bundled data still
  ends on 2026-12-25.

## 1.4.2 — documentation correction

### Fixed — calendar instance signature examples

The calendar-object method is documented consistently as
`calendar.is_market_open(at, market=market)`. The module-level convenience
helper remains market-first as `is_market_open(market, at=at)`. The distinction
is now stated in the source docstrings, README and published user guide so
copying an example cannot pass the market name where a datetime is expected.

## 1.4.1 — unreleased

### Removed — the legacy live-events refresh

`refresh_url` and the machinery behind it are gone. That path fetched from
whatever URL it was given, merged the result straight into live answers, and
cached it to `~/.aion_indian_market/live_cache.json` — **with no integrity check
of any kind**. Its default endpoint had returned 404 since before 1.4.0, so in
practice it logged an error and did nothing, which is why it survived this long
unnoticed.

In 1.4.0 that was cosmetic: it could not reach or corrupt the hash-verified
holiday data, which lives in a different directory entirely, so the only symptom
was a confusing `HTTP Error 404` in the logs when a caller passed the old URL.
It is removed anyway. A code path that accepts unverified remote data into live
answers is not worth the compatibility it buys, least of all in a package whose
point since 1.4.0 is that data is verified before it is trusted.

`refresh()` remains and is documented; it now refreshes the hash-verified dataset
and returns whether anything changed. `refresh_url` is still accepted as a
constructor argument and ignored. Use `AION_IN_CALENDAR_URL` to point the data
source elsewhere.

Four tests covering the removed path are deleted with it, with a note in
`tests/test_calendar.py` recording what they covered and why.

### Security — the taxonomy fetch now requires a hash

Found while auditing the removal above. The taxonomy manifesto path checked a
file's SHA-256 **only if the manifest supplied one**: `if expected_hash and ...`.
Omit the field and verification was skipped entirely. The thing being verified
decided whether to be verified — and that is precisely the route the 2026-06-26
incident took, a manifest with no `sha256` writing a 105-byte delta over a 117 KB
taxonomy. The structural guard added at the time covered a single filename; any
other `.yaml` without a hash was written unverified.

A missing hash is now a refusal. Writes are also deferred until every file in
the batch verifies, so a failure on the third no longer leaves the first two on
disk.

**Not believed exploited, and not reachable by default.** It required a caller to
pass `taxonomy_manifesto_url`, or to have had `refresh_url` set — and removing
the legacy refresh above means nothing internal calls this path any more.
`refresh_taxonomy_manifesto()` remains public, so it is hardened rather than
deleted.

*(An earlier note in this session described this as write-then-verify. That was
wrong: the mismatch check did precede the write. The defect was that the check
was optional.)*

### Fixed

- `HTTP Error 404: Not Found` no longer appears in the logs of anyone who passed
  the old refresh URL. Listed under *Known issues* in 1.4.0.

---

## 1.4.0 — 2026-09-12

Two things in this release matter more than the features: telemetry is gone, and
the holiday data can finally update itself.

### Removed — telemetry that sent a persistent install identifier

Until this release, a live refresh against an AION-owned host sent five headers.
One of them, `X-AION-Calendar-Install`, was a UUID4 written to
`~/.aion_indian_market/telemetry.json` on first use and **reused for the life of
the machine**, across upgrades and reinstalls. Alongside it went the package
version, the Python version and the operating system.

That is a persistent pseudonymous identifier. Combined with the source IP that
any HTTP request necessarily reveals, it allowed a single installation to be
followed over time. The source called it anonymous. It was not.

**Who was affected.** Library users were not: `refresh_url` defaults to `None`,
so importing this package and calling it never sent anything. **The CLI was
different** — `python -m aion_indian_market_calendar update` defaults
`--refresh-url` to an AION host, so anyone who ran it sent the identifier.

**Whether anything was recorded, we cannot say from our side.** The endpoint
returns 404, but a 404 comes *from* a server, which means the request and its
headers arrived. Whether the edge in front of it logged them, and for how long
any such logs are kept, is not answerable from this repository. We are not going
to claim it was nothing.

**What we have done.** The telemetry is deleted, not defaulted off — a code path
that can send an identifier is a liability in a published wheel even when it
never fires. The `telemetry=` keyword is still accepted so code written against
1.3.x does not break, including anyone who passed `telemetry=False`; it now
controls nothing.

**What you can do.** If you ever ran the CLI, you may safely delete
`~/.aion_indian_market/telemetry.json`. Nothing reads it any more. We have not
deleted it for you, because a package quietly removing files from your home
directory is its own bad behaviour.

`tests/test_no_egress.py` now intercepts `socket` itself and asserts that
importing the package, constructing a calendar and answering questions open no
connection at all, and that a refresh reaches only the configured host. The
telemetry cannot come back without failing the build.

Full detail: [`docs/TELEMETRY_AUDIT.md`](docs/TELEMETRY_AUDIT.md).

### Fixed — holiday data can update again

The previous refresh pointed at `api.aiondashboard.site/v1/calendar/live`, which
returns 404, and was fed by a scheduled poller that stopped running on
**2026-07-05**. `refresh_url` also defaulted to `None`, so the mechanism was
opt-in and off. **This package's holiday data has had no path to update since
July.**

It now fetches from a published data repository, on by default, at most once a
day. A new closure reaches you without a release.

### Security — hash verification and atomic swap

On **2026-06-26** a refresh with no integrity check wrote a 105-byte delta over a
117 KB calibrated data file and wiped a production component. The guard added at
the time checked a size floor and a few required keys, which stops that exact
payload and nothing else.

Every file is now verified against a SHA-256 listed in a signed manifest.
Downloads land in a staging directory; the swap happens only if **every** file
verifies, and it is atomic. A single mismatch means nothing is adopted. The
structural check is kept as a second line.

`tests/test_incident_20260626.py` reproduces the incident — and a correctly
shaped but altered file, which the old guard could not have caught — and asserts
both are rejected.

### Changed

- Bundled data file renamed `data/events_2026.json` → `data/holidays_2026.json`,
  matching the published repository so the bundled copy verifies against the same
  manifest. Reading it directly was never part of the public API.
- `AION_IN_CALENDAR_OFFLINE=1` disables all network access.
- `AION_IN_CALENDAR_URL` overrides the data source.
- `AION_IN_CALENDAR_CACHE` chooses where refreshed data is cached. It honours
  `XDG_CACHE_HOME`, and falls back to a temp directory if neither is writable
  rather than silently giving up on updates.
- The scheduled NSE poller is deprecated. It wrote to an endpoint that no longer
  exists; maintenance now runs through the ingestion tool in the data repository.

### Known issues (fixed in 1.4.1)

- Passing the old `refresh_url` explicitly makes the legacy path fire and log
  `HTTP Error 404: Not Found`. **Cosmetic.** That path writes to
  `~/.aion_indian_market/live_cache.json` and reads nothing from the
  hash-verified store, which lives in a separate directory, so it cannot
  override bundled data or bypass verification. Verified by inspection of both
  code paths. Removed entirely in 1.4.1.

### Unchanged

Every existing query API behaves as it did. The event payload keeps its `id`,
`policy`, `impact` and time range — those were deliberately not flattened to
match the sibling Lithuanian package, because callers act on them.

---
