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

This one verifies a SHA-256 per file against a SHA-256 manifest fetched over HTTPS, downloads to a
staging directory, and only swaps once **every** file verifies. A single mismatch
means nothing is adopted. The structural guard is kept as a second line.

**No telemetry.** The previous refresh sent a persistent install identifier on
every request to an AION host; see ``docs/TELEMETRY_AUDIT.md``. Nothing here sends
anything but a User-Agent, and ``tests/test_no_egress.py`` keeps it that way.

What changed in the 1.8.0 candidate (2026-11-09)
----------------------------------
Corrected Muhurat timings (dataset 2026.11.03) were published, verified and
downloadable, yet processes kept answering with the old timings. Four defects:

* ``load()`` returned its first answer for the life of the process: it never
  checked again, and never noticed that another process had refreshed the cache.
  It now re-checks when the daily check is due and re-reads when the verified
  data on disk changes (at most every ``SYNC_INTERVAL_SECONDS``).
* A verified cache was always preferred, even when the bundled copy was newer, and
  a forced refresh would adopt an *older* remote dataset. The newest verified
  dataset now wins, and an older remote is refused even when forced.
* Adoption replaced files one by one in a shared ``.staging`` directory. Each
  refresh now stages privately, moves the verified set into its own versioned
  directory, and switches one pointer file (``ACTIVE``) with an atomic rename.
  The flat files are still written, last-manifest-first, for older library
  versions that share the cache.
* Nobody could tell whether the answer was current. ``status()`` now reports the
  last conclusive check, the last refresh result and a ``freshness`` verdict
  (``current``, ``stale`` or ``indeterminate``) that a financial caller can use to
  fail closed. Calendar objects follow the store through ``generation()``.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
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
MAX_RESOURCE_BYTES = 2 * 1024 * 1024
MAX_DATA_FILES = 16

#: How often a process that has already loaded data looks at the disk again (a
#: few stat calls) and, when the daily check is due, at the remote. Bounded so a
#: hot query path costs one clock read between looks.
SYNC_INTERVAL_SECONDS = 60

#: After an inconclusive refresh (host unreachable, download refused), a running
#: process waits this long before trying the network again, so an outage does
#: not add a network timeout to every query.
RETRY_AFTER_FAILURE_SECONDS = 15 * 60

#: No conclusive check for longer than this and the data is reported "stale".
#: Two check intervals: one missed day is tolerated, two are not.
STALE_AFTER_SECONDS = 2 * CHECK_INTERVAL_SECONDS

_DATA_FILE = re.compile(r"^holidays_\d{4}\.json$")
_ACTIVE_POINTER = "ACTIVE"
_DATASETS_DIR = "datasets"
_LAST_REFRESH_FILE = ".last_refresh.json"
_KEEP_DATASETS = 3

_state: dict[str, Any] = {
    "loaded": False, "data": {}, "source": "none", "warned": set(),
    "directory": None, "manifest": {}, "identity": None, "generation": 0,
    "signature": None, "last_sync": 0.0, "last_attempt": 0.0, "last_refresh": None,
}

#: Results that mean the data in use is as current as the remote allows.
_SUCCESS_PREFIXES = ("updated to", "already current", "checked recently")


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


def _manifest_problem(manifest: Any) -> str | None:
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != SCHEMA_VERSION:
        return "manifest schema is unsupported"
    files = manifest.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_DATA_FILES:
        return "manifest lists no data files or exceeds the file limit"
    if not all(isinstance(n, str) and _DATA_FILE.fullmatch(n) and
               isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) for n, h in files.items()):
        return "manifest contains an unexpected file name or invalid hash"
    years = manifest.get("years")
    if not isinstance(years, list) or not all(type(y) is int for y in years) or set(years) != {int(n[9:13]) for n in files}:
        return "manifest years differ from its files"
    if not isinstance(manifest.get("dataset_version"), str) or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}(?:\.\d+)?", manifest["dataset_version"]):
        return "manifest dataset version is invalid"
    try:
        stamp = datetime.fromisoformat(manifest["last_updated"].replace("Z", "+00:00"))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            return "manifest update timestamp must be UTC"
        date.fromisoformat(manifest["next_review_date"])
        minimum = manifest.get("minimum_client_version")
        if minimum:
            from .software_updates import release_tuple
            if release_tuple(minimum) > release_tuple("1.8.0"):
                return "manifest needs a newer calendar client"
    except (KeyError, AttributeError, TypeError, ValueError):
        return "manifest metadata is invalid"
    return None


