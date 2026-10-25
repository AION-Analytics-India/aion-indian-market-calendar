# aion-indian-market-calendar - Site Map & Architecture

Mapped 2026-10-25 from the tracked file list, README, CHANGELOG, `pyproject.toml`, module docstrings, the release scripts, the CI workflow and targeted greps; updated the same day for version 1.6.0. Anything not verified is marked as such. This is a public repository: this file holds repository-relative paths only and nothing about internal systems.

## 1. High-Level Purpose

An MIT-licensed Python package (PyPI: `aion-indian-market-calendar`, version `1.6.0` in `pyproject.toml`, latest on PyPI `1.5.1`) that answers when Indian markets trade and settle: trading days, NSE Clearing settlement days, intraday phases (pre-open, continuous, closing auction, post-close, Muhurat), derivative expiry dates, and holidays for NSE, BSE, MCX and currency derivatives. Answers come from bundled data; an optional hash-verified refresh brings newer data without a release. Runtime dependencies: `pytz`, `tzdata`. Python `>=3.10`. Part of AION Analytics' open-source infrastructure.

Git: independent public repository on GitHub (organisation `AION-Analytics-India`), branch `main`. Releases are published only by the tag-triggered workflow (PyPI trusted publishing).

## 2. Directory Structure

Tracked files. Ignored local items: `dist/`, `*.egg-info/`, `.pytest_cache/`, `__pycache__/`.

```
aion-indian-market-calendar/
├── README.md  CHANGELOG.md  CONTRIBUTING.md  LICENSE  pyproject.toml  .gitignore
├── AGENTS.md  CLAUDE.md  SITE_MAP.md        agent contract, agent entry point, this map
├── .github/workflows/publish.yml            tag-triggered: tests (3.10, 3.11, 3.13 on three OSes), no-egress, build, publish
├── src/aion_indian_market_calendar/
│   ├── __init__.py                          public API and module-level helpers
│   ├── __main__.py                          CLI: update, poll
│   ├── calendar.py                          IndiaMarketCalendar and session logic
│   ├── microstructure.py                    settlement days, phases, expiries, Muhurat (1.6.0)
│   ├── models.py                            Event, EventPolicy, SessionRule, SessionSegment ...
│   ├── store.py                             verified data store and refresh
│   ├── live_overrides.py                    live event overrides
│   ├── live_events.json                     117-byte live events file shipped in the package
│   └── data/  (__init__.py, holidays_2026.json, manifest.json)
├── tests/                                   8 files, 120 tests (57 in test_microstructure.py)
├── scripts/                                 bump_version.sh, verify_release_ready.sh
├── examples/offline_session_checks.py
└── docs/                                    TELEMETRY_AUDIT.md, tutorials/, campaign-assets/ge01-calendar.jpg
```

## 3. Core Components & Scripts

