"""Opt-in scheduled approved-release checks. Never imported by calendar APIs.

A device owner pins a release public key once. Each later approved release is
signed by that authority, so clients do not need a new manual checksum per patch.
No production signing key, channel or background service is configured here.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit
from .software_updates import MAX_MANIFEST_BYTES, fetch_bytes, verify_approval
from .managed_updater import ManagedUpdater, _atomic


def verify_signed_channel(raw: bytes, *, public_key_hex: str, channel: str,
                          now: datetime | None = None) -> tuple[bytes, dict]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Signed channel exceeds size limit')
    envelope=json.loads(raw)
    if envelope.get('algorithm')!='Ed25519':
        raise ValueError('Unsupported signing algorithm')
    payload=base64.b64decode(envelope['payload'],validate=True)
    signature=base64.b64decode(envelope['signature'],validate=True)
    if len(payload)>MAX_MANIFEST_BYTES or len(signature)!=64:
        raise ValueError('Invalid signed envelope size')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(signature,payload)
    doc=json.loads(payload)
    if doc.get('channel')!=channel or type(doc.get('sequence')) is not int or doc['sequence']<1:
        raise ValueError('Wrong release channel or invalid sequence')
    start=datetime.fromisoformat(doc['issued_at'].replace('Z','+00:00'))
    end=datetime.fromisoformat(doc['expires_at'].replace('Z','+00:00'))
    when=now or datetime.now(timezone.utc)
    if start.utcoffset() is None or end.utcoffset() is None or not start<=when<end:
        raise ValueError('Signed release is expired or not yet valid')
    # Signature establishes the independently pinned approval authority.
    verify_approval(payload,hashlib.sha256(payload).hexdigest(),current_version='0.0.0')
    return payload,doc


class AutomaticUpdateCheck:
    """One supervised check, or a foreground polling loop, after explicit opt-in."""
    def __init__(self, updater: ManagedUpdater, policy: dict, *, network_authorized: bool=False,
                 allow_test_http: bool=False):
        if not network_authorized:
            raise PermissionError('Software checking must be explicitly enabled by device owner')
        self.updater=updater
        self.policy=dict(policy)
        self.test_http=allow_test_http
        if not self.policy.get('channel') or not self.policy.get('allowed_artifact_hosts'):
            raise ValueError('A pinned channel and artifact allowlist are required')
        interval=self.policy.get('poll_seconds',86400)
        if type(interval) is not int or not 60<=interval<=86400:
            raise ValueError('Polling interval must be 60..86400 seconds')
        bytes.fromhex(self.policy['public_key_hex'])
        if len(bytes.fromhex(self.policy['public_key_hex']))!=32:
            raise ValueError('Pinned Ed25519 public key must contain 32 bytes')

    def check(self, *, install: bool=False) -> dict:
        if not self.updater.state().get('active'):
            raise ValueError('Adopt an existing managed environment before enabling scheduled checks')
        raw=fetch_bytes(self.policy['channel_url'],max_bytes=MAX_MANIFEST_BYTES,
                        network_authorized=True,allow_test_http=self.test_http)
        payload,doc=verify_signed_channel(raw,public_key_hex=self.policy['public_key_hex'],channel=self.policy['channel'])
        digest=hashlib.sha256(payload).hexdigest()
        # Reuse the updater's cross-process lock around channel acceptance. The
        # subsequent upgrade rechecks the installed version under its own lock.
        with self.updater._lock():
            statefile=self.updater.root/'CHANNEL.json'
            old=json.loads(statefile.read_text()) if statefile.exists() else {}
            if old and old.get('channel')!=doc['channel']:
                raise ValueError('Channel changes require explicit supervisor migration')
            if doc['sequence']<old.get('sequence',0) or (doc['sequence']==old.get('sequence') and digest!=old.get('sha256')):
                raise ValueError('Release-channel rollback or same-sequence replacement refused')
            _atomic(statefile,{'sequence':doc['sequence'],'sha256':digest,'channel':doc['channel']})
        current=self.updater.state()['version']
        offer=verify_approval(payload,digest,current_version=current)
        notice={'status':'update_available' if offer.newer else 'up_to_date','installed':current,
                'available':offer.available,'sequence':doc['sequence']}
        self.updater._receipt({**notice,'status':'version_check','result':notice['status']})
        if not offer.newer or not install:
            return notice
        # Download only signed, explicitly allowlisted artifacts. No redirects
        # or remote shell commands. Exact size/hash checked before installation.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='approved-download-',dir=self.updater.root) as name:
            directory=Path(name)
            for artifact in doc['artifacts']:
                url=artifact.get('url','')
                if urlsplit(url).hostname not in self.policy['allowed_artifact_hosts']:
                    raise ValueError('Artifact destination is not allowlisted')
                data=fetch_bytes(url,max_bytes=artifact['size'],network_authorized=True,allow_test_http=self.test_http)
                if len(data)!=artifact['size'] or hashlib.sha256(data).hexdigest()!=artifact['sha256']:
                    raise ValueError('Downloaded artifact integrity failure')
                (directory/artifact['filename']).write_bytes(data)
            result=self.updater.upgrade(payload,digest,directory)
        return {**notice,'status':'upgraded','installed':result['version']}

    def watch(self, *, install: bool=False, max_checks: int | None=None) -> None:
        checks=0
        while max_checks is None or checks<max_checks:
            try:
                print(json.dumps(self.check(install=install),sort_keys=True),flush=True)
            except Exception as exc:
                # Preserve previous environment. Never print payloads, secrets,
                # transport exception strings or an operator's private paths.
                self.updater._receipt({'status':'check_failed','error_type':type(exc).__name__,
                                       'installed':self.updater.state()['version']})
                print(json.dumps({'status':'check_failed','error_type':type(exc).__name__}),flush=True)
            checks+=1
            if max_checks is None or checks<max_checks:
                time.sleep(self.policy.get('poll_seconds',86400))


def main() -> int:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['check','watch'])
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--enable-software-checks',action='store_true')
    parser.add_argument('--install-approved',action='store_true')
    args=parser.parse_args()
    if not args.enable_software_checks:
        parser.error('Device-owner opt-in --enable-software-checks is required')
    # The deployment root is explicitly opted in; install remains a separate
    # flag. Default check/watch modes only notify via stdout/local receipts.
    u=ManagedUpdater(args.root,allow_environment_changes=True)
    worker=AutomaticUpdateCheck(u,json.loads(args.policy.read_text()),network_authorized=True)
    if args.operation=='check':print(json.dumps(worker.check(install=args.install_approved),sort_keys=True))
    else:worker.watch(install=args.install_approved)
    return 0


if __name__=='__main__':raise SystemExit(main())