def _verify(directory: Path) -> tuple[bool, str]:
    """Does this directory hold a manifest whose hashes match its files?"""
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        return False, "manifest.json is missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"manifest.json is unreadable ({exc})"
    problem = _manifest_problem(manifest)
    if problem:
        return False, problem
    for name, expected in manifest["files"].items():
        candidate = directory / name
        if not candidate.is_file() or candidate.is_symlink():
            return False, f"{name} is listed in the manifest but missing or linked"
        if candidate.stat().st_size > MAX_RESOURCE_BYTES:
            return False, f"{name} exceeds the data size limit"
        if _sha256(candidate) != expected:
            return False, f"{name} does not match its manifest hash"
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            span = payload["range"]
            start, end = date.fromisoformat(span["start"]), date.fromisoformat(span["end"])
            year = int(name[9:13])
            if payload["timezone"] != "Asia/Kolkata" or not isinstance(payload["events"], list):
                raise ValueError("unsupported payload contract")
            if start > end or start.year != year or end.year != year:
                raise ValueError("payload range differs from file year")
            # Parse the real event/session contract before switching the active pointer.
            from .calendar import IndiaMarketCalendar
            IndiaMarketCalendar(_raw=payload)
        except (KeyError, TypeError, ValueError) as exc:
            return False, f"{name} has an invalid data schema ({type(exc).__name__})"
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


def _read_manifest(directory: Path) -> dict[str, Any]:
    try:
        return json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _version_key(manifest: dict[str, Any]) -> str:
    """Datasets are ordered by ``last_updated`` (ISO 8601, UTC, one format)."""
    stamp = str(manifest.get("last_updated") or "")
    if not stamp:
        return ""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds")


# --------------------------------------------------------------------------
# Which dataset is active
# --------------------------------------------------------------------------
def _active_pointer_dir() -> Path | None:
    try:
        name = (CACHE_DIR / _ACTIVE_POINTER).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not name or "/" in name or "\\" in name or name.startswith("."):
        return None
    return CACHE_DIR / _DATASETS_DIR / name


def _candidates() -> list[tuple[str, Path]]:
    """Every place verified data may live, in tie-break order."""
    found: list[tuple[str, Path]] = []
    pointed = _active_pointer_dir()
    if pointed is not None:
        found.append(("cache", pointed))
    found.append(("cache", CACHE_DIR))          # flat layout, also written by older versions
    found.append(("bundled", BUNDLED_DIR))
    return found


def _verified_candidates() -> list[tuple[str, Path, dict[str, Any]]]:
    """Every verified dataset, newest first (ties keep the tie-break order of _candidates)."""
    found: list[tuple[str, Path, dict[str, Any]]] = []
    for label, directory in _candidates():
        if not (directory / "manifest.json").exists():
            continue
        ok, reason = _verify(directory)
        if not ok:
            _warn_once(f"verify-{label}-{directory.name}",
                       "Holiday data in the %s directory failed verification (%s); "
                       "ignoring it.", label, reason)
            continue
        found.append((label, directory, _read_manifest(directory)))
    found.sort(key=lambda item: _version_key(item[2]), reverse=True)   # stable sort
    return found


def _select() -> tuple[str, Path, dict[str, Any]] | None:
    """The newest verified dataset. A cache never beats a newer bundled copy."""
    found = _verified_candidates()
    return found[0] if found else None


def _signature() -> tuple:
    """Cheap fingerprint of what is on disk: stat calls only, no hashing."""
    parts: list[Any] = []
    for name in (_ACTIVE_POINTER, "manifest.json"):
        try:
            st = (CACHE_DIR / name).stat()
            parts.append((name, st.st_mtime_ns, st.st_size))
        except OSError:
            parts.append((name, None))
    parts.append(str(CACHE_DIR))
    return tuple(parts)


# --------------------------------------------------------------------------
# Refresh
# --------------------------------------------------------------------------
def _offline() -> bool:
    return os.environ.get("AION_IN_CALENDAR_OFFLINE", "").strip().lower() in {"1", "true", "yes"}