| Path | Purpose | Dependencies (Internal/External) |
| :--- | :--- | :--- |
| `src/aion_indian_market_calendar/__init__.py` | Public API: `IndiaMarketCalendar`, `is_market_open`, `is_continuous_trading`, `next_trading_day`, and from 1.6.0 `is_trading_day`, `is_settlement_day`, `settlement_holidays`, `get_market_phase`, `get_expiry_day`, `is_muhurat_trading`, `muhurat_session` and the phase constants | Internal: `calendar.py`, `models.py`, `microstructure.py` |
| `src/aion_indian_market_calendar/calendar.py` | Trading days, sessions, holidays, closing auction rules per exchange and segment | Internal: `models.py`, `store.py`, `live_overrides.py`, bundled `data/`. External: `pytz`, `tzdata`. Reads env `AION_IN_CALENDAR_URL`, a user cache folder under the home directory, and env `AION_IMI_TAXONOMY_CACHE_DIR` (see section 6) |
| `src/aion_indian_market_calendar/microstructure.py` | Settlement days (NSE Clearing list), intraday phases, expiry days (NSE/FAOP/68747, BSE 20250623-59), Muhurat sessions. Wraps `IndiaMarketCalendar`; fetches nothing; raises outside the bundled data range | Internal: `calendar.py`, `models.py` |
| `src/aion_indian_market_calendar/models.py` | Dataclasses for events, policies and session rules | Used by `calendar.py` |
| `src/aion_indian_market_calendar/store.py` | Market data, its manifest, and the refresh that needs no release: every file must verify against its hash before any is adopted | External (only on a refresh): the public data repository `aion-market-calendar-data` over HTTPS. Env: `AION_IN_CALENDAR_URL`, `AION_IN_CALENDAR_CACHE`, `AION_IN_CALENDAR_OFFLINE` |
| `src/aion_indian_market_calendar/live_overrides.py` | Live event overrides applied on top of the bundled data | Internal: `calendar.py`, `live_events.json` |
| `src/aion_indian_market_calendar/__main__.py` | CLI: `update` runs the verified refresh (fixed in 1.6.0; `--refresh-url` accepted and ignored), `poll` reads NSE circulars RSS into a review file | Internal: `store.py`. External: NSE circulars RSS (`poll`, needs `feedparser`) |
| `src/aion_indian_market_calendar/data/holidays_2026.json`, `manifest.json` | Bundled 2026 data (range 2026-01-01 to 2026-12-25) with source URLs (NSE, MCX, BSE, SEBI) | Verified by hash before use |
| `scripts/verify_release_ready.sh` | Release gate: no forbidden imports, tag matches version, tests, build, clean install | `pytest`, a build |
| `scripts/bump_version.sh` | Version bump helper | Edits `pyproject.toml` (not read in detail) |
| `.github/workflows/publish.yml` | On tag `v*`: test matrix, no-egress check, build, `twine check`, publish via trusted publishing | GitHub Actions |
| `tests/test_microstructure.py` | 57 tests (7 for the naive-datetime warning): settlement list equals NSE's 2026 clearing list, phases at every boundary, CAS before and after 7 Dec 2026, Muhurat, 13 expiry cases including holiday shifts, refusals | Explicit calendar from the bundled file, so a refresh cannot change expectations |
| `tests/test_calendar.py`, `test_live_overrides.py`, `test_firewall.py`, `test_no_egress.py`, `test_no_telemetry.py`, `test_incident_20260626.py` | Calendar behaviour; no network unless asked; no identifier; the 2026-06-26 incident | |
| `examples/offline_session_checks.py` | Deterministic offline session checks | |

## 4. External Repo Dependencies

Reads from other AION repositories: **only one, and it is public.**

| Repository | What | Direction | Where |
| :--- | :--- | :--- | :--- |
| `AION-Analytics-India/aion-market-calendar-data` (public, GitHub) | The verified data files the optional refresh downloads | read, over HTTPS, only on a refresh | `store.py` |

No tracked file refers to a private repository or to a local filesystem path. No database. Data sources cited inside the bundled data: nseindia.com, mcxindia.com, bseindia.com, sebi.gov.in.

## 5. Scheduled Jobs

None defined in this repository. `publish.yml` runs on tag push only; there is no cron, launchd or scheduler file. The `poll` CLI command is run by hand.

## 6. Legacy & Cleanup Candidates

### Resolved in 1.6.0 (2026-10-25)

| Item | Resolution |
| :--- | :--- |
| `README.md` began with Hugging Face front matter and "This is an open-source Python package surface on Hugging Face" | Removed; the README now opens with the package description and a list of where it is published. The Hugging Face documentation page keeps its own card, which is separate |
| CI matrix tested Python 3.9 while `requires-python` is `>=3.10` | Matrix is now 3.10, 3.11, 3.13 |
| CLI `update` defaulted to a live-events URL ignored since 1.4.1, and errored without one | Runs the verified refresh; the option is kept and ignored with a warning |
| No `AGENTS.md`, `CLAUDE.md` | Added, public-safe |

### Still open

| Path | Note |
| :--- | :--- |
| Naive datetimes | From 1.6.0 still read as IST, now with a `UserWarning` (`calendar._coerce_datetime`). Refusing them outright, as the Lithuanian sibling does, would break existing callers; not decided |
| `src/aion_indian_market_calendar/calendar.py` | Reads an env var named `AION_IMI_TAXONOMY_CACHE_DIR`; the name refers to a different AION product. Naming review |
| Bundled data range ends 2026-12-25 | Settlement and expiry questions after that date raise until 2027 data is published to the data repository |
| `live_events.json` | 117 bytes, untouched since the first commit; purpose not checked |
| `docs/TELEMETRY_AUDIT.md` | Historical (as of 1.3.3); keep |
| `docs/campaign-assets/ge01-calendar.jpg` | Marketing image in a code repository |
| BANKEX and SENSEX50 expiries | Not supported: the BSE notice's rows for them were not unambiguous in the source read |

Mapping gaps: `calendar.py` was not read in full; manifest hashes of the bundled data were not re-verified in this session; CI history was not checked.
