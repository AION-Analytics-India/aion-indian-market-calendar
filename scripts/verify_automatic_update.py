from pathlib import Path
import base64,functools,http.server,json,hashlib,threading,sys,contextlib,io
from datetime import datetime,timedelta,timezone
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from aion_indian_market_calendar.automatic_updates import AutomaticUpdateCheck
from aion_indian_market_calendar.managed_updater import ManagedUpdater

w=Path(sys.argv[1]).resolve();new=Path(sys.argv[2]).resolve();root=Path(sys.argv[3]).resolve()
if root.exists():raise SystemExit('Refuse reused automatic-cycle root')
root.mkdir();wh=root/'served';wh.mkdir()
old=next((w/'artifacts').glob('*.whl'))
deps=[next((w/'repair-wheelhouse').glob(n)) for n in ['pytz-*.whl','tzdata-*.whl']]
for f in [old,new,*deps]:(wh/f.name).write_bytes(f.read_bytes())
def approval(version,wheels):
 return {'schema_version':1,'project':'aion-indian-market-calendar','approved':True,'approval_id':'isolated-cycle-only','version':version,'artifacts':[{'filename':f.name,'size':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in wheels]}
u=ManagedUpdater(root/'managed',allow_environment_changes=True)
initial=json.dumps(approval('1.7.1',[old,*deps])).encode();u.upgrade(initial,hashlib.sha256(initial).hexdigest(),wh)
requests=[]
class Handler(http.server.SimpleHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):requests.append(self.path);return super().do_GET()
handler=functools.partial(Handler,directory=str(wh))
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 base=f'http://127.0.0.1:{server.server_port}'
 key=Ed25519PrivateKey.generate();pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw).hex()
 doc=approval('1.8.0',[new,*deps]);now=datetime.now(timezone.utc)
 doc.update(channel='stable',sequence=1,issued_at=(now-timedelta(minutes=1)).isoformat(),expires_at=(now+timedelta(hours=1)).isoformat())
 for item in doc['artifacts']:item['url']=base+'/'+item['filename']
 payload=json.dumps(doc,sort_keys=True).encode();envelope={'algorithm':'Ed25519','payload':base64.b64encode(payload).decode(),'signature':base64.b64encode(key.sign(payload)).decode()}
 (wh/'approved.json').write_text(json.dumps(envelope))
 worker=AutomaticUpdateCheck(u,{'channel_url':base+'/approved.json','channel':'stable','public_key_hex':pub,'allowed_artifact_hosts':['127.0.0.1']},network_authorized=True,allow_test_http=True)
 import os
 os.environ['AION_IN_CALENDAR_OFFLINE']='0'
 notice=worker.check();assert notice['status']=='update_available' and u.state()['version']=='1.7.1'
 before=len(requests)
 with contextlib.redirect_stdout(io.StringIO()) as captured:worker.watch(install=True,max_checks=1)
 assert u.state()['version']=='1.8.0' and len(requests)-before==4
 after=len(requests);current=worker.check(install=True);assert current['status']=='up_to_date' and len(requests)-after==1
 (wh/'approved.json').write_text(json.dumps({**envelope,'signature':base64.b64encode(b'x'*64).decode()}))
 try:worker.check(install=True)
 except Exception as e:assert type(e).__name__=='InvalidSignature'
 else:raise AssertionError('Untrusted release accepted')
 assert u.state()['version']=='1.8.0'
 result={'notification':notice,'automatic_watch_result':json.loads(captured.getvalue()),'repeat_check':current,'tampered_release':'rejected','requests':requests,'active_version':u.state()['version'],'private_key':'ephemeral memory only','production_changes':False}
 (root/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'automatic_cycle':'PASS','notification':'PASS','upgrade':'1.7.1 -> 1.8.0','repeat_install':'prevented','tampered_release':'rejected'}))
finally:server.shutdown();server.server_close();thread.join()
