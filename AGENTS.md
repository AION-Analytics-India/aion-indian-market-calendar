# AGENTS.md - aion-indian-market-calendar

Rules for any automated agent, and any contributor, working in this repository. This is a
public repository: everything here is published.

This is **aion-indian-market-calendar**, an MIT-licensed Python package for Indian market
trading days, settlement days, intraday phases, derivative expiries and holidays (NSE, BSE, MCX,
currency derivatives). It is maintained by AION Analytics.

- **Source of truth for structure and dependencies: [`SITE_MAP.md`](SITE_MAP.md).** Read it before
  adding anything.
- Release notes: [`CHANGELOG.md`](CHANGELOG.md). User documentation: [`README.md`](README.md).

## Repository Hygiene & Site Maps

1. **The Site Map is Law:** Every product repository must maintain a `SITE_MAP.md` at its root. Before creating a new script, folder, or dependency, you must check the `SITE_MAP.md` to ensure you are not duplicating existing logic or breaking architectural boundaries.
2. **Update on Change:** Any time you add a new script, modify a core dependency, or deprecate a file, you must update the `SITE_MAP.md` in the same commit/session.
3. **No Scattered Debris:** Never create ad-hoc scripts in the root directory. All new scripts must go into the appropriate `scripts/` or `src/` subdirectory.
4. **Cross-Repo Reading:** You may only read files from another AION repo if the dependency is explicitly documented in your repo's `SITE_MAP.md`.

## Rules specific to this package

- **Facts come from primary sources.** Holidays, session timings and expiry rules are taken from
  the exchange (NSE, BSE, MCX) or the regulator (SEBI, RBI), never from a blog or a broker page,
  and the circular or notice is cited where the rule is written.
- **Refuse rather than guess.** Where the data has no answer (a date outside the bundled range, an
  index without a sourced expiry rule), raise. Never fall back to a weekday guess silently.
- **Data does not change here.** The published data, and the tool that edits it, live in
  [aion-market-calendar-data](https://github.com/AION-Analytics-India/aion-market-calendar-data).
  The bundled copy in `src/aion_indian_market_calendar/data/` is the offline fallback. Never edit a
  `manifest.json` by hand, and never put a test date into published data.
- **No network unless a refresh is asked for, and no identifier ever.** `tests/test_no_egress.py`
  and `tests/test_no_telemetry.py` guard this and must stay green.
- **Information, not advice.** The package reports when markets trade and settle. Nothing in the
  code or the documentation tells anyone what to trade.
- **Releases** go only through the tag-triggered workflow in `.github/workflows/publish.yml`.
  Never upload from a laptop, never force-push, never rewrite published history.
- **Nothing private.** No credentials, no internal paths, no server details, nothing about systems
  outside this repository.

Run the tests offline: `AION_IN_CALENDAR_OFFLINE=1 pytest -q`.
