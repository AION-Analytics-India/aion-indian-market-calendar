"""Concurrent refreshers and readers sharing one cache directory.

Readers must only ever see a complete verified dataset (old or new, never a mixture, never
rule-only), concurrent refreshers must all end on the same verified set, and a slow refresher
must never switch the cache back to an older dataset. Covered with threads in one process and
with separate processes against a local HTTP server; nothing leaves the machine.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time as _time
from datetime import date
from pathlib import Path

import pytest

import aion_indian_market_calendar as pkg
from aion_indian_market_calendar import IndiaMarketCalendar, microstructure as ms, store

OLD_DIR = Path(__file__).resolve().parent / "fixtures" / "dataset_2026_10_18"
NEW_DIR = Path(__file__).resolve().parent / "fixtures" / "dataset_2026_11_03"
MUHURAT = date(2026, 11, 8)
OLD_SEG = [("18:15", "19:15")]
NEW_SEG = [("14:20", "15:30")]


def _reset_state() -> None:
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set(),
                         "directory": None, "manifest": {}, "identity": None, "signature": None,
                         "last_sync": 0.0, "last_attempt": 0.0, "last_refresh": None})
    pkg._bundled_calendar.cache_clear()
    ms._calendar.cache_clear()


def _segments(cal) -> list[tuple[str, str]]:
    return [(s.open.strftime("%H:%M"), s.close.strftime("%H:%M")) for s in cal.get_session(MUHURAT, market="NSE")]


@pytest.fixture
def env(monkeypatch, tmp_path):
    old_bundle = tmp_path / "old_bundle"
    shutil.copytree(OLD_DIR, old_bundle)
    monkeypatch.delenv("AION_IN_CALENDAR_OFFLINE", raising=False)
    monkeypatch.setattr(store, "BUNDLED_DIR", old_bundle)
    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(store, "SYNC_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(store, "RETRY_AFTER_FAILURE_SECONDS", 0)
    _reset_state()
    yield tmp_path
    _reset_state()


def _serving(directory: Path, delay: float = 0.0):
    def fetch(url: str, timeout: int = 5):
        name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        if name != "manifest.json" and delay:
            _time.sleep(delay)
        return (directory / name).read_bytes()
    return fetch


def test_concurrent_refreshers_and_readers_in_one_process(env, monkeypatch):
    monkeypatch.setattr(store, "_fetch", _serving(NEW_DIR, delay=0.02))
    store.CACHE_DIR.mkdir(parents=True)
    store._mark_checked()                       # readers start on the old bundle, not refreshing
    reader_cal = IndiaMarketCalendar()
    assert _segments(reader_cal) == OLD_SEG

    seen: list = []
    errors: list = []
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                seen.append(tuple(_segments(reader_cal)))
                seen.append(tuple(_segments(IndiaMarketCalendar.bundled(2026))))
            except Exception as exc:  # noqa: BLE001
                errors.append(repr(exc))

    results: list[str] = []

    def refresher():
        results.append(store.refresh(force=True))

    readers = [threading.Thread(target=reader) for _ in range(3)]
    writers = [threading.Thread(target=refresher) for _ in range(6)]
    for t in readers + writers:
        t.start()
    for t in writers:
        t.join(30)
    _time.sleep(0.2)
    stop.set()
    for t in readers:
        t.join(30)

    assert errors == []
    assert set(seen) <= {tuple(OLD_SEG), tuple(NEW_SEG)}, "a reader saw neither complete dataset"
    assert all(store.refresh_succeeded(r) for r in results), results
    assert any(r.startswith("updated to") for r in results)
    assert _segments(reader_cal) == NEW_SEG
    assert store._verify(store.CACHE_DIR / "datasets" / (store.CACHE_DIR / "ACTIVE").read_text()) == (True, "ok")
    assert not list(store.CACHE_DIR.glob(".staging-*"))
    assert not list(store.CACHE_DIR.glob(".*.tmp"))


def test_a_slow_refresher_never_switches_back_to_an_older_dataset(env, monkeypatch):
    """B starts with the old remote, A adopts the new one meanwhile; B must not adopt."""
    store.CACHE_DIR.mkdir(parents=True)
    newer_manifest = json.loads((OLD_DIR / "manifest.json").read_text())
    older_but_newer_than_bundle = dict(newer_manifest, last_updated="2026-10-25T00:00:00+00:00")
    old_remote = store.CACHE_DIR.parent / "old_remote"
    shutil.copytree(OLD_DIR, old_remote)
    (old_remote / "manifest.json").write_text(json.dumps(older_but_newer_than_bundle))

    started = threading.Event()
    release = threading.Event()

    def slow_old_fetch(url, timeout=5):
        name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        if name != "manifest.json":
            started.set()
            release.wait(10)
        return (old_remote / name).read_bytes()

    monkeypatch.setattr(store, "_fetch", slow_old_fetch)
    result_b: list[str] = []
    b = threading.Thread(target=lambda: result_b.append(store.refresh(force=True)))
    b.start()
    assert started.wait(10)
    monkeypatch.setattr(store, "_fetch", _serving(NEW_DIR))
    assert store.refresh(force=True).startswith("updated to 2026-11-03")
    release.set()
    b.join(10)
    assert result_b == ["already current"]
    assert (store.CACHE_DIR / "ACTIVE").read_text().startswith("2026.11.03-")
    _reset_state()
    assert store.status()["dataset_version"] == "2026.11.03"


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def test_concurrent_processes_share_one_cache_safely(env):
    """Separate processes, one cache, a real (loopback) HTTP remote."""
    handler = functools.partial(_Quiet, directory=str(NEW_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    cache = env / "shared_cache"
    src_root = str(Path(pkg.__file__).resolve().parent.parent)
    child_env = dict(os.environ, AION_IN_CALENDAR_CACHE=str(cache),
                     AION_IN_CALENDAR_URL=f"http://127.0.0.1:{server.server_address[1]}",
                     PYTHONPATH=src_root + os.pathsep + os.environ.get("PYTHONPATH", ""))
    child_env.pop("AION_IN_CALENDAR_OFFLINE", None)
    old_bundle = str(env / "old_bundle")

    reader_code = textwrap.dedent(f"""
        import json, time
        from datetime import date
        from aion_indian_market_calendar import IndiaMarketCalendar, store
        from pathlib import Path
        store.BUNDLED_DIR = Path({old_bundle!r})
        store.SYNC_INTERVAL_SECONDS = 0
        store.CHECK_INTERVAL_SECONDS = 10**9          # readers never refresh; they only follow the cache
        store.CACHE_DIR.mkdir(parents=True, exist_ok=True); store._mark_checked()
        cal = IndiaMarketCalendar()
        seen, deadline = set(), time.time() + 4
        while time.time() < deadline:
            seen.add(tuple((s.open.strftime('%H:%M'), s.close.strftime('%H:%M'))
                           for s in cal.get_session(date(2026, 11, 8), market='NSE')))
            if store.status()['rule_only']:
                seen.add('RULE-ONLY')
        print(json.dumps(sorted(map(str, seen))))
    """)
    writer_code = textwrap.dedent(f"""
        from pathlib import Path
        from aion_indian_market_calendar import store
        store.BUNDLED_DIR = Path({old_bundle!r})
        print(store.refresh(force=True))
    """)
    try:
        readers = [subprocess.Popen([sys.executable, "-c", reader_code], env=child_env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        _time.sleep(1.0)
        writers = [subprocess.Popen([sys.executable, "-c", writer_code], env=child_env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        writer_out = [w.communicate(timeout=60) for w in writers]
        reader_out = [r.communicate(timeout=60) for r in readers]
    finally:
        server.shutdown()

    results = [out.strip() for out, _err in writer_out]
    assert all(store.refresh_succeeded(r) for r in results), writer_out
    assert any(r.startswith("updated to 2026-11-03") for r in results), results
    old, new = str(tuple(OLD_SEG)), str(tuple(NEW_SEG))
    for out, err in reader_out:
        seen = set(json.loads(out.strip().splitlines()[-1]))
        assert seen <= {old, new}, (seen, err)
        assert new in seen, "a running reader process must follow the refreshed cache"
    pointer = (cache / "ACTIVE").read_text()
    assert pointer.startswith("2026.11.03-")
    assert store._verify(cache / "datasets" / pointer) == (True, "ok")
    assert store._verify(cache) == (True, "ok")                      # flat copy for older versions
    assert not list(cache.glob(".staging-*")) and not list(cache.glob(".*.tmp"))
