"""Independent lifecycle boundaries; no real service is registered by unit tests."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import zipfile

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from aion_indian_market_calendar.managed_updater import ManagedUpdater
from aion_indian_market_calendar.update_lifecycle import validate_wheels, workload, setup, admission
from aion_indian_market_calendar.update_trust import validate_policy, verify_trust, verify_release
from aion_indian_market_calendar.update_supervision import Service, quote


def public(key):return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
def sign(key, doc, kid='release-a'):
    raw = json.dumps(doc, sort_keys=True).encode()
    return json.dumps({'algorithm': 'Ed25519', 'key_id': kid,
                       'payload': base64.b64encode(raw).decode(),
                       'signature': base64.b64encode(key.sign(raw)).decode()}).encode()
def period():
    now = datetime.now(timezone.utc)
    return {'issued_at': (now-timedelta(minutes=1)).isoformat(), 'expires_at': (now+timedelta(hours=1)).isoformat()}
def policy(root):
    return {'schema_version': 2, 'channel': 'stable', 'root_public_key_hex': public(root),
            'compatible_series': [1, 8], 'poll_seconds': 60, 'deployment': 'customer-managed',
            'trust_url': 'https://example.invalid/trust', 'channel_url': 'https://example.invalid/release',
            'allowed_artifact_hosts': ['example.invalid']}
def trust(key, **changes):
    return {'schema_version': 1, 'project': 'aion-indian-market-calendar', 'channel': 'stable',
            'trust_version': 1, **period(), 'release_keys': {'release-a': public(key)},
            'revoked_key_ids': [], 'revoked_versions': [], **changes}
def release(**changes):
    return {'schema_version': 1, 'project': 'aion-indian-market-calendar', 'approved': True,
            'approval_id': 'synthetic-boundary', 'channel': 'stable', 'sequence': 1,
            'version': '1.8.1', 'compatibility_series': '1.8', 'requires_python': '>=3.10,<3.15',
            **period(), 'artifacts': [{'filename': 'aion_indian_market_calendar-1.8.1-py3-none-any.whl',
                                     'size': 10, 'sha256': '0'*64}], **changes}


def test_release_key_rotation_and_revocation():
    root, a, b = [Ed25519PrivateKey.generate() for _ in range(3)]
    p = policy(root);doc, state = verify_trust(sign(root, trust(a)), p, {})
    verify_release(sign(a, release()), doc, p, '1.8.0')
    changed = trust(a, trust_version=2, release_keys={'release-b': public(b)}, revoked_key_ids=['release-a'])
    doc, state = verify_trust(sign(root, changed), p, state)
    verify_release(sign(b, release(), 'release-b'), doc, p, '1.8.0')
    with pytest.raises(ValueError, match='revoked'):verify_release(sign(a, release()), doc, p, '1.8.0')
    with pytest.raises(ValueError, match='Revocation removal'):
        verify_trust(sign(root, {**changed, 'trust_version': 3, 'revoked_key_ids': []}), p, state)


@pytest.mark.parametrize('fault', ['wrong-root', 'expired', 'rollback', 'replacement', 'wrong-channel', 'invalid-keyring'])
def test_untrusted_metadata_cannot_replace_state(fault):
    root, signer = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate();p = policy(root)
    doc = trust(signer);_, state = verify_trust(sign(root, doc), p, {})
    key = root
    if fault == 'wrong-root':key = Ed25519PrivateKey.generate()
    elif fault == 'expired':doc['expires_at'] = (datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
    elif fault == 'rollback':doc['trust_version'] = 0
    elif fault == 'replacement':doc['release_keys']['another'] = public(signer)
    elif fault == 'wrong-channel':doc['channel'] = 'other'
    elif fault == 'invalid-keyring':doc['release_keys'] = {}
    with pytest.raises(Exception):verify_trust(sign(key, doc), p, state)


@pytest.mark.parametrize('fault', ['minor-change', 'python', 'downgrade', 'revoked', 'unknown-key', 'unsigned'])
def test_incompatible_release_refused_before_install(fault):
    root, key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate();p = policy(root);doc = trust(key);r = release();kid = 'release-a'
    if fault == 'minor-change':r.update(version='1.9.0', compatibility_series='1.9', artifacts=[{'filename':'aion_indian_market_calendar-1.9.0-py3-none-any.whl','size':10,'sha256':'0'*64}])
    elif fault == 'python':r['requires_python'] = '>=9.0'
    elif fault == 'downgrade':r.update(version='1.8.0', artifacts=[{'filename':'aion_indian_market_calendar-1.8.0-py3-none-any.whl','size':10,'sha256':'0'*64}])
    elif fault == 'revoked':doc['revoked_versions'] = ['1.8.1']
    elif fault == 'unknown-key':kid = 'not-approved'
    raw = sign(key, r, kid)
    if fault == 'unsigned':raw = json.dumps(r).encode()
    with pytest.raises(Exception):verify_release(raw, doc, p, '1.8.1' if fault == 'downgrade' else '1.8.0')


def wheels(tmp_path, *, pytz='2026.1', extra=False):
    items = []
    for name, version, dependencies in [('aion-indian-market-calendar', '1.8.1', ['pytz', 'tzdata']), ('pytz', pytz, []), ('tzdata', '2025.3', [])] + ([('unrelated', '1.0', [])] if extra else []):
        normalized = name.replace('-', '_');p = tmp_path / f'{normalized}-{version}-py3-none-any.whl'
        body = 'Metadata-Version: 2.1\nName: '+name+'\nVersion: '+version+'\n' + ''.join('Requires-Dist: '+d+'\n' for d in dependencies)
        with zipfile.ZipFile(p, 'w') as z:z.writestr(f'{normalized}-{version}.dist-info/METADATA', body)
        raw = p.read_bytes();items.append({'filename':p.name, 'size':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()})
    return items


@pytest.mark.parametrize('fault', ['pin-change', 'customer-pin', 'unrelated', 'tamper'])
def test_dependency_constraints_are_enforced(tmp_path, fault):
    cfg = {'dependency_pins': {'pytz':'2026.1', 'tzdata':'2025.3'}, 'constraints': []}
    items = wheels(tmp_path, pytz='2027.1' if fault == 'pin-change' else '2026.1', extra=fault == 'unrelated')
    if fault == 'customer-pin':cfg['constraints'] = ['aion-indian-market-calendar==1.8.0']
    if fault == 'tamper':(tmp_path/items[0]['filename']).write_bytes(b'changed')
    with pytest.raises(ValueError):validate_wheels(tmp_path, items, cfg)


def test_valid_runtime_closure(tmp_path):
    validate_wheels(tmp_path, wheels(tmp_path), {'dependency_pins':{'pytz':'2026.1','tzdata':'2025.3'}, 'constraints':['aion-indian-market-calendar<1.9']})


def test_workload_lease_defers_update(tmp_path):
    with workload(tmp_path, exclusive=False):
        with pytest.raises(BlockingIOError):
            with workload(tmp_path, exclusive=True):pass
    with workload(tmp_path, exclusive=True):pass


def test_no_setup_without_consent(tmp_path):
    from types import SimpleNamespace
    with pytest.raises(PermissionError):setup(SimpleNamespace(consent=False, root=tmp_path/'unused'))
    assert not (tmp_path/'unused').exists()


def test_missing_ensurepip_refused_before_root_creation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('importlib.util.find_spec', lambda name:None)
    with pytest.raises(RuntimeError, match='ensurepip'):setup(SimpleNamespace(consent=True, root=tmp_path/'unused'))
    assert not (tmp_path/'unused').exists()


@pytest.mark.parametrize('fault', ['denied', 'changed-controller'])
def test_protected_controller_enforcement(tmp_path, fault):
    p=tmp_path/'admit';p.write_text('#!/bin/sh\nexit 1\n');p.chmod(0o700)
    cfg={'root':str(tmp_path),'policy':{'deployment':'aion-protected'},'admission':{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}}
    if fault=='changed-controller':p.write_text('#!/bin/sh\nexit 0\n')
    with pytest.raises(PermissionError):admission(cfg)


def test_uninstall_tombstone_does_not_hide_provider_state(tmp_path, monkeypatch):
    monkeypatch.setattr('aion_indian_market_calendar.update_supervision.platform.system', lambda:'Darwin')
    from types import SimpleNamespace
    s=Service(tmp_path, {'uninstalled':True})
    monkeypatch.setattr(s, 'command', lambda *a,**k:SimpleNamespace(returncode=0, stdout='\n\tpid = 123\n' if a[1]=='print' else ''))
    assert s.status()['scheduled'] and s.status()['running']


def test_repeated_linux_disable_requires_stopped_readback(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('aion_indian_market_calendar.update_supervision.platform.system', lambda:'Linux')
    s=Service(tmp_path, {})
    monkeypatch.setattr(s,'command',lambda *a,**k:SimpleNamespace(returncode=0 if 'show' in a else 1,stdout='ActiveState=inactive\nUnitFileState=not-found\n'))
    s.disable()
    monkeypatch.setattr(s,'command',lambda *a,**k:SimpleNamespace(returncode=1,stdout='ActiveState=active\nUnitFileState=enabled\n'))
    with pytest.raises(RuntimeError):s.disable()


def test_windows_adapter_cannot_be_executed_by_posix_emulation(tmp_path, monkeypatch):
    monkeypatch.setattr('aion_indian_market_calendar.update_supervision.platform.system', lambda:'Windows')
    with pytest.raises(NotImplementedError):Service(tmp_path, {})


def test_service_arguments_are_not_shell_commands():
    assert quote('/tmp/a path/100%') == '"/tmp/a path/100%%"'
    with pytest.raises(ValueError):quote('bad\nExecStart=/bin/false')


def test_inherited_lock_survives_supervisor_kill_and_then_recovers(tmp_path):
    root = tmp_path/'managed';marker = tmp_path/'child.json'
    code = '''
import sys,os,json,time
from pathlib import Path
from aion_indian_market_calendar.managed_updater import ManagedUpdater
u=ManagedUpdater(Path(sys.argv[1]),allow_environment_changes=True)
with u._lock():
 u._run([sys.executable,'-c',"import os,time;from pathlib import Path;Path("+repr(sys.argv[2])+").write_text(str(os.getpid()));time.sleep(45)"],u.root)
'''
    process = subprocess.Popen([sys.executable, '-c', code, str(root), str(marker)], start_new_session=True)
    try:
        end = time.monotonic()+10
        while not marker.exists() and time.monotonic()<end:time.sleep(.02)
        assert marker.exists()
        os.kill(process.pid, signal.SIGKILL);process.wait(timeout=5)
        u = ManagedUpdater(root, allow_environment_changes=True)
        with pytest.raises(FileExistsError):
            with u._lock():pass
        os.killpg(process.pid, signal.SIGKILL)
        end = time.monotonic()+5
        while time.monotonic()<end:
            try:
                with u._lock():pass
                break
            except FileExistsError:time.sleep(.02)
        else:pytest.fail('Advisory lock did not release after process-tree termination')
        assert not (root/'UPDATE.lock').exists()
        assert any(json.loads(s)['status']=='interrupted_operation_recovered' for s in (root/'upgrades.jsonl').read_text().splitlines())
    finally:
        try:os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=5)
