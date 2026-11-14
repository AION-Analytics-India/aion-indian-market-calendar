"""CLI signatures verified by the actual client; keys only cross an owned pipe."""
import json,os,subprocess,sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PrivateFormat,NoEncryption
from test_update_lifecycle import public,policy,trust,release
from aion_indian_market_calendar.update_trust import verify_trust,verify_release


def sign_cli(tmp_path,kind,key,doc,approved=True):
    path=tmp_path/(kind+'.json');path.write_text(json.dumps(doc));out=tmp_path/(kind+'.signed.json')
    rd,wr=os.pipe();os.write(wr,key.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()));os.close(wr)
    script=Path(__file__).parents[1]/'scripts/sign_software_channel.py'
    args=[sys.executable,str(script),kind,'--document',str(path),'--output',str(out),'--key-id','test-release','--private-key-fd',str(rd)]
    if approved:args+=['--approve-signing']
    try:p=subprocess.run(args,pass_fds=(rd,),capture_output=True,text=True,timeout=10)
    finally:os.close(rd)
    return p,out


def test_offline_signer_produces_verified_trust_and_release(tmp_path):
    root,key=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate()
    p,out=sign_cli(tmp_path,'trust',root,trust(key,release_keys={'test-release':public(key)}));assert p.returncode==0
    doc,_=verify_trust(out.read_bytes(),policy(root),{})
    p,out=sign_cli(tmp_path,'release',key,release());assert p.returncode==0
    verify_release(out.read_bytes(),doc,policy(root),'1.8.0')
    assert set(json.loads(p.stdout))=={'kind','signed','sha256'}


def test_signer_without_approval_writes_nothing(tmp_path):
    key=Ed25519PrivateKey.generate();p,out=sign_cli(tmp_path,'release',key,release(),approved=False)
    assert p.returncode!=0 and not out.exists()
