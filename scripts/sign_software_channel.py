"""Offline root/keyring or release signing. No key discovery or publication.

The approved signing controller supplies exactly 32 raw private-key bytes on
an inherited descriptor >=3. No private key belongs in argv, logs or this repo.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import sys


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('kind',choices=['trust','release'])
    ap.add_argument('--document',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--key-id',required=True)
    ap.add_argument('--private-key-fd',type=int,required=True)
    ap.add_argument('--approve-signing',action='store_true')
    a=ap.parse_args()
    if not a.approve_signing or a.private_key_fd<3:
        raise PermissionError('Explicit signing approval and a dedicated key descriptor are required')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from aion_indian_market_calendar.update_trust import verify_trust,verify_release
    raw=a.document.read_bytes()
    if len(raw)>128*1024:raise ValueError('Metadata exceeds its bound')
    doc=json.loads(raw);payload=json.dumps(doc,sort_keys=True,separators=(',',':')).encode()
    with os.fdopen(os.dup(a.private_key_fd),'rb') as fd:keybytes=fd.read(33)
    if len(keybytes)!=32:raise ValueError('Signing key must contain exactly 32 raw bytes')
    key=Ed25519PrivateKey.from_private_bytes(keybytes)
    public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    envelope={'algorithm':'Ed25519','key_id':a.key_id,'payload':base64.b64encode(payload).decode(),
              'signature':base64.b64encode(key.sign(payload)).decode()}
    encoded=json.dumps(envelope,sort_keys=True).encode()
    if a.kind=='trust':
        verify_trust(encoded,{'root_public_key_hex':public,'channel':'stable'},{})
    else:
        parts=doc['version'].split('.')
        verify_release(encoded,{'release_keys':{a.key_id:public},'revoked_key_ids':[],'revoked_versions':[]},
                       {'channel':'stable','compatible_series':[int(n) for n in parts[:2]]},'0.0.0')
    # Signing is separate from publication. Never silently replace a receipt.
    fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
    with os.fdopen(fd,'wb') as f:f.write(encoded+b'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'kind':a.kind,'signed':True,'sha256':hashlib.sha256(encoded+b'\n').hexdigest()}))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'signed':False,'error_type':type(exc).__name__}),file=sys.stderr)
        raise SystemExit(1)
