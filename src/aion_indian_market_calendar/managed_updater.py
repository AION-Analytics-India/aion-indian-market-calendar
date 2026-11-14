"""Opt-in deployment supervisor. Not imported or invoked by calendar APIs.

Installs only hash-approved local wheels with --no-index and --no-deps, checks
an isolated environment, then atomically changes a pointer. It never restarts a
consumer, edits its current environment or chooses a public release as approved.
The deployment owner must launch future workers using active_python().
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from .software_updates import verify_approval

# Fixed local compatibility checks, never shell text from a remote manifest.
SMOKE = '''
import importlib.metadata as m, json, sys
from datetime import date
from aion_indian_market_calendar import IndiaMarketCalendar, get_market_phase, get_expiry_day
assert m.version("aion-indian-market-calendar") == sys.argv[1]
c = IndiaMarketCalendar.bundled(2026)
assert c.covers(date(2026,11,13)) and not c.covers(date(2027,1,26))
for market in ("CDS","USDINR","EURINR","GBPINR","JPYINR"):
 assert c.is_market_open("2026-11-13T16:30:00+05:30",market=market)
assert not c.is_market_open("2026-04-01T16:30:00+05:30",market="CDS")
assert get_market_phase("2026-11-13T17:00:00+05:30","CDS",calendar=c)=="CLOSED"
assert str(get_expiry_day("NIFTY","2026-10-19",calendar=c))=="2026-10-19"
print(json.dumps({"version":m.version("aion-indian-market-calendar"),"checks":"passed"}))
'''


def _atomic(path: Path, data: dict) -> None:
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class ManagedUpdater:
    def __init__(self, root: Path, *, allow_environment_changes: bool = False, python: str = sys.executable):
        if not allow_environment_changes:
            raise PermissionError("Managed upgrades require explicit deployment-owner opt-in")
        if os.name == 'nt':
            from .windows_runtime import reject_reparse
            reject_reparse(Path(root).absolute())
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.python = str(Path(python).resolve())
        (self.root / "environments").mkdir(exist_ok=True)

    @contextlib.contextmanager
    def _lock(self):
        if os.name == 'nt':
            from .windows_runtime import open_guard
            try:guard = open_guard(self.root / '.UPDATE.guard')
            except BlockingIOError:
                raise FileExistsError('Another managed operation holds the update lock') from None
        else:
            import fcntl
            guard = os.open(self.root / '.UPDATE.guard', os.O_RDWR | os.O_CREAT, 0o600)
        # Never unlink the advisory inode. Children inherit the descriptor, so
        # killing a supervisor cannot admit a second installer over a live pip.
        lock = self.root / "UPDATE.lock"
        token = uuid.uuid4().hex
        try:
            try:
                if os.name != 'nt':fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise FileExistsError('Another managed operation holds the update lock') from None
            if lock.exists():
                try:
                    prior = json.loads(lock.read_text())
                except (ValueError, OSError):
                    raise FileExistsError('Legacy update lock requires owner review') from None
                if not isinstance(prior, dict) or prior.get('lock_protocol') != 2:
                    raise FileExistsError('Legacy update lock requires owner review')
                self._receipt({'status': 'interrupted_operation_recovered'})
            _atomic(lock, {'lock_protocol': 2, 'token': token})
            self._lock_fd = guard
            try:
                yield
            finally:
                self._lock_fd = None
                if lock.exists() and json.loads(lock.read_text()).get('token') == token:
                    lock.unlink()
        finally:
            os.close(guard)

    def state(self) -> dict:
        p = self.root / "CURRENT.json"
        return json.loads(p.read_text()) if p.exists() else {"active": None, "previous": None, "version": "0.0.0"}

    def _environment(self, name: str) -> Path:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Invalid managed environment")
        path = self.root / "environments" / name
        if os.name == 'nt':
            from .windows_runtime import reject_reparse
            reject_reparse(path)
        if path.resolve().parent != (self.root / "environments").resolve() or path.is_symlink():
            raise ValueError("Environment escaped managed root")
        return path

    def active_python(self) -> Path | None:
        active = self.state()["active"]
        return self._bin(self._environment(active)) if active else None

    @staticmethod
    def _bin(env: Path) -> Path:
        return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def _receipt(self, event: dict) -> None:
        # No user identifier, absolute path, environment dump or subprocess stderr.
        with (self.root / "upgrades.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": time.time(), **event}, sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _env(self, candidate: Path) -> dict:
        # Do not inherit credentials, proxies, PYTHONPATH, live cache or pip config.
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "WINDIR", "TMPDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "SYSTEMDRIVE", "COMSPEC", "PATHEXT") if k in os.environ}
        env.update(AION_IN_CALENDAR_OFFLINE="1", AION_IN_CALENDAR_CACHE=str(candidate / "calendar-cache"),
                   PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONNOUSERSITE="1")
        if os.name == 'nt':
            temporary = candidate / 'tmp';temporary.mkdir(exist_ok=True)
            env.update(TEMP=str(temporary), TMP=str(temporary))
        return env

    def _run(self, args: list[str], candidate: Path) -> None:
        fd = getattr(self, '_lock_fd', None)
        if os.name == 'nt':
            from .windows_runtime import run_child
            run_child(args, cwd=candidate, env=self._env(candidate), check=True,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                      lease_fds=(fd,) if fd is not None else ())
            return
        subprocess.run(args, cwd=candidate, env=self._env(candidate), check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
                       pass_fds=(fd,) if fd is not None else ())

    def _smoke(self, candidate: Path, version: str) -> None:
        self._run([str(self._bin(candidate)), "-I", "-c", SMOKE, version], candidate)
        self._run([str(self._bin(candidate)), "-I", "-m", "pip", "check"], candidate)

    def upgrade(self, raw_manifest: bytes, approved_sha256: str, wheelhouse: Path) -> dict:
        """Transactionally stage -> test -> promote; old environment remains immutable.

        An interrupted staging directory is never active. Protocol-2 locks are
        recovered after the inherited advisory lock becomes available. Unknown
        legacy locks still require explicit owner review.
        """
        with self._lock():
            before = self.state()
            offer = verify_approval(raw_manifest, approved_sha256, current_version=before["version"])
            if offer.manifest.get("channel"):
                channel = json.loads((self.root / "CHANNEL.json").read_text())
                if (channel.get("channel") != offer.manifest["channel"] or
                    channel.get("sequence") != offer.manifest.get("sequence") or
                    channel.get("sha256") != offer.manifest_sha256):
                    raise ValueError("Signed channel changed while artifacts were downloading")
            if not offer.newer:
                raise ValueError("Upgrade is not newer; use explicit rollback for an accepted previous environment")
            attempt = uuid.uuid4().hex
            self._receipt({"attempt": attempt, "status": "attempted", "installed": before["version"],
                           "target": offer.available, "approval": offer.manifest_sha256})
            candidate = self._environment(f"{offer.available}-{attempt}")
            candidate.mkdir()
            try:
                # Validate and copy before running any artifact code. Never install mutable wheelhouse paths.
                wheels = candidate / "approved-wheels"
                wheels.mkdir()
                for item in offer.manifest["artifacts"]:
                    source = Path(wheelhouse) / item["filename"]
                    if source.is_symlink() or source.resolve().parent != Path(wheelhouse).resolve():
                        raise ValueError("Artifact escaped wheelhouse")
                    with source.open("rb") as f:
                        data = f.read(item["size"] + 1)
                    if len(data) != item["size"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                        raise ValueError("Artifact integrity check failed")
                    (wheels / item["filename"]).write_bytes(data)
                self._run([self.python, "-I", "-m", "venv", str(candidate)], candidate)
                self._run([str(self._bin(candidate)), "-I", "-m", "pip", "install", "--no-index", "--no-deps",
                           *[str(wheels / a["filename"]) for a in offer.manifest["artifacts"]]], candidate)
                self._smoke(candidate, offer.available)
                accepted = {"version": offer.available, "approval": offer.manifest_sha256, "accepted": True}
                _atomic(candidate / "ACCEPTED.json", accepted)
                state = {"active": candidate.name, "previous": before["active"], "version": offer.available,
                         "previous_version": before["version"], "attempt": attempt}
                _atomic(self.root / "CURRENT.json", state)
                self._receipt({"attempt": attempt, "status": "success", "installed": offer.available})
                return state
            except BaseException as exc:
                # No pointer change occurs before acceptance; leave bounded diagnostics, never promote failures.
                self._receipt({"attempt": attempt, "status": "failed", "installed": self.state()["version"],
                               "target": offer.available, "error_type": type(exc).__name__})
                raise

    def rollback(self) -> dict:
        with self._lock():
            before = self.state()
            if not before.get("previous"):
                raise ValueError("No previously accepted environment to roll back to")
            previous = self._environment(before["previous"])
            accepted = json.loads((previous / "ACCEPTED.json").read_text())
            if accepted.get("accepted") is not True or accepted["version"] != before["previous_version"]:
                raise ValueError("Rollback acceptance record mismatch")
            self._smoke(previous, accepted["version"])
            restored = {"active": previous.name, "previous": before["active"], "version": accepted["version"],
                        "previous_version": before["version"]}
            _atomic(self.root / "CURRENT.json", restored)
            self._receipt({"status": "rollback", "installed": restored["version"], "from": before["version"]})
            return restored


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=['status','upgrade','rollback'])
    ap.add_argument('--root', required=True, type=Path)
    ap.add_argument('--allow-environment-changes', action='store_true')
    ap.add_argument('--manifest', type=Path)
    ap.add_argument('--approved-sha256')
    ap.add_argument('--wheelhouse', type=Path)
    args = ap.parse_args()
    if args.operation == 'status':
        p=args.root/'CURRENT.json'
        print(p.read_text() if p.exists() else json.dumps({'version':None,'active':None}))
        return 0
    updater = ManagedUpdater(args.root, allow_environment_changes=args.allow_environment_changes)
    if args.operation == 'rollback':
        state=updater.rollback()
    else:
        if not args.manifest or not args.approved_sha256 or not args.wheelhouse:
            ap.error('upgrade requires --manifest, --approved-sha256 and --wheelhouse')
        state=updater.upgrade(args.manifest.read_bytes(),args.approved_sha256,args.wheelhouse)
    print(json.dumps(state,sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
