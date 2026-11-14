"""Pinned root -> expiring, versioned release keyring -> signed releases.

No default production identity or endpoint is invented. Owners provision the
public root separately. Release-key rotation/revocation is root-signed; root
replacement remains an explicit owner action, never an online key substitution.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

from .automatic_updates import verify_signed_channel
from .software_updates import MAX_MANIFEST_BYTES, release_tuple


def envelope_payload(raw: bytes, public_hex: str) -> tuple[bytes, dict]:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError('Signed metadata is too large')
    env = json.loads(raw)
    if env.get('algorithm') != 'Ed25519':
        raise ValueError('Unsupported signature')
    payload = base64.b64decode(env['payload'], validate=True)
    signature = base64.b64decode(env['signature'], validate=True)
    if len(payload) > MAX_MANIFEST_BYTES or len(signature) != 64:
        raise ValueError('Invalid signature envelope size')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(signature, payload)
    return payload, json.loads(payload)


def valid_period(doc: dict, now: datetime | None = None) -> None:
    start = datetime.fromisoformat(doc['issued_at'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(doc['expires_at'].replace('Z', '+00:00'))
    when = now or datetime.now(timezone.utc)
    if start.utcoffset() is None or end.utcoffset() is None or not start <= when < end:
        raise ValueError('Metadata is expired or not yet valid')


def check_monotonic(old: dict, *, number: int, digest: str) -> None:
    if type(number) is not int or number < 1:
        raise ValueError('Invalid metadata version')
    if number < old.get('number', 0) or (number == old.get('number') and digest != old.get('sha256')):
        raise ValueError('Metadata rollback or replacement refused')


def verify_trust(raw: bytes, policy: dict, old: dict) -> tuple[dict, dict]:
    payload, doc = envelope_payload(raw, policy['root_public_key_hex'])
    valid_period(doc)
    if (doc.get('schema_version') != 1 or doc.get('project') != 'aion-indian-market-calendar'
            or doc.get('channel') != policy['channel']):
        raise ValueError('Wrong trust metadata scope')
    keys = doc.get('release_keys')
    if not isinstance(keys, dict) or not 1 <= len(keys) <= 8:
        raise ValueError('Missing bounded release keyring')
    for ident, value in keys.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Invalid release identity')
    for field in ('revoked_key_ids', 'revoked_versions'):
        values = doc.get(field)
        if not isinstance(values, list) or len(values) > 1024 or any(not isinstance(x, str) for x in values):
            raise ValueError('Invalid revocation set')
    digest = hashlib.sha256(payload).hexdigest()
    check_monotonic(old, number=doc['trust_version'], digest=digest)
    # A root-signed newer keyring cannot silently undo an existing revocation.
    previous = old.get('document', {})
    for field in ('revoked_key_ids', 'revoked_versions'):
        if not set(previous.get(field, ())).issubset(doc[field]):
            raise ValueError('Revocation removal refused')
    return doc, {'number': doc['trust_version'], 'sha256': digest, 'document': doc}


def verify_release(raw: bytes, trust: dict, policy: dict, current: str) -> tuple[bytes, dict]:
    from packaging.specifiers import SpecifierSet
    import platform
    env = json.loads(raw)
    key_id = env.get('key_id')
    if key_id in trust['revoked_key_ids'] or key_id not in trust['release_keys']:
        raise ValueError('Release signing identity is unknown or revoked')
    payload, doc = verify_signed_channel(raw, public_key_hex=trust['release_keys'][key_id], channel=policy['channel'])
    target = release_tuple(doc['version'])
    if list(target[:2]) != policy['compatible_series'] or doc.get('compatibility_series') != '.'.join(map(str, target[:2])):
        raise ValueError('Release is outside the owner-approved patch series')
    if doc['version'] in trust['revoked_versions']:
        raise ValueError('Release version is revoked')
    if not isinstance(doc.get('requires_python'), str) or not doc['requires_python']:
        raise ValueError('Release has no Python compatibility declaration')
    if platform.python_version() not in SpecifierSet(doc['requires_python']):
        raise ValueError('Release is incompatible with this Python interpreter')
    if target < release_tuple(current):
        raise ValueError('Automatic downgrade refused')
    return payload, doc


def validate_policy(doc: dict) -> dict:
    if doc.get('schema_version') != 2 or doc.get('channel') != 'stable':
        raise ValueError('Unsupported managed policy')
    if not re.fullmatch(r'[0-9a-f]{64}', str(doc.get('root_public_key_hex', ''))):
        raise ValueError('An independently trusted root public key is required')
    series = doc.get('compatible_series')
    if not isinstance(series, list) or len(series) != 2 or any(type(n) is not int or n < 0 for n in series):
        raise ValueError('A fixed compatible major/minor series is required')
    if type(doc.get('poll_seconds')) is not int or not 60 <= doc['poll_seconds'] <= 86400:
        raise ValueError('Polling interval must be 60..86400 seconds')
    hosts = doc.get('allowed_artifact_hosts')
    if not isinstance(hosts, list) or not hosts or len(hosts) > 8 or any(not isinstance(h, str) or not h for h in hosts):
        raise ValueError('An artifact host allowlist is required')
    for key in ('channel_url', 'trust_url'):
        u = urlsplit(doc.get(key, ''))
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.fragment:
            raise ValueError('Credential-free HTTPS policy endpoints are required')
    if doc.get('deployment') not in ('customer-managed', 'aion-protected'):
        raise ValueError('Explicit deployment ownership is required')
    return dict(doc)
