"""The 2026-06-26 incident, reproduced and rejected.

What happened: a refresh with no integrity check wrote a 105-byte live-events
delta -- ``{version, events, deleted_ids}`` -- over a 117 KB calibrated taxonomy
file, wiping a production sector engine.

The guard added at the time checked a size floor and four required top-level
keys. That stops *that* payload. It does not stop a correctly-shaped but wrong
file, and it is not integrity verification: it asks "does this look roughly like
a taxonomy" rather than "is this the file the maintainer signed".

These tests assert both layers. The hash is the primary guard and rejects any
substitution; the structural check is kept as a second line because defence that
costs nothing is worth keeping.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aion_indian_market_calendar import store

# The shape of the payload that actually caused the incident.
INCIDENT_DELTA = {
    "version": "20260626-001",
    "events": [],
    "deleted_ids": [],
}


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set()})
    yield
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set()})


def _staged(tmp_path: Path) -> Path:
    """A directory holding the real manifest and the real data beside it."""
    directory = tmp_path / "published"
    directory.mkdir()
    for item in store.BUNDLED_DIR.glob("*.json"):
        (directory / item.name).write_bytes(item.read_bytes())
    return directory


def test_the_incident_payload_is_rejected_by_the_hash(tmp_path):
    """A small delta substituted for a real data file fails verification.

    This is the primary guard and the one that was missing in June.
    """
    directory = _staged(tmp_path)
    target = next(p for p in directory.glob("holidays_*.json"))
    original_size = target.stat().st_size
    target.write_text(json.dumps(INCIDENT_DELTA), encoding="utf-8")

    assert target.stat().st_size < 200, "the incident payload was ~105 bytes"
    assert original_size > 10_000, "the file it overwrote was large"

    ok, reason = store._verify(directory)
    assert not ok
    assert "hash" in reason


def test_a_correctly_shaped_but_wrong_file_is_also_rejected(tmp_path):
    """The structural guard could not catch this; the hash does.

    A file that passes every size and key check is still not the file the
    maintainer signed. That is the difference between 'looks plausible' and
    'is the one we published'.
    """
    directory = _staged(tmp_path)
    target = next(p for p in directory.glob("holidays_*.json"))
    payload = json.loads(target.read_text(encoding="utf-8"))
    # Same shape, same keys, comfortably over any size floor -- one event removed.
    payload["events"] = payload["events"][:-1]
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    assert target.stat().st_size > 10_000
    assert set(payload) >= {"timezone", "version", "events"}

    ok, reason = store._verify(directory)
    assert not ok and "hash" in reason


def test_a_remote_serving_the_incident_payload_is_not_adopted(monkeypatch, tmp_path):
    """End to end: the download path refuses it and keeps what it had.

    Nothing is swapped in, because verification happens in staging and the swap
    is all-or-nothing.
    """
    monkeypatch.delenv("AION_IN_CALENDAR_OFFLINE", raising=False)
    manifest = json.loads((store.BUNDLED_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["last_updated"] = "2099-01-01T00:00:00+00:00"    # newer, so it is tried

    def fake_fetch(url, timeout=5):
        if "manifest.json" in url:
            return json.dumps(manifest).encode()
        return json.dumps(INCIDENT_DELTA).encode()            # the incident payload

    monkeypatch.setattr(store, "_fetch", fake_fetch)
    result = store.refresh(force=True)
    assert "verification failed" in result
    assert store.source() in {"bundled", "cache"}
    assert store.status()["rule_only"] is False


def test_the_structural_guard_is_still_present():
    """Kept as a second line. Cheap, and it names the incident in its message."""
    from aion_indian_market_calendar.calendar import _assert_payload_is_taxonomy
    with pytest.raises(ValueError, match="2026-06-26"):
        _assert_payload_is_taxonomy("taxonomy.yaml", json.dumps(INCIDENT_DELTA).encode())


# --------------------------------------------------------------------------
# The taxonomy path, hardened in 1.4.1.
#
# The incident was on this path, not the calendar data one, and the guard added
# at the time left the door it came through open: the hash check ran only `if
# expected_hash`, so a manifest that omitted the field skipped verification
# entirely. The thing being verified decided whether to be verified.
# --------------------------------------------------------------------------

def test_a_manifest_without_a_hash_is_refused(tmp_path, monkeypatch):
    """Omitting sha256 used to skip verification. It is now a refusal."""
    from aion_indian_market_calendar.calendar import IndiaMarketCalendar

    cal = IndiaMarketCalendar()
    monkeypatch.setattr(cal, "_taxonomy_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(cal, "_fetch_bytes", lambda url: json.dumps(INCIDENT_DELTA).encode())

    manifesto = {
        "version": "v9",
        "files": [{"name": "some_other_table.yaml", "path": "/taxonomy/x.yaml"}],
    }
    with pytest.raises(ValueError, match="no sha256"):
        cal._download_taxonomy_manifesto_update("https://example.invalid/m.json", manifesto)
    assert not list(tmp_path.iterdir()), "nothing may be written when verification is refused"


def test_nothing_is_written_until_every_file_verifies(tmp_path, monkeypatch):
    """Writing each file as it verified left earlier ones on disk when a later
    one failed -- partial adoption, the failure staging exists to prevent."""
    import hashlib

    from aion_indian_market_calendar.calendar import IndiaMarketCalendar

    good = b"metadata:\n  x: 1\nconfig:\n  y: 2\nsectors: []\ncategories: []\n" + b"#pad\n" * 3000
    cal = IndiaMarketCalendar()
    monkeypatch.setattr(cal, "_taxonomy_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(cal, "_fetch_bytes", lambda url: good)

    manifesto = {"version": "v9", "files": [
        {"name": "first.yaml", "path": "/t/first.yaml",
         "sha256": hashlib.sha256(good).hexdigest()},          # verifies
        {"name": "second.yaml", "path": "/t/second.yaml",
         "sha256": "0" * 64},                                   # does not
    ]}
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        cal._download_taxonomy_manifesto_update("https://example.invalid/m.json", manifesto)
    assert not list(tmp_path.iterdir()), (
        "first.yaml verified and must still not be on disk: the batch failed"
    )
