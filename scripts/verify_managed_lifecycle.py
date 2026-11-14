"""Real launchd/systemd/Task Scheduler lifecycle, synthetic TLS channel, disposable installs.

Usage: python verify_managed_lifecycle.py WORKSPACE QUARANTINE
WORKSPACE contains artifacts/1.7.1, lifecycle-dist/1.8.0 and repair-wheelhouse/.
Never registers a job other than its hash-derived disposable label. Private
keys remain in RAM. This is not proof of a live production trust channel.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import base64,csv,hashlib,http.server,io,ipaddress,json,os,platform,signal,ssl,subprocess,sys,threading,time,zipfile
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,ed25519
from cryptography.x509.oid import NameOID

W=Path(sys.argv[1]).resolve();R=Path(sys.argv[2]).absolute()
if R.exists():raise SystemExit('Refuse reused quarantine')
if os.name=='nt':
 from aion_indian_market_calendar.windows_runtime import create_private_directory
 create_private_directory(R)
else:R.mkdir(mode=0o700)
(R/'tmp').mkdir();(R/'home').mkdir();S=R/'served';S.mkdir()
NEW=W/'lifecycle-dist/aion_indian_market_calendar-1.8.0-py3-none-any.whl';OLD=W/'artifacts/aion_indian_market_calendar-1.7.1-py3-none-any.whl'
RESULT={'started_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'python':sys.version,'cases':[],'commands':[],'requests':[],'production_changes':False}
def save(): (R/'RESULTS.json').write_text(json.dumps(RESULT,indent=2)+'\n')
def record(name,**evidence):
 RESULT['cases'].append({'case':name,'result':'PASS',**evidence});save();print(name+': PASS',flush=True)
def env(online=False):
 e={k:os.environ[k] for k in ['PATH','SYSTEMROOT','WINDIR','USERPROFILE','LOCALAPPDATA','APPDATA','SYSTEMDRIVE','COMSPEC','PATHEXT','DBUS_SESSION_BUS_ADDRESS','XDG_RUNTIME_DIR'] if k in os.environ}
 e.update(PYTHONUTF8='1',TEMP=str(R/'tmp'),TMP=str(R/'tmp'),TMPDIR=str(R/'tmp'),AION_IN_CALENDAR_OFFLINE='0' if online else '1',AION_IN_CALENDAR_CACHE=str(R/'cache'),PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PIP_NO_CACHE_DIR='1',PYTHONDONTWRITEBYTECODE='1')
 if (R/'test-ca.pem').exists():e['SSL_CERT_FILE']=str(R/'test-ca.pem')
 return e
def run(args,tag,expected=0,online=False,timeout=240):
 p=subprocess.run(list(map(str,args)),cwd=R,env=env(online),capture_output=True,text=True,timeout=timeout)
 (R/(tag+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');RESULT['commands'].append({'case':tag,'argv':list(map(str,args)),'exit':p.returncode});save()
 if expected is not None:assert p.returncode==expected,(tag,p.returncode,(p.stdout+p.stderr)[-1800:])
 return p
if os.name=='nt':
 from aion_indian_market_calendar.windows_runtime import interactive_identity
 RESULT['windows_identity_class']=interactive_identity();RESULT['windows_identity_class'].pop('sid',None);save()
U=R/'original';run([sys._base_executable,'-m','venv',U],'original-venv');PY=U/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def pip(*args,tag):return run([PY,'-m','pip','install','--no-index','--find-links',W/'repair-wheelhouse','--find-links',W/'lifecycle-dist',*args],tag)
pip(OLD,tag='published-171-install')
assert run([PY,'-I','-c','import importlib.metadata as m; print(m.version("aion-indian-market-calendar"))'],'published-version').stdout.strip()=='1.7.1'
pip('--upgrade','aion-indian-market-calendar[updates]==1.8.0',tag='one-time-bootstrap')
assert hashlib.sha256(OLD.read_bytes()).hexdigest()=='02ff1daa1a715a6cfd67401f65e9c70f88406128d86208921f8318fc81fd6bd7'
record('published_171_manual_bootstrap_to_actual_candidate',original_version='1.8.0',wheel_sha256=hashlib.sha256(NEW.read_bytes()).hexdigest())
key=ec.generate_private_key(ec.SECP256R1());subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'isolated-calendar-lifecycle')]);now=datetime.now(timezone.utc)
cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=2)).not_valid_after(now+timedelta(hours=2)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),False).add_extension(x509.BasicConstraints(ca=True,path_length=None),True).sign(key,hashes.SHA256())
pem=cert.public_bytes(serialization.Encoding.PEM);(R/'test-ca.pem').write_bytes(pem)
if os.name=='nt':
 from windows_fixture_tls import FixtureServer
 server=FixtureServer(S,key,cert,RESULT['requests']);thread=None;URL='https://127.0.0.1:'+str(server.port)
else:
 fds=[]
 for data in [pem,key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())]:
  rd,wr=os.pipe();os.write(wr,data);os.close(wr);fds.append(rd)
 context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain('/dev/fd/'+str(fds[0]),'/dev/fd/'+str(fds[1]))
 for fd in fds:os.close(fd)
 class Handler(http.server.SimpleHTTPRequestHandler):
  def __init__(self,*args,**kw):super().__init__(*args,directory=str(S),**kw)
  def log_message(self,*args):pass
  def do_GET(self):
   RESULT['requests'].append({'at':time.time(),'path':self.path,'headers':dict(self.headers)});return super().do_GET()
 server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);server.socket=context.wrap_socket(server.socket,server_side=True);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();URL='https://127.0.0.1:'+str(server.server_port)
ROOTKEY=ed25519.Ed25519PrivateKey.generate();RELEASEKEY=ed25519.Ed25519PrivateKey.generate()
def public(k):return k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()
def signed(k,d,kid):
 raw=json.dumps(d,sort_keys=True).encode();return json.dumps({'algorithm':'Ed25519','key_id':kid,'payload':base64.b64encode(raw).decode(),'signature':base64.b64encode(k.sign(raw)).decode()})
def write(name,text):
 p=S/(name+'.tmp');p.write_text(text);os.replace(p,S/name)
def period():
 now=datetime.now(timezone.utc);return {'issued_at':(now-timedelta(minutes=1)).isoformat(),'expires_at':(now+timedelta(hours=1)).isoformat()}
def trust(version=1,signer=RELEASEKEY,kid='release-a',revoked=()):
 doc={'schema_version':1,'project':'aion-indian-market-calendar','channel':'stable','trust_version':version,**period(),'release_keys':{kid:public(signer)},'revoked_key_ids':list(revoked),'revoked_versions':[]};write('trust.json',signed(ROOTKEY,doc,'root'))
def item(p,url=False):
 d={'filename':p.name,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 if url:d['url']=URL+'/'+p.name
 return d
DEPS=[next((W/'repair-wheelhouse').glob(n)) for n in ['pytz-*.whl','tzdata-*.whl']]
from packaging.tags import sys_tags
from packaging.utils import parse_wheel_filename
tags=set(sys_tags())
def compatible(pattern):
 return next(p for p in (W/'repair-wheelhouse').glob(pattern) if tags & parse_wheel_filename(p.name)[3])
CONTROLLER=[compatible(n) for n in ['cryptography-*.whl','cffi-*.whl','pycparser-*.whl','packaging-*.whl']]
if sys.version_info[:2] < (3,11):CONTROLLER.append(compatible('typing_extensions-*.whl'))
for p in [NEW,*DEPS,*CONTROLLER]:(S/p.name).write_bytes(p.read_bytes())
def publish(version,wheel,seq,*,signer=RELEASEKEY,kid='release-a',tamper=False):
 doc={'schema_version':1,'project':'aion-indian-market-calendar','approved':True,'approval_id':'disposable-os-lifecycle','version':version,'channel':'stable','sequence':seq,**period(),'compatibility_series':'.'.join(version.split('.')[:2]),'requires_python':'>=3.10,<3.15','artifacts':[item(p,True) for p in [wheel,*DEPS]]}
 raw=signed(signer,doc,kid)
 if tamper:
  parsed=json.loads(raw);parsed['signature']=base64.b64encode(b'x'*64).decode();raw=json.dumps(parsed)
 write('channel.json',raw)
def synth(version,broken=False):
 files={};old='aion_indian_market_calendar-1.8.0.dist-info';new=f'aion_indian_market_calendar-{version}.dist-info'
 with zipfile.ZipFile(NEW) as z:
  for n in z.namelist():
   if n.endswith('/RECORD'):continue
   data=z.read(n)
   if n==old+'/METADATA':data=data.replace(b'Version: 1.8.0\n',('Version: '+version+'\n').encode())
   if n=='aion_indian_market_calendar/__init__.py':
    data=data.replace(b'__version__ = "1.8.0"',('__version__ = "'+version+'"').encode())
    if broken:data+=b'\nIndiaMarketCalendar.is_market_open = lambda *args, **kwargs: False\n'
   files[n.replace(old,new)]=data
 table=io.StringIO();wr=csv.writer(table,lineterminator='\n')
 for n,b in files.items():wr.writerow([n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('='),len(b)])
 wr.writerow([new+'/RECORD','','']);files[new+'/RECORD']=table.getvalue().encode();p=S/f'aion_indian_market_calendar-{version}-py3-none-any.whl'
 with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in files.items():z.writestr(n,b)
 return p
POLICY=R/'policy.json';POLICY.write_text(json.dumps({'schema_version':2,'channel':'stable','root_public_key_hex':public(ROOTKEY),'compatible_series':[1,8],'poll_seconds':60,'deployment':'customer-managed','channel_url':URL+'/channel.json','trust_url':URL+'/trust.json','tls_ca_file':str(R/'test-ca.pem'),'allowed_artifact_hosts':['127.0.0.1']}))
BOOT={'schema_version':1,'project':'aion-indian-market-calendar','approved':True,'approval_id':'explicit-local-bootstrap','version':'1.8.0','artifacts':[item(p) for p in [NEW,*DEPS,*CONTROLLER]]};raw=json.dumps(BOOT).encode();APPROVAL=R/'bootstrap.json';APPROVAL.write_bytes(raw);HASH=hashlib.sha256(raw).hexdigest();MANAGED=R/'managed'
def cli(operation,tag,*extra,root=MANAGED,expected=0):return run([PY,'-m','aion_indian_market_calendar.update_lifecycle',operation,'--root',root,*extra],tag,expected=expected,online=True)
def state():return json.loads((MANAGED/'runtime/CURRENT.json').read_text())
def receipts():
 p=MANAGED/'runtime/upgrades.jsonl';return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def completed(version):
 return state()['version']==version and any(x.get('kind')=='supervisor_check' and x.get('status')=='upgraded' and x.get('installed')==version for x in receipts())
def until(fn,seconds=330):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  if fn():return
  time.sleep(.02)
 raise AssertionError('Timed out waiting for actual OS supervisor evidence')
def setup(root,install):
 return cli('setup','setup-'+root.name,'--consent',*(['--enable-auto-install'] if install else []),'--policy',POLICY,'--bootstrap-manifest',APPROVAL,'--approved-sha256',HASH,'--wheelhouse',S,'--service-directory',R/('services-'+root.name),root=root)
created=[]
try:
 trust();publish('1.8.0',NEW,1)
 no=cli('setup','no-consent','--policy',POLICY,'--bootstrap-manifest',APPROVAL,'--approved-sha256',HASH,'--wheelhouse',S,root=R/'not-consented',expected=None)
 assert no.returncode!=0 and not (R/'not-consented').exists();record('no_supervisor_without_explicit_consent')
 created.append(MANAGED);setup(MANAGED,True)
 before_setup=(MANAGED/'SUPERVISOR.json').read_bytes()
 setup(MANAGED,True)
 assert (MANAGED/'SUPERVISOR.json').read_bytes()==before_setup
 record('matching_setup_is_idempotent_without_reenrollment')
 status=json.loads(cli('status','status-after-setup').stdout);assert status['automatic_installation_enabled'];RESULT['initial_status']=status
 until(lambda:any(x.get('kind')=='supervisor_check' for x in receipts()))
 record('actual_os_supervisor_registered_after_setup_terminal_exit',supervision=status['supervision'])
 cli('stop','simulated-manager-stop');assert not json.loads(cli('status','status-stopped').stdout)['supervision']['scheduled']
 count=len(receipts());cli('start','simulated-manager-restart','--consent');until(lambda:len(receipts())>count)
 record('simulated_user_manager_restart_resumes_from_persistent_registration')
 patch=synth('1.8.1');publish('1.8.1',patch,2);published=time.time()
 until(lambda:completed('1.8.1'))
 actual=cli('run','managed-application-version','--','-I','-c','import importlib.metadata as m; print(m.version("aion-indian-market-calendar"))').stdout.strip()
 original=run([PY,'-I','-c','import importlib.metadata as m; print(m.version("aion-indian-market-calendar"))'],'original-still-180').stdout.strip()
 assert actual=='1.8.1' and original=='1.8.0'
 cli('run','managed-application-smoke','--','-I','-c','from aion_indian_market_calendar import IndiaMarketCalendar;assert IndiaMarketCalendar.bundled(2026).is_market_open("2026-11-13T16:30:00+05:30",market="CDS");print("PASS")')
 record('unattended_os_scheduled_signed_patch_runs_in_managed_application',managed_version=actual,original_version=original,elapsed_seconds=time.time()-published,manual_check_after_publication=False)
 cli('stop','pause-schedule-for-negative-tests')
 before=state();publish('1.8.2',synth('1.8.2'),3,tamper=True)
 bad=cli('check','invalid-signature',expected=1);assert state()==before;record('invalid_signature_rejected_no_promotion',output=bad.stdout.strip())
 publish('1.9.0',synth('1.9.0'),4)
 bad=cli('check','incompatible-series',expected=1);assert state()==before;record('incompatible_minor_release_rejected',output=bad.stdout.strip())
 publish('1.8.2',synth('1.8.2'),5)
 cli('start','start-for-interruption','--consent')
 until(lambda:any(x.get('status')=='attempted' and x.get('target')=='1.8.2' for x in receipts()))
 cfg=json.loads((MANAGED/'SUPERVISOR.json').read_text());label=cfg['service']['label']
 if platform.system()=='Linux':run(['systemctl','--user','kill','--signal=SIGKILL','--kill-whom=all',label+'.service'],'kill-only-owned-service',online=True)
 elif platform.system()=='Windows':cli('stop','terminate-owned-windows-task');cli('start','resume-owned-windows-task','--consent')
 else:run(['launchctl','kill','SIGKILL','gui/'+str(os.getuid())+'/'+label],'kill-only-owned-service',online=True)
 assert state()==before
 until(lambda:completed('1.8.2'))
 assert any(x.get('status')=='interrupted_operation_recovered' for x in receipts())
 record('os_next_tick_recovers_killed_install_without_manual_lock_removal',installed=state()['version'])
 cli('stop','pause-after-recovery');before=state();publish('1.8.3',synth('1.8.3',broken=True),6)
 cli('check','failed-real-calendar-health',expected=1);assert state()==before;record('failed_calendar_health_preserves_active_runtime')
 cli('rollback','actual-rollback');assert state()['version']=='1.8.1';record('verified_rollback_to_previous_accepted_runtime')
 nextkey=ed25519.Ed25519PrivateKey.generate();trust(2,nextkey,'release-b',['release-a'])
 publish('1.8.2',synth('1.8.2'),7,signer=nextkey,kid='release-b');cli('check','rotated-key-install');assert state()['version']=='1.8.2'
 publish('1.8.3',synth('1.8.3'),8);before=state();cli('check','revoked-key-refused',expected=1);assert state()==before
 record('root_signed_release_key_rotation_and_revocation_enforced')
 cli('disable','disable-supervisor');disabled=json.loads(cli('status','disabled-status').stdout);assert not disabled['automatic_installation_enabled'] and not disabled['supervision']['scheduled']
 request_count=len(RESULT['requests']);r=cli('check','disabled-check');assert json.loads(r.stdout)['status']=='disabled' and len(RESULT['requests'])==request_count
 record('disable_stops_schedule_and_prevents_network_and_install')
 cli('uninstall','uninstall-supervisor');cfg=json.loads((MANAGED/'SUPERVISOR.json').read_text())
 assert not list(Path(cfg['service']['directory']).glob(cfg['service']['label']+'*'))
 record('uninstall_removes_owned_supervisor_files_preserves_runtime_receipts')
 # Real second onboarding with notifications only; no installation flag.
 trust(3,nextkey,'release-b',['release-a']);publish('1.8.2',synth('1.8.2'),9,signer=nextkey,kid='release-b')
 notify=R/'notify-managed';created.append(notify);setup(notify,False)
 p=notify/'runtime/upgrades.jsonl';until(lambda:p.exists() and any(json.loads(s).get('status')=='update_available' for s in p.read_text().splitlines()))
 assert json.loads((notify/'runtime/CURRENT.json').read_text())['version']=='1.8.0';record('notification_only_onboarding_does_not_install_available_release')
 cli('offline','offline-stop',root=notify);requests=len(RESULT['requests']);out=cli('check','offline-check',root=notify);assert json.loads(out.stdout)['status']=='offline' and len(RESULT['requests'])==requests;record('offline_no_network_no_install')
 cli('uninstall','notify-uninstall',root=notify)
 if os.name=='nt':
  partial=R/'partial setup';created.append(partial);marker=R/'partial-registered'
  code='''
import sys,time
from pathlib import Path
from aion_indian_market_calendar.windows_supervision import WindowsService
from aion_indian_market_calendar.update_lifecycle import main
original=WindowsService.call
marker_path=sys.argv[1]
def hold(self,operation,**extra):
 result=original(self,operation,**extra)
 if operation=='install':
  Path(marker_path).write_text('registered')
  time.sleep(60)
 return result
WindowsService.call=hold
del sys.argv[1]
raise SystemExit(main())
'''
  args=[PY,'-c',code,marker,'setup','--root',partial,'--consent','--policy',POLICY,
        '--bootstrap-manifest',APPROVAL,'--approved-sha256',HASH,'--wheelhouse',S,
        '--service-directory',R/'partial task files']
  with (R/'partial-setup.log').open('w',encoding='utf-8') as output:
   process=subprocess.Popen(list(map(str,args)),env=env(True),stdout=output,stderr=subprocess.STDOUT)
   try:
    until(lambda:marker.exists() or process.poll() is not None)
    assert marker.exists(),'Partial setup failed before native task registration'
    intent=json.loads((partial/'SUPERVISOR.json').read_text())
    assert intent['service'] and not intent['enabled']
    process.kill();process.wait(timeout=10)
   finally:
    if process.poll() is None:process.kill();process.wait(timeout=10)
  cli('uninstall','partial-intent-uninstall',root=partial)
  cli('uninstall','partial-repeat-uninstall',root=partial)
  assert not json.loads(cli('status','partial-final-status',root=partial).stdout)['supervision']['registered']
  record('interrupted_setup_retains_owned_task_intent_and_idempotent_teardown')
 RESULT['bootstrap_artifact_manifest']=BOOT;RESULT['runtime_receipts']=receipts();RESULT['final_state']=state();RESULT['production_signing']='NOT_TESTED_EPHEMERAL_KEYS_ONLY'
finally:
 RESULT['all_runtime_receipts']={}
 for root in created:
  ledger=root/'runtime/upgrades.jsonl'
  if ledger.exists():RESULT['all_runtime_receipts'][root.name]=[json.loads(s) for s in ledger.read_text().splitlines()]
  if (root/'SUPERVISOR.json').exists():
   cfg=json.loads((root/'SUPERVISOR.json').read_text())
   if cfg.get('service') and not cfg.get('uninstalled'):cli('uninstall','finally-uninstall-'+root.name,root=root,expected=None)
 if os.name=='nt':server.close()
 else:server.shutdown();server.server_close();thread.join()
 RESULT['finished_at']=datetime.now(timezone.utc).isoformat();RESULT['private_keys_written']=False;save()
print('Disposable OS lifecycle ended; production paths not used',flush=True)
