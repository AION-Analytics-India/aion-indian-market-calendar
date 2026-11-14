"""Explicit per-user managed-runtime onboarding and persistent update lifecycle.

The original pip environment is read only. Only applications launched through
``run`` use the managed runtime. No operation is invoked by normal calendar use.
The Windows adapter is staged and requires native acceptance before release.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

from .managed_updater import ManagedUpdater, _atomic
from .software_updates import fetch_bytes, MAX_MANIFEST_BYTES, verify_approval
from .update_trust import validate_policy, verify_trust, verify_release, check_monotonic

PROJECT = 'aion-indian-market-calendar'
RUNTIME_DEPS = {'pytz', 'tzdata'}


def canonical(name):
    return name.lower().replace('_', '-').replace('.', '-')


def private_file(path: Path) -> None:
    if os.name == 'nt':
        from .windows_runtime import private_path
        private_path(path)
        return
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o022:
        raise PermissionError('Managed input must be owned and not writable by other users')


def config(root: Path) -> dict:
    private_file(root)
    p = root / 'SUPERVISOR.json'
    private_file(p)
    doc = json.loads(p.read_text())
    if doc.get('root') != str(root) or doc.get('schema_version') != 1:
        raise ValueError('Managed ownership record mismatch')
    return doc


def write_config(root: Path, doc: dict) -> None:
    _atomic(root / 'SUPERVISOR.json', doc)


def controller_python(root: Path) -> Path:
    if os.name == 'nt':
        p = root / 'CONTROLLER.json';private_file(p)
        doc = json.loads(p.read_text())
        name = doc.get('environment')
        if not isinstance(name, str) or Path(name).name != name:
            raise PermissionError('Invalid immutable Windows controller record')
        target = root / 'bootstrap' / 'environments' / name / 'Scripts' / 'python.exe'
        private_file(target)
        return target
    return root / 'controller' / 'bin' / 'python'


def runtime(root: Path) -> ManagedUpdater:
    return ManagedUpdater(root / 'runtime', allow_environment_changes=True, python=str(controller_python(root)))


@contextlib.contextmanager
def workload(root: Path, *, exclusive: bool):
    if os.name == 'nt':
        from .windows_runtime import open_guard
        fd = open_guard(root / 'WORKLOAD.guard', shared=not exclusive)
        try:yield fd
        finally:os.close(fd)
        return
    import fcntl
    fd = os.open(root / 'WORKLOAD.guard', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BlockingIOError('Managed runtime is in use or being updated') from None
        yield fd
    finally:
        os.close(fd)


def validate_wheels(directory: Path, artifacts: list[dict], cfg: dict) -> None:
    """Inspect wheel metadata without executing it; freeze dependency policy."""
    from email.parser import BytesParser
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    pins = cfg['dependency_pins']
    supplied = {}
    for item in artifacts:
        p = directory / item['filename']
        if p.is_symlink() or p.resolve().parent != directory.resolve():
            raise ValueError('Wheel path escaped quarantine')
        raw = p.read_bytes()
        if len(raw) != item['size'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Wheel integrity mismatch')
        with zipfile.ZipFile(p) as z:
            names = [n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
            if len(names) != 1 or z.getinfo(names[0]).file_size > 128 * 1024:
                raise ValueError('Wheel must have one metadata record')
            m = BytesParser().parsebytes(z.read(names[0]))
        name = canonical(m['Name'])
        if name in supplied or name not in RUNTIME_DEPS | {PROJECT}:
            raise ValueError('Unexpected or duplicate runtime dependency')
        if m.get('Requires-Python') and platform.python_version() not in SpecifierSet(m['Requires-Python']):
            raise ValueError('Wheel Python compatibility refused')
        supplied[name] = m['Version']
        if name in pins and m['Version'] != pins[name]:
            raise ValueError('Dependency lock refused a changed version')
        for text in m.get_all('Requires-Dist', []):
            req = Requirement(text)
            if req.marker and not req.marker.evaluate({'extra': ''}):
                continue
            dep = canonical(req.name)
            if dep not in pins or req.url or pins[dep] not in req.specifier:
                raise ValueError('Release dependency is outside the approved runtime lock')
    if set(supplied) != RUNTIME_DEPS | {PROJECT}:
        raise ValueError('Release must contain the exact approved runtime closure')
    from packaging.requirements import Requirement
    for text in cfg['constraints']:
        req = Requirement(text)
        if supplied[canonical(req.name)] not in req.specifier:
            raise ValueError('Customer constraint refused this release')


def admission(cfg: dict) -> None:
    if cfg['policy']['deployment'] == 'aion-protected':
        p = Path(cfg['admission']['path'])
        private_file(p)
        if hashlib.sha256(p.read_bytes()).hexdigest() != cfg['admission']['sha256']:
            raise PermissionError('Approved deployment controller changed')
        env = ({'SYSTEMROOT': os.environ['SYSTEMROOT'], 'PATH': str(Path(os.environ['SYSTEMROOT'])/'System32')}
               if os.name == 'nt' else {'PATH':'/usr/bin:/bin'})
        result = subprocess.run([str(p), '--check', cfg['root']], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=10)
        if result.returncode:
            raise PermissionError('Protected deployment controller did not grant admission')


def check(root: Path, *, scheduled: bool = False) -> dict:
    cfg = config(root)
    u = runtime(root)
    if cfg.get('uninstalled') or not cfg['enabled']:
        return {'status': 'disabled'}
    if cfg['offline'] or os.environ.get('AION_IN_CALENDAR_OFFLINE', '').lower() in ('1', 'true', 'yes'):
        return {'status': 'offline', 'installed': u.state()['version']}
    policy = validate_policy(cfg['policy'])
    if policy.get('tls_ca_file'):
        ca = Path(policy['tls_ca_file']);private_file(ca)
        os.environ['SSL_CERT_FILE'] = str(ca)
    raw = fetch_bytes(policy['trust_url'], max_bytes=MAX_MANIFEST_BYTES, network_authorized=True)
    with u._lock():
        old = json.loads((root / 'TRUST.json').read_text()) if (root / 'TRUST.json').exists() else {}
        trust, state = verify_trust(raw, policy, old)
        _atomic(root / 'TRUST.json', state)
    raw = fetch_bytes(policy['channel_url'], max_bytes=MAX_MANIFEST_BYTES, network_authorized=True)
    payload, doc = verify_release(raw, trust, policy, u.state()['version'])
    digest = hashlib.sha256(payload).hexdigest()
    with u._lock():
        old = json.loads((u.root / 'CHANNEL.json').read_text()) if (u.root / 'CHANNEL.json').exists() else {}
        check_monotonic({'number': old.get('sequence', 0), 'sha256': old.get('sha256')}, number=doc['sequence'], digest=digest)
        _atomic(u.root / 'CHANNEL.json', {'channel': policy['channel'], 'sequence': doc['sequence'], 'sha256': digest})
    if doc['version'] == u.state()['version']:
        return {'status': 'up_to_date', 'installed': u.state()['version']}
    if not cfg['automatic_installation']:
        return {'status': 'update_available', 'installed': u.state()['version'], 'available': doc['version']}
    admission(cfg)
    try:
        with workload(root, exclusive=True):
            with tempfile.TemporaryDirectory(dir=root, prefix='download-') as name:
                directory = Path(name)
                from urllib.parse import urlsplit
                for item in doc['artifacts']:
                    if urlsplit(item.get('url', '')).hostname not in policy['allowed_artifact_hosts']:
                        raise ValueError('Artifact host is not approved')
                    raw = fetch_bytes(item['url'], max_bytes=item['size'], network_authorized=True)
                    (directory / item['filename']).write_bytes(raw)
                validate_wheels(directory, doc['artifacts'], cfg)
                # Trust and channel cannot change between this validation and
                # promotion: one OS job/check is serialized by OPERATION.guard.
                state = u.upgrade(payload, digest, directory)
        return {'status': 'upgraded', 'installed': state['version']}
    except BlockingIOError:
        return {'status': 'deferred_active_workload', 'installed': u.state()['version']}


@contextlib.contextmanager
def operation(root: Path):
    if os.name == 'nt':
        from .windows_runtime import open_guard
        fd = open_guard(root / 'OPERATION.guard')
        try:yield fd
        finally:os.close(fd)
        return
    import fcntl
    fd = os.open(root / 'OPERATION.guard', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        os.close(fd)


def setup(args) -> dict:
    from .update_supervision import Service
    from packaging.requirements import Requirement
    if not args.consent:
        raise PermissionError('Explicit --consent is required; no environment was modified')
    if platform.system() not in ('Darwin', 'Linux', 'Windows') or not (3, 10) <= sys.version_info[:2] <= (3, 14):
        raise NotImplementedError('Managed installation requires a supported platform and Python 3.10-3.14')
    if platform.system() == 'Windows':
        from .windows_runtime import interactive_identity
        interactive_identity()
    import importlib.util
    if importlib.util.find_spec('ensurepip') is None:
        raise RuntimeError('Managed setup requires this Python installation to provide venv/ensurepip')
    private_file(args.policy)
    policy = validate_policy(json.loads(args.policy.read_text()))
    installed = metadata.version(PROJECT)
    print(json.dumps({'original_version': installed, 'original_environment': sys.prefix,
                      'managed_root': str(args.root), 'original_environment_will_be_changed': False,
                      'automatic_installation_requested': args.enable_auto_install}), flush=True)
    if args.root.exists():
        raise FileExistsError('Setup requires a new, dedicated managed root')
    pins = {name: metadata.version(name) for name in sorted(RUNTIME_DEPS)}
    constraints = []
    if args.constraints:
        for line in args.constraints.read_text().splitlines():
            line = line.split('#', 1)[0].strip()
            if not line:continue
            req = Requirement(line)
            if req.url or req.marker or req.extras or canonical(req.name) not in RUNTIME_DEPS | {PROJECT}:
                raise ValueError('Constraints must target only this owned calendar runtime')
            if not req.specifier:
                raise ValueError('An explicit version constraint is required')
            constraints.append(line)
    admission_doc = None
    if policy['deployment'] == 'aion-protected':
        if not args.admission or not args.admission_sha256:
            raise PermissionError('Protected workloads require their approved deployment controller')
        admission_doc = {'path': str(args.admission.resolve()), 'sha256': args.admission_sha256}
    raw = args.bootstrap_manifest.read_bytes()
    offer = verify_approval(raw, args.approved_sha256, current_version='0.0.0')
    if offer.available != installed:
        raise ValueError('Bootstrap approval must match the installed candidate')
    if policy.get('tls_ca_file'):
        ca = Path(policy['tls_ca_file']);private_file(ca);os.environ['SSL_CERT_FILE'] = str(ca)
    if os.environ.get('AION_IN_CALENDAR_OFFLINE', '').lower() in ('1', 'true', 'yes'):
        raise PermissionError('Offline setup cannot verify a release channel or enable supervision')
    trust_raw = fetch_bytes(policy['trust_url'], max_bytes=MAX_MANIFEST_BYTES, network_authorized=True)
    trust, trust_state = verify_trust(trust_raw, policy, {})
    release_raw = fetch_bytes(policy['channel_url'], max_bytes=MAX_MANIFEST_BYTES, network_authorized=True)
    verify_release(release_raw, trust, policy, installed)
    cfg = {'schema_version': 1, 'root': str(args.root), 'policy': policy, 'dependency_pins': pins,
           'constraints': constraints, 'enabled': False, 'automatic_installation': args.enable_auto_install,
           'offline': False, 'original_version': installed, 'original_environment': sys.prefix,
           'admission': admission_doc, 'created_at': time.time(), 'uninstalled': False}
    if os.name == 'nt':
        from .windows_runtime import create_private_directory
        create_private_directory(args.root)
    else:args.root.mkdir(mode=0o700)
    (args.root / 'tmp').mkdir(mode=0o700)
    write_config(args.root, cfg)
    _atomic(args.root / 'TRUST.json', trust_state)
    bootstrap = ManagedUpdater(args.root / 'bootstrap', allow_environment_changes=True)
    # Explicit, independently hash-approved local closure includes signature and
    # policy dependencies for the fixed controller. Never resolves from PyPI.
    state = bootstrap.upgrade(raw, args.approved_sha256, args.wheelhouse)
    source = bootstrap._environment(state['active'])
    # A stable symlink to an immutable accepted controller, not a copied venv.
    if os.name == 'nt':_atomic(args.root / 'CONTROLLER.json', {'environment':source.name})
    else:(args.root / 'controller').symlink_to(source, target_is_directory=True)
    runtime_items = [a for a in offer.manifest['artifacts'] if a['filename'].startswith(('aion_indian_market_calendar-', 'pytz-', 'tzdata-'))]
    validate_wheels(args.wheelhouse.resolve(), runtime_items, cfg)
    initial = {**offer.manifest, 'artifacts': runtime_items}
    initial.pop('channel', None);initial.pop('sequence', None)
    initial_raw = json.dumps(initial, sort_keys=True).encode()
    runtime(args.root).upgrade(initial_raw, hashlib.sha256(initial_raw).hexdigest(), args.wheelhouse)
    service = Service(args.root, cfg, directory=args.service_directory)
    service.install()
    cfg.update(service=service.record(), enabled=True)
    write_config(args.root, cfg)
    try:
        service.start()
    except BaseException:
        cfg['enabled'] = False;write_config(args.root, cfg)
        service.disable()
        raise
    return status(args.root)


def status(root: Path) -> dict:
    from .update_supervision import Service
    cfg = config(root)
    actual = Service(root, cfg).status() if cfg.get('service') else {'registered': False, 'scheduled': False}
    return {'managed_version': runtime(root).state()['version'], 'original_version_at_setup': cfg['original_version'],
            'enabled': cfg['enabled'], 'automatic_installation_enabled': bool(cfg['enabled'] and cfg['automatic_installation'] and not cfg['offline'] and actual['scheduled']),
            'offline': cfg['offline'], 'uninstalled': cfg['uninstalled'], 'supervision': actual}


def main() -> int:
    from .update_supervision import Service
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('operation', choices=['setup', 'start', 'stop', 'status', 'disable', 'uninstall', 'check', 'worker', 'run', 'rollback', 'offline'])
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--policy', type=Path)
    ap.add_argument('--consent', action='store_true')
    ap.add_argument('--enable-auto-install', action='store_true')
    ap.add_argument('--bootstrap-manifest', type=Path)
    ap.add_argument('--approved-sha256')
    ap.add_argument('--wheelhouse', type=Path)
    ap.add_argument('--constraints', type=Path)
    ap.add_argument('--admission', type=Path)
    ap.add_argument('--admission-sha256')
    ap.add_argument('--service-directory', type=Path)
    args, command = ap.parse_known_args()
    if command and args.operation != 'run':ap.error('Unexpected arguments')
    if args.root.is_symlink():raise PermissionError('Managed root cannot be a symlink')
    args.root = args.root.absolute()
    if os.name == 'nt':
        from .windows_runtime import reject_reparse, attach_worker_job
        reject_reparse(args.root)
        if args.operation in ('worker','check','run','rollback') or (args.operation == 'setup' and args.consent):
            attach_worker_job()
    if args.operation == 'setup':
        if not all((args.policy, args.bootstrap_manifest, args.approved_sha256, args.wheelhouse)):
            ap.error('setup requires policy and independently hash-approved local bootstrap wheels')
        result = setup(args)
    elif args.operation == 'status':result = status(args.root)
    elif args.operation == 'run':
        if command[:1] == ['--']:command = command[1:]
        if not command:ap.error('run requires Python arguments after --')
        cfg = config(args.root)
        if cfg['uninstalled']:raise PermissionError('Supervisor is uninstalled; retained data is recovery-only')
        with workload(args.root, exclusive=False) as fd:
            u = runtime(args.root)
            trust = json.loads((args.root / 'TRUST.json').read_text())['document']
            if u.state()['version'] in trust['revoked_versions']:raise PermissionError('Managed version is revoked')
            if os.name == 'nt':
                from .windows_runtime import run_child
                return run_child([str(u.active_python()), *command], env=u._env(u.active_python().parent.parent), lease_fds=(fd,)).returncode
            return subprocess.run([str(u.active_python()), *command], env=u._env(u.active_python().parent.parent), pass_fds=(fd,)).returncode
    elif args.operation in ('check', 'worker'):
        try:
            with operation(args.root):result = check(args.root, scheduled=args.operation == 'worker')
        except Exception as exc:
            result = {'status': 'check_failed', 'error_type': type(exc).__name__}
            runtime(args.root)._receipt(result)
            print(json.dumps(result), flush=True)
            return 1
        runtime(args.root)._receipt({**result, 'kind': 'supervisor_check'})
    else:
        cfg = config(args.root)
        service = Service(args.root, cfg)
        if args.operation == 'rollback':
            service.stop()
            admission(cfg)
            with operation(args.root), workload(args.root, exclusive=True):
                u = runtime(args.root);trust = json.loads((args.root / 'TRUST.json').read_text())['document']
                from .update_trust import valid_period
                valid_period(trust)
                if u.state().get('previous_version') in trust['revoked_versions']:raise PermissionError('Rollback target is revoked')
                result = u.rollback()
        else:
            if args.operation == 'start':
                if not args.consent:raise PermissionError('Explicit --consent is required to re-enable')
                if cfg['uninstalled']:raise PermissionError('Uninstalled supervision requires fresh setup')
                cfg['enabled'] = True;write_config(args.root, cfg);service.start()
            elif args.operation == 'stop':service.stop()
            elif args.operation == 'disable':
                cfg['enabled'] = False;write_config(args.root, cfg);service.disable()
            elif args.operation == 'offline':
                cfg['offline'] = True;write_config(args.root, cfg);service.stop()
            elif args.operation == 'uninstall':
                cfg['enabled'] = False;cfg['uninstalled'] = True;write_config(args.root, cfg);service.uninstall()
            result = status(args.root)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
