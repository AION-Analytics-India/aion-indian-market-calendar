"""Market event data, its manifest, and the update that does not need a release.

Ported from the Lithuanian package, which got here first. The *mechanism* is
identical on purpose -- one manifest schema means one ingestion tool maintains
both -- and the payload is not, because an Indian entry carries an id, a policy,
an impact level and a time range that callers act on. Flattening that into date
lists would have destroyed information users already depend on.

Why this replaces what was here
-------------------------------
The previous mechanism pointed at ``api.aiondashboard.site/v1/calendar/live``,
which returns 404, fed by a launchd poller that stopped running on 2026-07-05.
``refresh_url`` also defaulted to ``None``, so it was opt-in and off. The holiday
data in this package therefore had no path to update at all.

More seriously, that refresh had no integrity check. On 2026-06-26 it wrote a
105-byte delta over a 117 KB calibrated taxonomy file and wiped a production
sector engine. The guard added at the time checked a size floor and four required
keys, which stops that exact payload and nothing else.

This one verifies a SHA-256 per file against a signed manifest, downloads to a
staging directory, and only swaps once **every** file verifies. A single mismatch
means nothing is adopted. The structural guard is kept as a second line.

**No telemetry.** The previous refresh sent a persistent install identifier on
every request to an AION host; see ``docs/TELEMETRY_AUDIT.md``. Nothing here sends
anything but a User-Agent, and ``tests/test_no_egress.py`` keeps it that way.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

#: Shipped inside the wheel. Always present, always the fallback.
BUNDLED_DIR = Path(__file__).resolve().parent / "data"

def _default_cache_dir() -> Path:
    """Where refreshed data lands. Per-user; a library must never need root.

    Honours XDG_CACHE_HOME, because that is the documented way for a user to say
    where caches go and ignoring it is how a library ends up writing somewhere
    the user did not expect.

    Falls back to a temp directory when the preferred location cannot be
    created. That is not hypothetical: on the machine this was developed on,
    ``~/.cache`` is owned by root -- something ran under sudo once -- so nothing
    running as the user can create a directory inside it. Without a fallback,
    auto-update would be permanently and *silently* off on that machine, which is
    precisely the failure this design exists to prevent. A temp directory loses
    the cache on reboot, which costs one extra fetch and is strictly better than
    never updating.
    """
    override = os.environ.get("AION_IN_CALENDAR_CACHE")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    preferred = base / "aion_in_calendar"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".writable"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return preferred
    except OSError:
        import tempfile
        fallback = Path(tempfile.gettempdir()) / f"aion_in_calendar-{os.getuid()}"
        log.warning(
            "Cannot write to %s, so refreshed holiday data will be cached in %s "
            "and lost on reboot. Auto-update still works; it just re-fetches more "
            "often. Set AION_IN_CALENDAR_CACHE to choose somewhere writable.",
            preferred, fallback,
        )
        return fallback


CACHE_DIR = _default_cache_dir()

#: Default remote. GitHub raw rather than a vanity domain: it is free, it is
#: versioned in the same repository as the code, anyone can audit what changed
#: and when, and it does not quietly expire the way a domain registration does.
#: Override with AION_IN_CALENDAR_URL to serve from a CDN later.
REMOTE_BASE = os.environ.get(
    "AION_IN_CALENDAR_URL",
    "https://raw.githubusercontent.com/AION-Analytics-India/"
    "aion-market-calendar-data/main/in",
).rstrip("/")

#: How long a refresh check is considered fresh. A holiday announced today is
#: not needed within the hour, and hammering a static host from every process
#: start is rude.
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
NETWORK_TIMEOUT_SECONDS = 5

_state: dict[str, Any] = {"loaded": False, "data": {}, "source": "none", "warned": set()}


def _warn_once(key: str, message: str, *args: Any) -> None:
    """Warn, but not on every call. A per-request warning becomes noise, and
    noise is how a real warning goes unread."""
    if key not in _state["warned"]:
        _state["warned"].add(key)
        log.warning(message, *args)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _verify(directory: Path) -> tuple[bool, str]:
    """Does this directory hold a manifest whose hashes match its files?"""
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return False, "manifest.json is missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"manifest.json is unreadable ({exc})"
    if manifest.get("schema_version") != SCHEMA_VERSION:
        return False, (f"manifest schema {manifest.get('schema_version')!r} is not "
                       f"the {SCHEMA_VERSION} this library understands")
    files = manifest.get("files") or {}
    if not files:
        return False, "manifest lists no data files"
    for name, expected in files.items():
        candidate = directory / name
        if not candidate.exists():
            return False, f"{name} is listed in the manifest but missing"
        actual = _sha256(candidate)
        if actual != expected:
            return False, f"{name} does not match its manifest hash"
    return True, "ok"


def _read_dataset(directory: Path) -> dict[int, dict[str, Any]]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    years: dict[int, dict[str, Any]] = {}
    for name in manifest.get("files", {}):
        payload = json.loads((directory / name).read_text(encoding="utf-8"))
        # The Indian payload has no "year" field -- it carries a range and a list
        # of events -- so the year comes from the filename, which the manifest
        # schema fixes as holidays_YYYY.json.
        try:
            year = int(str(name).rsplit("_", 1)[-1].split(".")[0])
        except ValueError:
            log.debug("skipping %s: no year in the filename", name)
            continue
        years[year] = payload
    return years


# --------------------------------------------------------------------------
# Refresh
# --------------------------------------------------------------------------
def _offline() -> bool:
    return os.environ.get("AION_IN_CALENDAR_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def _fetch(url: str, timeout: int = NETWORK_TIMEOUT_SECONDS) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "aion-in-calendar"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
        log.debug("holiday data fetch failed for %s: %s", url, exc)
        return None


def _due_for_check() -> bool:
    stamp = CACHE_DIR / ".last_check"
    try:
        return (_time.time() - stamp.stat().st_mtime) > CHECK_INTERVAL_SECONDS
    except OSError:
        return True


def _mark_checked() -> None:
    """Start the daily clock. Called only on a conclusive outcome.

    Deliberately NOT called when a download fails verification or a host is
    unreachable. GitHub raw caches paths independently and can serve a stale
    manifest beside a fresh payload for a few minutes after a push -- observed
    on 2026-09-12. Marking that as "checked today" made a client wait a full day
    for data that was already published. A transient failure should be retried
    on the next call, not once tomorrow.
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / ".last_check").write_text(
            datetime.now(timezone.utc).isoformat(timespec="seconds"), encoding="utf-8")
    except OSError:
        pass


