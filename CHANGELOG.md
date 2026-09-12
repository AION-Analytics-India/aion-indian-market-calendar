# Changelog

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

### Unchanged

Every existing query API behaves as it did. The event payload keeps its `id`,
`policy`, `impact` and time range — those were deliberately not flattened to
match the sibling Lithuanian package, because callers act on them.

---

