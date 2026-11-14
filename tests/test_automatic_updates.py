"""Pinned-authority checks; ephemeral signing keys never leave test memory."""
import base64
from datetime import datetime,timedelta,timezone
import hashlib,json
from pathlib import Path
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from aion_indian_market_calendar.automatic_updates import verify_signed_channel,AutomaticUpdateCheck
from aion_indian_market_calendar.managed_updater import ManagedUpdater,_atomic
from test_software_updates import http_fixture


def signed(key,**changes):
    now=datetime.now(timezone.utc)
    doc={'schema_version':1,'project':'aion-indian-market-calendar','approved':True,'approval_id':'synthetic-only',
         'version':'1.8.0','channel':'stable','sequence':1,'issued_at':(now-timedelta(minutes=1)).isoformat(),
         'expires_at':(now+timedelta(hours=1)).isoformat(),'artifacts':[
             {'filename':'aion_indian_market_calendar-1.8.0-py3-none-any.whl','sha256':'0'*64,'size':12,'url':'https://example.invalid/a.whl'}]}
    doc.update(changes);payload=json.dumps(doc,sort_keys=True).encode()
    raw=json.dumps({'algorithm':'Ed25519','payload':base64.b64encode(payload).decode(),
                    'signature':base64.b64encode(key.sign(payload)).decode()}).encode()
    public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
    return raw,public


def test_signature_verification_uses_pinned_authority():
    key=Ed25519PrivateKey.generate();raw,public=signed(key)
    payload,doc=verify_signed_channel(raw,public_key_hex=public,channel='stable')
    assert doc['version']=='1.8.0' and doc['sequence']==1
    with pytest.raises(InvalidSignature):
        verify_signed_channel(raw,public_key_hex=signed(Ed25519PrivateKey.generate())[1],channel='stable')


@pytest.mark.parametrize('fault',['tamper','expired','future','channel','sequence','unapproved'])
def test_rejected_channels(fault):
    key=Ed25519PrivateKey.generate();changes={};now=datetime.now(timezone.utc)
    if fault=='expired':changes['expires_at']=(now-timedelta(seconds=1)).isoformat()
    if fault=='future':changes['issued_at']=(now+timedelta(minutes=1)).isoformat()
    if fault=='channel':changes['channel']='other'
    if fault=='sequence':changes['sequence']=0
    if fault=='unapproved':changes['approved']=False
    raw,public=signed(key,**changes)
    if fault=='tamper':
        env=json.loads(raw);env['payload']=base64.b64encode(base64.b64decode(env['payload'])+b' ').decode();raw=json.dumps(env).encode()
    with pytest.raises((ValueError,InvalidSignature)):
        verify_signed_channel(raw,public_key_hex=public,channel='stable')


def test_real_http_notify_replay_and_optin(http_fixture,tmp_path,monkeypatch):
    base,responses,requests=http_fixture;key=Ed25519PrivateKey.generate();raw,public=signed(key,sequence=2)
    responses['/release']=(200,{},raw)
    u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    _atomic(tmp_path/'CURRENT.json',{'version':'1.7.1','active':'synthetic-state-only','previous':None})
    policy={'channel_url':base+'/release','public_key_hex':public,'channel':'stable','allowed_artifact_hosts':['127.0.0.1']}
    with pytest.raises(PermissionError):AutomaticUpdateCheck(u,policy)
    worker=AutomaticUpdateCheck(u,policy,network_authorized=True,allow_test_http=True)
    monkeypatch.setattr(u,'upgrade',lambda *a:pytest.fail('notification tried to install'))
    notice=worker.check();assert notice['status']=='update_available' and notice['installed']=='1.7.1'
    assert u.state()['version']=='1.7.1' and not list((tmp_path/'environments').iterdir())
    older,_=signed(key,sequence=1);responses['/release']=(200,{},older)
    with pytest.raises(ValueError,match='rollback'):worker.check()
    changed,_=signed(key,sequence=2,approval_id='changed');responses['/release']=(200,{},changed)
    with pytest.raises(ValueError,match='replacement'):worker.check()
    assert len(requests)==3


def test_watch_reports_failure_without_installation(tmp_path,monkeypatch,capsys):
    raw,public=signed(Ed25519PrivateKey.generate())
    u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    worker=AutomaticUpdateCheck(u,{'channel_url':'https://example.invalid','channel':'stable','public_key_hex':public,'allowed_artifact_hosts':['example.invalid']},network_authorized=True)
    monkeypatch.setattr(worker,'check',lambda **k:(_ for _ in ()).throw(ValueError('private diagnostic')))
    worker.watch(max_checks=1)
    assert 'private diagnostic' not in capsys.readouterr().out
    assert u.state()['active'] is None


def test_offline_worker_never_fetches(tmp_path,monkeypatch):
    _,public=signed(Ed25519PrivateKey.generate());u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    _atomic(tmp_path/'CURRENT.json',{'version':'1.7.1','active':'synthetic-state-only'})
    worker=AutomaticUpdateCheck(u,{'channel_url':'https://example.invalid','channel':'stable','public_key_hex':public,'allowed_artifact_hosts':['example.invalid']},network_authorized=True)
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1')
    with pytest.raises(PermissionError):worker.check(install=True)
    assert u.state()['version']=='1.7.1'


def test_superseded_download_cannot_promote(tmp_path):
    key=Ed25519PrivateKey.generate();raw,public=signed(key,sequence=1)
    payload,doc=verify_signed_channel(raw,public_key_hex=public,channel='stable')
    u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    _atomic(tmp_path/'CHANNEL.json',{'channel':'stable','sequence':2,'sha256':'newer-approved-release'})
    with pytest.raises(ValueError,match='changed while artifacts'):
        u.upgrade(payload,hashlib.sha256(payload).hexdigest(),tmp_path)
    assert u.state()['active'] is None