def _fetch(url: str, timeout: int = NETWORK_TIMEOUT_SECONDS) -> bytes | None:
    try:
        from .software_updates import fetch_bytes
        # Explicit operator-configured loopback HTTP is supported for isolated
        # tests; the default approved source is HTTPS and redirects are refused.
        host = urllib.parse.urlsplit(REMOTE_BASE).hostname
        return fetch_bytes(url, max_bytes=MAX_RESOURCE_BYTES, network_authorized=True,
                           allow_test_http=host == "127.0.0.1")
    except (urllib.error.URLError, OSError, ValueError, PermissionError) as exc:
        log.debug("holiday data fetch refused (%s)", type(exc).__name__)
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


def refresh_succeeded(result: str) -> bool:
    """True when a :func:`refresh` result leaves the data as current as the remote allows."""
    return str(result).startswith(_SUCCESS_PREFIXES)


def _record(result: str, *, persist: bool = True) -> str:
    """Remember the outcome (in this process, and on disk for other processes)."""
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "result": result, "ok": refresh_succeeded(result)}
    _state["last_refresh"] = entry
    if not entry["ok"]:
        _state["last_attempt"] = _time.monotonic()
    if persist:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _atomic_write_bytes(CACHE_DIR / _LAST_REFRESH_FILE, json.dumps(entry).encode("utf-8"))
        except OSError:
            pass
    return result


