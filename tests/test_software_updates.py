"""Explicit discovery and managed upgrade refusal/transaction contracts."""
import hashlib
import json
from pathlib import Path
import pytest
from aion_indian_market_calendar.software_updates import verify_approval, discover, fetch_bytes
from aion_indian_market_calendar.managed_updater import ManagedUpdater


def approval(**changes):
    data={'schema_version':1,'project':'aion-indian-market-calendar','approved':True,
          'approval_id':'disposable-test','version':'1.8.0','artifacts':[
              {'filename':'aion_indian_market_calendar-1.8.0-py3-none-any.whl','sha256':'0'*64,'size':12}]}
    data.update(changes);raw=json.dumps(data).encode()
    return raw,hashlib.sha256(raw).hexdigest()


def test_explicit_approved_version_discovery(monkeypatch):
    raw,digest=approval()
    monkeypatch.setattr('aion_indian_market_calendar.software_updates.fetch_bytes',lambda *a,**k:raw)
    offer=discover('https://example.invalid/approved',approved_manifest_sha256=digest,current_version='1.7.1',network_authorized=True)
    assert offer.newer and offer.available=='1.8.0' and offer.installed=='1.7.1'
    assert verify_approval(raw,digest,current_version='1.8.0').newer is False


@pytest.mark.parametrize('changes',[{'approved':False},{'schema_version':99},{'project':'other'},{'version':'1.8.0rc1'},{'approval_id':''},{'artifacts':[]},{'artifacts':[{'filename':'../x.whl','sha256':'0'*64,'size':1}]}])
def test_invalid_or_unapproved_release_refused(changes):
    raw,digest=approval(**changes)
    with pytest.raises(ValueError):verify_approval(raw,digest,current_version='1.7.1')


def test_approval_requires_independent_hash():
    raw,_=approval()
    with pytest.raises(ValueError,match='hash mismatch'):verify_approval(raw,'f'*64,current_version='1.7.1')


@pytest.mark.parametrize('authorized,offline',[(False,False),(True,True)])
def test_no_unauthorized_discovery_socket(monkeypatch,authorized,offline):
    monkeypatch.setenv('AION_IN_CALENDAR_OFFLINE','1' if offline else '0')
    monkeypatch.setattr('urllib.request.OpenerDirector.open',lambda *a,**k:pytest.fail('network reached'))
    with pytest.raises(PermissionError):fetch_bytes('https://example.invalid',max_bytes=20,network_authorized=authorized)


def test_managed_changes_are_opt_in(tmp_path):
    with pytest.raises(PermissionError):ManagedUpdater(tmp_path)
    assert not list(tmp_path.iterdir())


def test_corrupt_artifact_keeps_active_state(tmp_path):
    u=ManagedUpdater(tmp_path/'managed',allow_environment_changes=True)
    raw,digest=approval();wh=tmp_path/'wheels';wh.mkdir()
    (wh/'aion_indian_market_calendar-1.8.0-py3-none-any.whl').write_bytes(b'not a wheel!')
    with pytest.raises(ValueError,match='integrity'):u.upgrade(raw,digest,wh)
    assert u.state()['active'] is None
    assert [json.loads(x)['status'] for x in (u.root/'upgrades.jsonl').read_text().splitlines()]==['attempted','failed']


def test_interrupted_or_competing_update_is_not_promoted(tmp_path):
    u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    (tmp_path/'UPDATE.lock').write_text('synthetic abandoned owner')
    raw,digest=approval()
    with pytest.raises(FileExistsError):u.upgrade(raw,digest,tmp_path)
    assert u.state()['active'] is None
    assert (tmp_path/'UPDATE.lock').exists()


def test_managed_pointer_cannot_escape_root(tmp_path):
    u=ManagedUpdater(tmp_path,allow_environment_changes=True)
    (tmp_path/'CURRENT.json').write_text(json.dumps({'active':'../../outside'}))
    with pytest.raises(ValueError):u.active_python()


def test_failed_upgrade_after_staging_does_not_promote(tmp_path,monkeypatch):
    u=ManagedUpdater(tmp_path/'managed',allow_environment_changes=True)
    data=b'disposable invalid wheel';name='aion_indian_market_calendar-1.8.0-py3-none-any.whl'
    raw,digest=approval(artifacts=[{'filename':name,'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)}])
    wh=tmp_path/'wh';wh.mkdir();(wh/name).write_bytes(data)
    def failed(*args):raise RuntimeError('synthetic subprocess failure')
    monkeypatch.setattr(u,'_run',failed)
    with pytest.raises(RuntimeError):u.upgrade(raw,digest,wh)
    assert u.state()['active'] is None and not (u.root/'UPDATE.lock').exists()


@pytest.fixture
def http_fixture(monkeypatch):
    import http.server, threading
    responses={}
    requests=[]
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append((self.path,dict(self.headers)))
            code,headers,body=responses[self.path]
            self.send_response(code)
            for k,v in headers.items():self.send_header(k,v)
            self.end_headers();self.wfile.write(body)
        def log_message(self,*a):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.delenv('AION_IN_CALENDAR_OFFLINE',raising=False)
    try:yield f'http://127.0.0.1:{server.server_port}',responses,requests
    finally:server.shutdown();server.server_close();thread.join()


def test_real_http_discovery_is_explicit_bounded_and_header_minimal(http_fixture):
    base,responses,requests=http_fixture
    raw,digest=approval();responses['/approved']=(200,{},raw)
    offer=discover(base+'/approved',approved_manifest_sha256=digest,current_version='1.7.1',network_authorized=True,allow_test_http=True)
    assert offer.available=='1.8.0' and len(requests)==1
    assert not any(k.lower() in {'authorization','cookie'} or k.lower().startswith('x-') for k in requests[0][1])


def test_real_http_size_and_redirect_refusal(http_fixture):
    base,responses,requests=http_fixture
    responses['/large']=(200,{},b'x'*50)
    responses['/redirect']=(302,{'Location':'https://example.invalid/no'},b'')
    with pytest.raises(ValueError,match='size limit'):fetch_bytes(base+'/large',max_bytes=10,network_authorized=True,allow_test_http=True)
    with pytest.raises(ValueError,match='redirects'):fetch_bytes(base+'/redirect',max_bytes=10,network_authorized=True,allow_test_http=True)
    assert len(requests)==2
