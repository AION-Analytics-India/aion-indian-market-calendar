"""Read-only-source calendar contract probes; writes only caller's quarantine."""
from pathlib import Path
from datetime import date,datetime,time
from zoneinfo import ZoneInfo
import json,sys,os,hashlib,inspect,shutil,contextlib,io
import aion_indian_market_calendar as p
from aion_indian_market_calendar import IndiaMarketCalendar as Cal,store,microstructure as ms
expected_root = Path(os.environ["CALENDAR_AUDIT_EXPECTED_MODULE_ROOT"]).resolve()
if not Path(p.__file__).resolve().is_relative_to(expected_root):
    raise RuntimeError("Wrong calendar implementation loaded; refuse installed-package fallback")
OUT=Path(sys.argv[1]);OUT.parent.mkdir(parents=True,exist_ok=True)
rows=[]
def case(name,fn,expected,scope='contract'):
 try:
  v=fn()
  if isinstance(v,(date,time)):v=v.isoformat()
 except Exception as e:v={'exception':type(e).__name__}
 ok=(v==expected) if not callable(expected) else expected(v)
 rows.append({'case':name,'scope':scope,'actual':v,'expected':expected if not callable(expected) else 'Documented unsupported input must raise ValueError or FileNotFoundError','result':'PASS' if ok else 'FAIL'})
cal=Cal()
segs=lambda obj,day,market:[(s.open.strftime('%H:%M'),s.close.strftime('%H:%M'),s.kind) for s in (obj.get_session(day,market=market) or [])]
case('CDS regular hours',lambda:[(s.open.strftime('%H:%M'),s.close.strftime('%H:%M')) for s in cal.get_session(date(2026,11,13),market='CDS')],[('09:00','17:00')])
for alias in ['CDS','CURRENCY_DERIVATIVES','NSE_CURRENCY_DERIVATIVES','USDINR','EURINR','GBPINR','JPYINR']:
 case('CDS alias '+alias,lambda a=alias:cal.is_market_open('2026-11-13T16:30+05:30',market=a),True)
case('CDS before open',lambda:cal.is_market_open('2026-11-13T08:59:59+05:30',market='CDS'),False)
case('CDS after close',lambda:cal.is_market_open('2026-11-13T17:00:01+05:30',market='CDS'),False)
case('CDS UTC conversion',lambda:cal.is_market_open('2026-11-13T03:30:00+00:00',market='CDS'),True)
case('CDS bank closing holiday',lambda:ms.is_trading_day('2026-04-01','CDS',calendar=cal),False)
case('Equity trades on bank closing holiday',lambda:ms.is_trading_day('2026-04-01','NSE',calendar=cal),True)
case('NSE settlement closed on bank closing',lambda:ms.is_settlement_day('2026-04-01',calendar=cal),False)
for alias in ['EURUSD','GBPUSD','USDJPY','BSE_CURRENCY_DERIVATIVES']:
 case('Unsupported currency contract '+alias,lambda a=alias:cal.get_session(date(2026,11,13),market=a),lambda v:isinstance(v,dict) and v.get('exception')=='ValueError')
for day,expected in [('2026-10-30','23:30:00'),('2026-11-02','23:55:00'),('2026-03-06','23:55:00'),('2026-03-09','23:30:00')]:
 case('MCX seasonal close '+day,lambda d=day:p.commodity_close(date.fromisoformat(d)),expected)
case('MCX holiday evening',lambda:[(s.open.strftime('%H:%M'),s.close.strftime('%H:%M')) for s in cal.get_session(date(2026,3,3),market='MCX')],[('17:00','23:55')])
case('December CAS phase',lambda:ms.get_market_phase('2026-12-07T15:32+05:30','NSE_EQUITY_FNO_UNDERLYING',calendar=cal),'CLOSING_AUCTION')
case('December derivative segment open',lambda:cal.is_market_open('2026-12-07T15:44+05:30',market='NIFTY'),True)
case('December derivative segment closed',lambda:cal.is_market_open('2026-12-07T15:46+05:30',market='NIFTY'),False)
case('CAS transition excludes continuous matching',lambda:cal.is_continuous_trading('2026-12-07T15:30:00+05:30',market='NSE_EQUITY_FNO_UNDERLYING'),False)
case('CDS phase end excludes continuous',lambda:ms.get_market_phase('2026-11-13T17:00+05:30','CDS',calendar=cal),'CLOSED')
case('NIFTY holiday expiry shift',lambda:ms.get_expiry_day('NIFTY','2026-10-19',calendar=cal),'2026-10-19')
case('BANKNIFTY monthly holiday shift',lambda:ms.get_expiry_day('BANKNIFTY','2026-03-25',calendar=cal),'2026-03-30')
case('SENSEX Thursday holiday shift',lambda:ms.get_expiry_day('SENSEX','2026-03-23',calendar=cal),'2026-03-25')
for index in ['BANKEX','USDINR']:
 case('Unsupported expiry '+index,lambda x=index:ms.get_expiry_day(x,'2026-11-13',calendar=cal),lambda v:isinstance(v,dict) and v.get('exception')=='ValueError')