def _atomic_write_bytes(target: Path, body: bytes) -> None:
    """Write a temp file unique to this call (process *and* thread), then rename over the target."""
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _adopt(staging: Path, manifest: dict[str, Any], raw_manifest: bytes) -> Path:
    """Move a verified staging directory into place and switch to it atomically.

    The switch is one rename of the ``ACTIVE`` pointer, so a reader sees either
    the old verified set or the new verified set, never a mixture.
    """
    datasets = CACHE_DIR / _DATASETS_DIR
    datasets.mkdir(parents=True, exist_ok=True)
    name = "{}-{}".format(
        re.sub(r"[^0-9A-Za-z._-]", "_", str(manifest.get("dataset_version") or "unknown")),
        hashlib.sha256(raw_manifest).hexdigest()[:12])
    target = datasets / name
    if target.exists() and not _verify(target)[0]:
        shutil.rmtree(target, ignore_errors=True)          # a broken leftover, never trusted
    try:
        os.replace(staging, target)
    except OSError:
        # Another refresher (process or thread) moved the same verified set into place
        # first: renaming onto a non-empty directory fails. Use theirs if it verifies.
        if not (target.exists() and _verify(target)[0]):
            raise
        shutil.rmtree(staging, ignore_errors=True)
    _atomic_write_bytes(CACHE_DIR / _ACTIVE_POINTER, name.encode("utf-8"))

    # Flat copy for library versions up to 1.7.2, which share this directory and
    # read only the flat files. Data first, manifest last; they verify hashes, so
    # a reader between two renames refuses the pair rather than trusting it.
    for item in sorted(target.iterdir(), key=lambda p: p.name == "manifest.json"):
        _atomic_write_bytes(CACHE_DIR / item.name, item.read_bytes())

    # Keep the active dataset and the few newest others; nothing outside datasets/.
    others = sorted((p for p in datasets.iterdir() if p.is_dir() and p.name != name),
                    key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in others[_KEEP_DATASETS - 1:]:
        shutil.rmtree(stale, ignore_errors=True)
    return target


@contextmanager
def _adoption_lock():
    """Serialize the version check and pointer switch across processes.

    A crashed writer's lock is not silently stolen. Refresh fails closed until
    its owner explicitly verifies and removes the abandoned lock.
    """
    lock = CACHE_DIR / ".adoption.lock"
    deadline = _time.monotonic() + 5
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            break
        except FileExistsError:
            if _time.monotonic() >= deadline:
                raise TimeoutError("another data adopter owns the cache lock")
            _time.sleep(0.01)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        lock.unlink()


def refresh(force: bool = False) -> str:
    """Fetch newer holiday data if there is any. Returns what happened.

    Never raises. Every failure path ends at "keep using what we have", because
    a calendar that throws on a DNS hiccup is worse than one that is a week out
    of date. ``force`` skips the daily throttle; it never makes an older or
    unverified dataset acceptable. Use :func:`refresh_succeeded` on the result.
    """
    if _offline():
        return _record("offline: AION_IN_CALENDAR_OFFLINE is set", persist=False)
    if not force and not _due_for_check():
        # Not an attempt, so it does not overwrite the last real outcome.
        return "checked recently"

    raw = _fetch(f"{REMOTE_BASE}/manifest.json")
    if raw is None:
        _warn_once("unreachable", "Holiday data host unreachable; keeping the current verified data.")
        return _record("remote unreachable")
    try:
        remote = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _warn_once("badjson", "Remote holiday manifest is not valid JSON; keeping the current data.")
        return _record("remote manifest unparseable")
    if not isinstance(remote, dict) or remote.get("schema_version") != SCHEMA_VERSION:
        return _record("remote uses a different schema")
    problem = _manifest_problem(remote)
    if problem:
        return _record(f"remote manifest refused: {problem}")
    names = list(remote["files"])

    # Compare against the dataset actually in use, not merely "the cache if any".
    active = _select()
    active_manifest = active[2] if active else {}
    remote_key, active_key = _version_key(remote), _version_key(active_manifest)
    if remote_key < active_key:
        _mark_checked()
        return _record(f"remote is older than the active dataset (remote {remote_key or 'undated'}, "
                       f"active {active_key}); kept the active dataset")
    if remote_key == active_key:
        if remote.get("files") != active_manifest.get("files"):
            return _record("remote changed hashes without a new data version; kept the active dataset")
        _mark_checked()
        return _record("already current")

    # Download into a private staging directory and only adopt once every hash
    # verifies. A half-written cache is indistinguishable from a tampered one, and
    # both should be refused rather than half-trusted.
    staging: Path | None = None
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=CACHE_DIR))
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
        for name in names:
            body = _fetch(f"{REMOTE_BASE}/{name}{suffix}")
            if body is None:
                return _record(f"could not download {name}")
            (staging / name).write_bytes(body)
        (staging / "manifest.json").write_bytes(raw)
        ok, reason = _verify(staging)
        if not ok:
            _warn_once("badhash", "Downloaded holiday data failed verification (%s); "
                                  "keeping existing data.", reason)
            return _record(f"verification failed: {reason}")
        # Monotonic under concurrency: another refresher may have adopted a newer
        # set while this one was downloading. Never switch back to an older one.
        with _adoption_lock():
            current = _select()
            if current is not None and _version_key(current[2]) >= remote_key:
                _mark_checked()
                return _record("already current")
            _adopt(staging, remote, raw)
        staging = None
        _mark_checked()
        log.info("Holiday data updated to %s", remote.get("last_updated"))
        result = _record(f"updated to {remote.get('last_updated')}")
        if _state["loaded"]:
            _reload()                       # this process sees it at once
        return result
    except OSError as exc:
        # Loud, not debug. A cache that cannot be written means auto-update is
        # off, and an update that is silently off is the thing this module was
        # written to prevent.
        _warn_once("nocache",
                   "Could not write refreshed holiday data to %s (%s); continuing "
                   "with the current verified data. Set AION_IN_CALENDAR_CACHE to a "
                   "writable path to enable updates.", CACHE_DIR, exc)
        return _record(f"could not write cache: {exc}")
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def _reload() -> None:
    """Re-read the newest verified dataset; bump ``generation`` if it changed."""
    _state["signature"] = _signature()
    chosen = None
    # Newest first; if a directory vanishes between verification and reading (another
    # process pruned or replaced it), fall through to the next verified one.
    for label, directory, manifest in _verified_candidates():
        try:
            data = _read_dataset(directory)
        except (OSError, KeyError, ValueError) as exc:
            _warn_once(f"read-{label}", "Could not read holiday data from %s: %s", label, exc)
            continue
        chosen = (label, directory, manifest)
        break
    if chosen is None:
        _warn_once("ruleonly",
                   "No verified holiday data; running in RULE-ONLY mode. Weekends "
                   "still apply, but exchange holidays, special sessions and "
                   "half-days are unknown.")
        label, directory, manifest, data = "rule-only", None, {}, {}
    identity = (label, str(directory), _version_key(manifest), manifest.get("dataset_version"),
                json.dumps(manifest.get("files") or {}, sort_keys=True))
    if identity != _state.get("identity"):
        _state["generation"] = int(_state.get("generation") or 0) + 1
        _state["identity"] = identity
    _state.update({"data": data, "source": label, "directory": directory,
                   "manifest": manifest, "loaded": True})