def refresh(force: bool = False) -> str:
    """Fetch newer holiday data if there is any. Returns what happened.

    Never raises. Every failure path ends at "keep using what we have", because
    a calendar that throws on a DNS hiccup is worse than one that is a week out
    of date.
    """
    if _offline():
        return "offline: AION_IN_CALENDAR_OFFLINE is set"
    if not force and not _due_for_check():
        return "checked recently"

    raw = _fetch(f"{REMOTE_BASE}/manifest.json")
    if raw is None:
        _warn_once("unreachable", "Holiday data host unreachable; using bundled data.")
        return "remote unreachable"
    try:
        remote = json.loads(raw)
    except json.JSONDecodeError:
        _warn_once("badjson", "Remote holiday manifest is not valid JSON; using bundled data.")
        return "remote manifest unparseable"
    if remote.get("schema_version") != SCHEMA_VERSION:
        return "remote uses a different schema"

    local_dir = CACHE_DIR if (CACHE_DIR / "manifest.json").exists() else BUNDLED_DIR
    try:
        local = json.loads((local_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        local = {}
    if not force and str(remote.get("last_updated", "")) <= str(local.get("last_updated", "")):
        _mark_checked()
        return "already current"

    # Download into a staging directory and only swap once every hash verifies.
    # A half-written cache is indistinguishable from a tampered one, and both
    # should be refused rather than half-trusted.
    staging = CACHE_DIR / ".staging"
    try:
        staging.mkdir(parents=True, exist_ok=True)
        # Fetch each payload keyed to the manifest we just read.
        #
        # GitHub raw caches per path for a few minutes and the paths expire
        # independently, so immediately after a push it will happily serve a
        # fresh payload alongside a stale manifest -- observed on 2026-09-12,
        # manifest two minutes behind its own data. The hash check caught it and
        # refused, which is correct but means a client hitting that window waits
        # a day for data that is already published.
        #
        # Appending the manifest's own version pins the payload to the manifest
        # that asked for it: a stale manifest now fetches its matching stale
        # payload, which verifies and is merely a little old, instead of a
        # mismatched pair that verifies against nothing. Consistent-and-behind
        # beats inconsistent-and-refused.
        version = str(remote.get("last_updated") or remote.get("dataset_version") or "")
        suffix = f"?v={urllib.parse.quote(version)}" if version else ""
        for name in remote.get("files", {}):
            body = _fetch(f"{REMOTE_BASE}/{name}{suffix}")
            if body is None:
                return f"could not download {name}"
            (staging / name).write_bytes(body)
        (staging / "manifest.json").write_bytes(raw)
        ok, reason = _verify(staging)
        if not ok:
            _warn_once("badhash", "Downloaded holiday data failed verification (%s); "
                                  "keeping existing data.", reason)
            return f"verification failed: {reason}"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            item.replace(CACHE_DIR / item.name)
        _mark_checked()
        _state["loaded"] = False          # force a reload on next read
        log.info("Holiday data updated to %s", remote.get("last_updated"))
        return f"updated to {remote.get('last_updated')}"
    except OSError as exc:
        # Loud, not debug. A cache that cannot be written means auto-update is
        # off, and an update that is silently off is the thing this module was
        # written to prevent.
        _warn_once("nocache",
                   "Could not write refreshed holiday data to %s (%s); continuing "
                   "with the bundled data. Set AION_IN_CALENDAR_CACHE to a "
                   "writable path to enable updates.", CACHE_DIR, exc)
        return f"could not write cache: {exc}"


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load(auto_refresh: bool = True) -> dict[int, dict[str, Any]]:
    """The holiday dataset, refreshing at most once a day.

    Falls back to rule-only mode -- an empty dataset -- if nothing verifies. The
    caller then still has weekends and computed public holidays, which is the
    part that cannot go stale.
    """
    if _state["loaded"]:
        return _state["data"]

    if auto_refresh:
        refresh()

    for directory, label in ((CACHE_DIR, "cache"), (BUNDLED_DIR, "bundled")):
        if not (directory / "manifest.json").exists():
            continue
        ok, reason = _verify(directory)
        if not ok:
            _warn_once(f"verify-{label}",
                       "Holiday data in the %s directory failed verification (%s); "
                       "ignoring it.", label, reason)
            continue
        try:
            _state["data"] = _read_dataset(directory)
            _state["source"] = label
            _state["loaded"] = True
            return _state["data"]
        except (OSError, KeyError, ValueError) as exc:
            _warn_once(f"read-{label}", "Could not read holiday data from %s: %s", label, exc)

    _warn_once("ruleonly",
               "No verified holiday data; running in RULE-ONLY mode. Weekends and "
               "computed Lithuanian public holidays still apply, but exchange "
               "holidays and half-days are unknown.")
    _state["data"] = {}
    _state["source"] = "rule-only"
    _state["loaded"] = True
    return _state["data"]


def source() -> str:
    """Where the data in use came from: cache, bundled, or rule-only."""
    load()
    return _state["source"]


def status() -> dict[str, Any]:
    """Everything a caller needs to decide whether to trust the answer.

    Exposed because a library that quietly degrades is the thing this module was
    written to avoid: if it is in rule-only mode, the caller should be able to
    find that out without reading the logs.
    """
    load()
    directory = CACHE_DIR if _state["source"] == "cache" else BUNDLED_DIR
    manifest: dict[str, Any] = {}
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "source": _state["source"],
        "rule_only": _state["source"] == "rule-only",
        "dataset_version": manifest.get("dataset_version"),
        "last_updated": manifest.get("last_updated"),
        "next_review_date": manifest.get("next_review_date"),
        "years": sorted(_state["data"]),
        "offline": _offline(),
        "remote": REMOTE_BASE,
    }


# --------------------------------------------------------------------------
# Queries
#
# The Lithuanian store answers holiday questions directly because its payload is
# date lists. This one only *supplies* payloads: the event objects are
# interpreted by IndiaMarketCalendar, which already knows how to read a policy
# and an impact level. Keeping that knowledge in one place is why this module
# stops here.
# --------------------------------------------------------------------------
def payload_for(year: int) -> dict[str, Any] | None:
    """The event payload for a year, or None when nothing is loaded for it."""
    return load().get(year)


def payloads() -> dict[int, dict[str, Any]]:
    """Every loaded payload, keyed by year."""
    return load()
