"""Nothing reaches the network unless a refresh was asked for.

This is the test that would have caught the telemetry. Until 1.4.0 a refresh
against an AION host sent a persistent install identifier; a test asserting "no
unexpected egress" makes its return a build failure rather than something found
later in a proxy log.

The approach is to intercept ``socket.socket`` itself rather than the library's
own fetch helper. Patching the helper only proves the helper behaves; patching
the socket proves that *nothing anywhere* -- an import side effect, a dependency,
a future addition -- opened a connection.
"""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest


class _Tripwire:
    """Records every connection attempt and refuses all of them."""

    def __init__(self) -> None:
        self.attempts: list = []

    def install(self, monkeypatch) -> None:
        tripwire = self

        class NoSocket(socket.socket):
            def connect(self, address, *args, **kwargs):          # noqa: D102
                tripwire.attempts.append(address)
                raise AssertionError(f"unexpected network egress to {address!r}")

            def connect_ex(self, address, *args, **kwargs):       # noqa: D102
                tripwire.attempts.append(address)
                raise AssertionError(f"unexpected network egress to {address!r}")

        monkeypatch.setattr(socket, "socket", NoSocket)
        # urllib builds connections through create_connection, which would
        # otherwise bypass the subclass entirely.
        def no_create_connection(address, *args, **kwargs):
            tripwire.attempts.append(address)
            raise AssertionError(f"unexpected network egress to {address!r}")
        monkeypatch.setattr(socket, "create_connection", no_create_connection)


@pytest.fixture
def tripwire(monkeypatch):
    wire = _Tripwire()
    wire.install(monkeypatch)
    return wire


def test_importing_the_package_opens_no_connection(tripwire, monkeypatch):
    """An import must never phone home. This is where telemetry would hide."""
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    import importlib

    import aion_indian_market_calendar
    importlib.reload(aion_indian_market_calendar)
    assert tripwire.attempts == []


def test_constructing_a_calendar_opens_no_connection(tripwire, monkeypatch, tmp_path):
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    from aion_indian_market_calendar import store
    from aion_indian_market_calendar.calendar import IndiaMarketCalendar

    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set()})
    IndiaMarketCalendar()
    assert tripwire.attempts == []


def test_answering_questions_opens_no_connection(tripwire, monkeypatch, tmp_path):
    """The common path -- construct, ask, done -- must be entirely local."""
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    from datetime import date

    from aion_indian_market_calendar import store
    from aion_indian_market_calendar.calendar import IndiaMarketCalendar

    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set()})
    cal = IndiaMarketCalendar()
    for method in ("is_trading_day", "is_market_open"):
        if hasattr(cal, method):
            try:
                getattr(cal, method)(date(2026, 6, 10))
            except TypeError:
                pass
    assert tripwire.attempts == []


def test_offline_mode_opens_no_connection_even_on_an_explicit_refresh(tripwire, monkeypatch):
    """Air-gapped means air-gapped, including when a caller forces a refresh."""
    monkeypatch.setenv("AION_IN_CALENDAR_OFFLINE", "1")
    from aion_indian_market_calendar import store

    assert "offline" in store.refresh(force=True)
    assert tripwire.attempts == []


def test_a_refresh_fetches_only_the_configured_host(monkeypatch, tmp_path):
    """One request per resource, none to anywhere else.

    Recorded at the fetch layer rather than the socket, because here we want the
    URLs. The socket tests above prove nothing sneaks past this layer.
    """
    monkeypatch.delenv("AION_IN_CALENDAR_OFFLINE", raising=False)
    from urllib.parse import urlparse

    from aion_indian_market_calendar import store

    monkeypatch.setattr(store, "CACHE_DIR", tmp_path / "cache")
    store._state.update({"loaded": False, "data": {}, "source": "none", "warned": set()})

    requested: list[str] = []
    manifest = json.loads((store.BUNDLED_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest["last_updated"] = "2099-01-01T00:00:00+00:00"

    def fake_fetch(url, timeout=5):
        requested.append(url)
        if "manifest.json" in url:
            return json.dumps(manifest).encode()
        name = url.rsplit("/", 1)[-1].split("?", 1)[0]
        return (store.BUNDLED_DIR / name).read_bytes()

    monkeypatch.setattr(store, "_fetch", fake_fetch)
    store.refresh(force=True)

    expected_host = urlparse(store.REMOTE_BASE).hostname
    for url in requested:
        assert urlparse(url).hostname == expected_host, f"reached {url}"
    # the manifest, then each file it lists, and nothing more
    assert len(requested) == 1 + len(manifest["files"])


def test_no_header_carries_an_identifier(monkeypatch):
    """Whatever is sent, it is not an identifier."""
    from aion_indian_market_calendar.calendar import IndiaMarketCalendar

    headers = IndiaMarketCalendar(
        refresh_url="https://api.aiondashboard.site/v1/calendar/live")._refresh_headers()
    assert set(headers) == {"User-Agent"}
    assert not any(k.lower().startswith("x-") for k in headers)
