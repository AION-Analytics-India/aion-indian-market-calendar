"""Auto-update without a release: discovery, verification, adoption and every reader following it.

Incident, 9 November 2026: corrected Muhurat timings (dataset 2026.11.03, NSE circular
NSE/CMTR/76941) were published to the data repository, and an installed 1.7.1 kept
answering 18:15-19:15. An isolated refresh with the installed code downloaded and verified
the new dataset correctly; what failed was everything after it:

* ``store.load()`` never looked again once a process had loaded;
* calendar objects copied events and session rules at construction, so the objects behind
  ``is_market_open`` and the ``microstructure`` helpers (both ``lru_cache``) kept the old
  rules after a successful refresh;
* a check made shortly before publication started a 24-hour wait;
* the CLI printed "Calendar update complete" whatever happened.

The "remote" here is a fake ``_fetch`` serving the real 2026.11.03 bundle; the "old
install" is the real published 2026.10.18 dataset, copied byte for byte from git into
``tests/fixtures/dataset_2026_10_18``. No test touches the network or the user's cache.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import time as _time
from datetime import date, datetime, time
from pathlib import Path

import pytest

import aion_indian_market_calendar as pkg
from aion_indian_market_calendar import IndiaMarketCalendar, microstructure as ms, store

OLD_DIR = Path(__file__).resolve().parent / "fixtures" / "dataset_2026_10_18"
NEW_DIR = Path(__file__).resolve().parent / "fixtures" / "dataset_2026_11_03"                       # the corrected bundle, dataset 2026.11.03
MUHURAT = date(2026, 11, 8)


def _manifest(directory: Path) -> dict:
    return json.loads((directory / "manifest.json").read_text(encoding="utf-8"))


def _segments(cal: IndiaMarketCalendar, market: str = "NSE") -> list[tuple[str, str]]:
    return [(s.open.strftime("%H:%M"), s.close.strftime("%H:%M")) for s in cal.get_session(MUHURAT, market=market)]


def _ist(hh: int, mm: int) -> datetime:
    return datetime(2026, 11, 8, hh, mm, tzinfo=pkg.get_ist_timezone())


def _reset_state() -> None:
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set(),
                         "directory": None, "manifest": {}, "identity": None, "signature": None,
                         "last_sync": 0.0, "last_attempt": 0.0, "last_refresh": None})
    pkg._bundled_calendar.cache_clear()
    ms._calendar.cache_clear()


class Remote:
    """A fake data host: serves one dataset directory, records requests, can fail on demand."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.requests: list[str] = []
        self.down = False
        self.corrupt = False
        self.drop_data = False

    def __call__(self, url: str, timeout: int = 5):
        self.requests.append(url)
        if self.down:
            return None
        name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        if name != "manifest.json":
            if self.drop_data:
                return None
            if self.corrupt:
                return b'{"version": "tampered", "events": [], "deleted_ids": []}'
        return (self.directory / name).read_bytes()


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Old dataset installed as the bundle, empty private cache, fake remote serving the new one."""
    old_bundle = tmp_path / "old_bundle"
    shutil.copytree(OLD_DIR, old_bundle)
    monkeypatch.delenv("AION_IN_CALENDAR_OFFLINE", raising=False)
    monkeypatch.setattr(store, "BUNDLED_DIR", old_bundle)
    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(store, "SYNC_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(store, "RETRY_AFTER_FAILURE_SECONDS", 0)
    remote = Remote(NEW_DIR)
    monkeypatch.setattr(store, "_fetch", remote)
    _reset_state()
    yield remote
    _reset_state()


def _age_last_check(hours: float) -> None:
    stamp = store.CACHE_DIR / ".last_check"
    past = _time.time() - hours * 3600
    os.utime(stamp, (past, past))


def _cache_fingerprint() -> dict[str, str]:
    return {p.relative_to(store.CACHE_DIR).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(store.CACHE_DIR.rglob("*")) if p.is_file() and p.name != ".last_refresh.json"}


# --------------------------------------------------------------------------
# Fixture sanity: the two datasets are the real ones.
# --------------------------------------------------------------------------
def test_fixtures_are_the_published_datasets():
    assert _manifest(OLD_DIR)["dataset_version"] == "2026.10.18"
    assert _manifest(NEW_DIR)["dataset_version"] == "2026.11.03"
    assert store._verify(OLD_DIR) == (True, "ok")
    assert store._verify(NEW_DIR) == (True, "ok")


# --------------------------------------------------------------------------
# 1. Old bundled data updates to the remote version, no reinstall
# --------------------------------------------------------------------------
def test_old_bundled_data_updates_to_remote_2026_11_03(env):
    before = IndiaMarketCalendar()
    assert store.status()["dataset_version"] == "2026.11.03"     # the first load refreshed
    assert _segments(before) == [("14:20", "15:30")]
    assert env.requests[0].endswith("/manifest.json")
    info = store.status()
    assert info["source"] == "cache" and info["last_refresh"]["ok"] is True
    assert info["last_refresh"]["result"] == "updated to 2026-11-03T02:04:20+00:00"
    assert info["freshness"] == "current"


def test_refresh_reports_exactly_what_it_did(env):
    assert store.refresh(force=True) == "updated to 2026-11-03T02:04:20+00:00"
    assert store.refresh(force=True) == "already current"
    assert store.refresh() == "checked recently"


# --------------------------------------------------------------------------
# 2. Muhurat 8 Nov: NSE from the circular; BSE and MCX keep their own status
# --------------------------------------------------------------------------
def test_muhurat_segments_and_their_status_per_exchange(env):
    store.refresh(force=True)
    cal = IndiaMarketCalendar()
    for market in ("NSE", "BSE", "MCX"):
        assert _segments(cal, market) == [("14:20", "15:30")], market
    nse = ms.muhurat_session(MUHURAT, "NSE", calendar=cal)
    bse = ms.muhurat_session(MUHURAT, "BSE", calendar=cal)
    mcx = ms.muhurat_session(MUHURAT, "MCX", calendar=cal)
    assert (nse.open, nse.close, nse.provisional) == (time(14, 20), time(15, 30), False)
    # BSE and MCX timings come from press reports of the exchange notices: still provisional.
    assert bse.provisional is True and mcx.provisional is True
    by_id = {e.id: e for e in cal.events_on("2026-11-08")}
    assert "NSE/CMTR/76941" in by_id["NSE_EQUITY_MUHURAT_20261108"].metadata["source"]
    assert by_id["BSE_EQUITY_MUHURAT_20261108"].metadata["status"] == "timings_from_press_reports"
    assert by_id["MCX_MUHRAT_TRADING_2026"].metadata["status"] == "timings_from_press_reports"


# --------------------------------------------------------------------------
# 3. Existing objects and module helpers do not keep stale rules
# --------------------------------------------------------------------------
def test_existing_objects_and_helpers_follow_a_refresh(env):
    env.down = True                                  # start on the old dataset
    instance = IndiaMarketCalendar()
    bundled = IndiaMarketCalendar.bundled(2026)
    assert store.status()["dataset_version"] == "2026.10.18"
    assert _segments(instance) == [("18:15", "19:15")]
    assert pkg.is_market_open("NSE", _ist(18, 30)) is True          # module helper, lru_cache'd
    assert ms.muhurat_session(MUHURAT, "NSE").open == time(18, 15)  # microstructure, lru_cache'd

    env.down = False
    assert instance.refresh(force=True) is True

    assert _segments(instance) == [("14:20", "15:30")]
    assert _segments(bundled) == [("14:20", "15:30")]
    assert pkg.is_market_open("NSE", _ist(14, 30)) is True
    assert pkg.is_market_open("NSE", _ist(18, 30)) is False
    assert ms.muhurat_session(MUHURAT, "NSE").open == time(14, 20)
    assert ms.get_market_phase(_ist(14, 30), "NSE") == ms.MUHURAT_TRADING
    assert instance.data_generation() == store.generation()


def test_a_running_process_adopts_data_another_process_refreshed(env):
    env.down = True
    cal = IndiaMarketCalendar()
    assert _segments(cal) == [("18:15", "19:15")]
    # Another process (same cache directory) refreshes; this one did nothing itself.
    staging = store.CACHE_DIR / ".staging-other"
    shutil.copytree(NEW_DIR, staging)
    store._adopt(staging, _manifest(NEW_DIR), (NEW_DIR / "manifest.json").read_bytes())
    assert _segments(cal) == [("14:20", "15:30")]
    assert pkg.next_trading_day("NSE", date(2026, 11, 7)) == MUHURAT


def test_objects_built_from_a_file_or_records_never_change(env, tmp_path):
    env.down = True
    fixed = IndiaMarketCalendar(events_json_path=str(OLD_DIR / "holidays_2026.json"))
    env.down = False
    store.refresh(force=True)
    assert _segments(fixed) == [("18:15", "19:15")]


# --------------------------------------------------------------------------
# 4. Offline mode uses verified cached or bundled data and never the network
# --------------------------------------------------------------------------
def test_offline_uses_a_verified_cache(env, monkeypatch):
    store.refresh(force=True)
    _reset_state()
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    env.requests.clear()
    cal = IndiaMarketCalendar()
    assert _segments(cal) == [("14:20", "15:30")]
    assert "offline" in store.refresh(force=True)
    assert env.requests == []
    assert store.status()["freshness"] == "indeterminate"


def test_offline_falls_back_to_the_bundle_when_the_cache_fails_verification(env, monkeypatch):
    store.refresh(force=True)
    for target in (store.CACHE_DIR / "holidays_2026.json", *store.CACHE_DIR.glob("datasets/*/holidays_2026.json")):
        target.write_text('{"tampered": true}', encoding="utf-8")
    _reset_state()
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    assert store.source() == "bundled"
    assert _segments(IndiaMarketCalendar()) == [("18:15", "19:15")]    # the verified old bundle


def test_a_newer_bundle_beats_an_older_cache(env, monkeypatch):
    # A cache left by an older install must not outrank a newer bundled copy.
    shutil.copytree(OLD_DIR, store.CACHE_DIR)
    monkeypatch.setattr(store, "BUNDLED_DIR", NEW_DIR)
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    _reset_state()
    assert store.source() == "bundled"
    assert store.status()["dataset_version"] == "2026.11.03"


# --------------------------------------------------------------------------
# 5. Failures never corrupt or replace the data in use
# --------------------------------------------------------------------------
def test_unreachable_remote_keeps_existing_data(env):
    store.refresh(force=True)
    before = _cache_fingerprint()
    env.down = True
    assert store.refresh(force=True) == "remote unreachable"
    assert _cache_fingerprint() == before
    assert store.status()["dataset_version"] == "2026.11.03"
    assert store.status()["last_refresh"]["ok"] is False


@pytest.mark.parametrize("failure, expected", [
    ("corrupt", "verification failed"),
    ("drop_data", "could not download"),
])
def test_invalid_or_partial_downloads_are_never_adopted(env, failure, expected):
    env.down = True
    IndiaMarketCalendar()                                    # loaded on the old bundle
    env.down = False
    setattr(env, failure, True)
    result = store.refresh(force=True)
    assert result.startswith(expected)
    assert not list(store.CACHE_DIR.glob(".staging-*")), "staging must be cleaned up"
    assert not (store.CACHE_DIR / "ACTIVE").exists()
    assert not (store.CACHE_DIR / "manifest.json").exists()
    assert store.status()["dataset_version"] == "2026.10.18"


def test_an_older_remote_is_refused_even_when_forced(env, monkeypatch):
    store.refresh(force=True)
    monkeypatch.setattr(env, "directory", OLD_DIR)
    before = _cache_fingerprint()
    result = store.refresh(force=True)
    assert result.startswith("remote is older than the active dataset")
    assert _cache_fingerprint() == before
    assert store.status()["dataset_version"] == "2026.11.03"


def test_adoption_is_one_pointer_switch(env):
    store.refresh(force=True)
    pointer = (store.CACHE_DIR / "ACTIVE").read_text(encoding="utf-8")
    target = store.CACHE_DIR / "datasets" / pointer
    assert pointer.startswith("2026.11.03-")
    assert store._verify(target) == (True, "ok")
    # Flat copy kept for library versions up to 1.7.2 that share the cache.
    assert store._verify(store.CACHE_DIR) == (True, "ok")
    assert store.status()["directory"] == str(target)


# --------------------------------------------------------------------------
# 6. Throttling never blocks adoption once a check is eligible
# --------------------------------------------------------------------------
def test_a_check_just_before_publication_does_not_block_adoption_for_long(env, monkeypatch):
    """The 9 Nov sequence: a conclusive check at 11:19 saw the old remote; the fix was
    published at 12:14. The process must adopt it once the check is due again,
    without a restart."""
    monkeypatch.setattr(env, "directory", OLD_DIR)        # remote still old
    cal = IndiaMarketCalendar()
    assert store.status()["last_refresh"]["result"] == "already current"
    monkeypatch.setattr(env, "directory", NEW_DIR)        # publication
    assert _segments(cal) == [("18:15", "19:15")]         # throttled: not due yet
    _age_last_check(25)                                   # the next day
    assert _segments(cal) == [("14:20", "15:30")]         # same object, same process


def test_a_failed_check_is_retried(env):
    env.down = True
    cal = IndiaMarketCalendar()
    assert store.status()["last_refresh"]["result"] == "remote unreachable"
    env.down = False
    assert _segments(cal) == [("14:20", "15:30")]         # inconclusive, so not throttled


# --------------------------------------------------------------------------
# 7. Freshness is visible, so a financial caller can fail closed
# --------------------------------------------------------------------------
def test_freshness_states(env, monkeypatch):
    env.down = True
    IndiaMarketCalendar()
    assert store.freshness()[0] == "indeterminate"        # never checked conclusively
    env.down = False
    store.refresh(force=True)
    assert store.freshness()[0] == "current"
    _age_last_check(72)
    env.down = True                                       # cannot re-check
    state, reason = store.freshness()
    assert state == "stale" and "remote unreachable" in reason


# --------------------------------------------------------------------------
# 8. The CLI does not claim success when the refresh failed
# --------------------------------------------------------------------------
def _run_cli(monkeypatch, *argv):
    from aion_indian_market_calendar import __main__ as cli
    monkeypatch.setattr("sys.argv", ["aion-indian-market-calendar", *argv])
    return cli.main()


def test_cli_reports_a_failed_refresh(env, monkeypatch, caplog):
    env.down = True
    with caplog.at_level(logging.INFO):
        code = _run_cli(monkeypatch, "update", "--force")
    assert code == 1
    assert "FAILED" in caplog.text and "remote unreachable" in caplog.text
    assert "update complete" not in caplog.text


def test_cli_reports_success_and_offline(env, monkeypatch, caplog):
    with caplog.at_level(logging.INFO):
        assert _run_cli(monkeypatch, "update", "--force") == 0
    assert "updated to 2026-11-03" in caplog.text
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    assert _run_cli(monkeypatch, "update", "--force") == 2