def load(auto_refresh: bool = True) -> dict[int, dict[str, Any]]:
    """The holiday dataset, refreshing at most once a day.

    A process that has already loaded keeps answering from memory, and every
    ``SYNC_INTERVAL_SECONDS`` looks again: it refreshes when the daily check is
    due (backing off after a failure) and re-reads when the verified data on
    disk has changed, including when another process refreshed it.

    Falls back to rule-only mode -- an empty dataset -- if nothing verifies. The
    caller then still has weekends and computed public holidays, which is the
    part that cannot go stale.
    """
    now = _time.monotonic()
    if _state["loaded"]:
        if now - float(_state.get("last_sync") or 0.0) < SYNC_INTERVAL_SECONDS:
            return _state["data"]
        _state["last_sync"] = now
        if (auto_refresh and _due_for_check()
                and now - float(_state.get("last_attempt") or 0.0) >= RETRY_AFTER_FAILURE_SECONDS):
            refresh()
        if _signature() != _state.get("signature"):
            _reload()
        return _state["data"]

    _state["last_sync"] = now
    if auto_refresh:
        refresh()
    _reload()
    return _state["data"]


def generation() -> int:
    """A number that changes whenever the dataset in use changes.

    Calendar objects record it when they are built and rebuild themselves when
    it moves, so a long-lived object never keeps answering from replaced data.
    """
    load()
    return int(_state.get("generation") or 0)


def source() -> str:
    """Where the data in use came from: cache, bundled, or rule-only."""
    load()
    return _state["source"]


def _last_check() -> tuple[str | None, float | None]:
    stamp = CACHE_DIR / ".last_check"
    try:
        return stamp.read_text(encoding="utf-8").strip() or None, _time.time() - stamp.stat().st_mtime
    except OSError:
        return None, None


def _last_refresh() -> dict[str, Any] | None:
    """The most recent refresh outcome, from this process or, failing that, from disk."""
    mine = _state.get("last_refresh")
    try:
        theirs = json.loads((CACHE_DIR / _LAST_REFRESH_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        theirs = None
    if mine and (not theirs or str(mine.get("at")) >= str(theirs.get("at"))):
        return mine
    return theirs


def freshness() -> tuple[str, str]:
    """``("current" | "stale" | "indeterminate", reason)`` for the data in use.

    *current*: verified data, and a conclusive check against the remote within
    ``STALE_AFTER_SECONDS``. *stale*: the last conclusive check is older than
    that. *indeterminate*: no verified data, offline, or never checked, so
    nobody can say. A caller that must not act on outdated sessions should treat
    anything but "current" as a reason to refuse.
    """
    load()
    if _state["source"] == "rule-only":
        return "indeterminate", "no verified holiday data (rule-only mode)"
    if _offline():
        return "indeterminate", "offline mode: the remote is never checked"
    checked_at, age = _last_check()
    if age is None:
        return "indeterminate", "never checked against the remote"
    if age > STALE_AFTER_SECONDS:
        last = _last_refresh()
        why = f"; last refresh: {last['result']}" if last else ""
        return "stale", f"last conclusive check {checked_at} is {age / 3600:.0f} h old{why}"
    return "current", f"checked {checked_at}"


def status() -> dict[str, Any]:
    """Everything a caller needs to decide whether to trust the answer.

    Exposed because a library that quietly degrades is the thing this module was
    written to avoid: if it is in rule-only mode, or its data is stale, the caller
    should be able to find that out without reading the logs.
    """
    load()
    manifest = _state.get("manifest") or {}
    checked_at, age = _last_check()
    state, reason = freshness()
    directory = _state.get("directory")
    return {
        "source": _state["source"],
        "rule_only": _state["source"] == "rule-only",
        "dataset_version": manifest.get("dataset_version"),
        "last_updated": manifest.get("last_updated"),
        "next_review_date": manifest.get("next_review_date"),
        "review_due": bool(manifest.get("next_review_date") and
                           date.today().isoformat() >= manifest["next_review_date"]),
        "coverage": {str(y): p.get("range") for y, p in _state["data"].items()},
        "years": sorted(_state["data"]),
        "offline": _offline(),
        "remote": REMOTE_BASE,
        "directory": str(directory) if directory else None,
        "generation": int(_state.get("generation") or 0),
        "last_check": checked_at,
        "check_age_hours": round(age / 3600, 2) if age is not None else None,
        "last_refresh": _last_refresh(),
        "freshness": state,
        "freshness_reason": reason,
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