case('Unknown 2027 class trading day refuses',lambda:cal.is_trading_day(datetime(2027,1,26,10,tzinfo=ZoneInfo('Asia/Kolkata'))),lambda v:isinstance(v,dict) and v.get('exception') in ['ValueError','FileNotFoundError'])
case('Unknown 2027 class market-open refuses',lambda:cal.is_market_open('2027-01-26T10:00+05:30'),lambda v:isinstance(v,dict) and v.get('exception') in ['ValueError','FileNotFoundError'])
case('Unknown Dec28 module trading refuses',lambda:ms.is_trading_day('2026-12-28',calendar=cal),lambda v:isinstance(v,dict) and v.get('exception') in ['ValueError','FileNotFoundError'])
case('Aware date-taking trading helper uses IST date',lambda:ms.is_trading_day(datetime(2026,10,23,22,tzinfo=ZoneInfo('UTC')),calendar=cal),False)
case('Aware date-taking settlement helper uses IST date',lambda:ms.is_settlement_day(datetime(2026,10,23,22,tzinfo=ZoneInfo('UTC')),calendar=cal),False)
case('Source Muhurat NSE continuous window',lambda:[(s.open.strftime('%H:%M'),s.close.strftime('%H:%M')) for s in cal.get_session(date(2026,11,8),market='NSE')],[('14:20','15:30')],'regulatory_current_data')
case('Muhurat CAS securities not continuous at 15:20',lambda:cal.is_continuous_trading('2026-11-08T15:20+05:30',market='NSE_EQUITY_FNO_UNDERLYING'),False,'regulatory_current_data')
# Current installed code is never changed. This tests a verified fixture refresh in a quarantine.
old=Path(os.environ['CALENDAR_AUDIT_OLD_FIXTURE']);new=Path(os.environ['CALENDAR_AUDIT_REMOTE_FIXTURE']);cache=Path(os.environ['AION_IN_CALENDAR_CACHE'])/'refresh-probe';cache.mkdir(parents=True,exist_ok=True)
store.CACHE_DIR=cache;store.BUNDLED_DIR=old
store._state.update({'loaded':False,'data':{},'source':'none','warned':set(),'directory':None,'manifest':{},'identity':None,'signature':None,'last_sync':0.0,'last_attempt':0.0,'last_refresh':None})
p._bundled_calendar.cache_clear();ms._calendar.cache_clear()
os.environ['AION_IN_CALENDAR_OFFLINE']='1';existing=Cal();before=segs(existing,date(2026,11,8),'NSE')
def fake_fetch(url,timeout=5):return (new/url.rsplit('/',1)[-1].split('?',1)[0]).read_bytes()
store._fetch=fake_fetch;os.environ.pop('AION_IN_CALENDAR_OFFLINE',None);result=store.refresh(force=True)
after=segs(existing,date(2026,11,8),'NSE');fresh=segs(Cal(),date(2026,11,8),'NSE')
rows.append({'case':'Existing object follows explicit verified data refresh','scope':'refresh lifecycle','actual':after,'expected':fresh,'result':'PASS' if after==fresh else 'FAIL','before':before,'refresh_result':result})
# A daily-due read must not remain cached forever (no real network; fake supplier above).
requests=[];store._fetch=lambda url,timeout=5:(requests.append(url) or fake_fetch(url,timeout));store._due_for_check=lambda:True
if hasattr(store,'SYNC_INTERVAL_SECONDS'):store.SYNC_INTERVAL_SECONDS=0;store.RETRY_AFTER_FAILURE_SECONDS=0
store.load();rows.append({'case':'Loaded process rechecks a due dataset','scope':'refresh lifecycle','actual':len(requests),'expected':'At least one manifest request to the synthetic fixture supplier','result':'PASS' if requests else 'FAIL'})
report={'package_file':p.__file__,'reported_version':p.__version__,'source_sha256':hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest(),'coverage':{'start':str(cal.coverage_start),'end':str(cal.coverage_end)},'public_functions':{n:str(inspect.signature(getattr(p,n))) for n in p.__all__ if callable(getattr(p,n,None))},'rows':rows,'passed':sum(r['result']=='PASS' for r in rows),'failed':sum(r['result']=='FAIL' for r in rows)}
OUT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'source':p.__file__,'passed':report['passed'],'failed':report['failed'],'failures':[r['case'] for r in rows if r['result']=='FAIL']}))
