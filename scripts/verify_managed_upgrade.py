#!/usr/bin/env python3
"""Exercise real isolated installs, compatibility rejection and explicit rollback.

Inputs must be local, approved test artifacts. Never point --root at a live
consumer. This script uses synthetic approvals only for its disposable run.
"""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from aion_indian_market_calendar.managed_updater import ManagedUpdater


def manifest(version, wheels):
    doc={'schema_version':1,'project':'aion-indian-market-calendar','approved':True,
         'approval_id':'disposable-acceptance-only','version':version,'artifacts':[
             {'filename':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in wheels]}
    raw=json.dumps(doc,sort_keys=True).encode()
    return raw,hashlib.sha256(raw).hexdigest()


def failing_smoke_wheel(source, destination):
    old='aion_indian_market_calendar-1.8.0.dist-info'
    new='aion_indian_market_calendar-1.8.1.dist-info'
    contents={}
    with zipfile.ZipFile(source) as z:
        for n in z.namelist():
            if n.endswith('/RECORD'):continue
            b=z.read(n)
            if n==old+'/METADATA':b=b.replace(b'Version: 1.8.0\n',b'Version: 1.8.1\n')
            if n=='aion_indian_market_calendar/__init__.py':
                b+=b'\n# Deliberately broken disposable acceptance fixture.\nIndiaMarketCalendar.is_market_open = lambda *args, **kwargs: False\n'
            contents[n.replace(old,new)]=b
    lines=[]
    for n,b in contents.items():lines.append((n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('='),str(len(b))))
    output=io.StringIO();writer=csv.writer(output,lineterminator='\n');writer.writerows(lines);writer.writerow((new+'/RECORD','',''))
    contents[new+'/RECORD']=output.getvalue().encode()
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        for n,b in contents.items():z.writestr(n,b)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--old-wheel',type=Path,required=True)
    ap.add_argument('--new-wheel',type=Path,required=True)
    ap.add_argument('--dependencies',type=Path,required=True)
    args=ap.parse_args()
    if args.root.exists():raise SystemExit('Refuse reuse of an existing acceptance root')
    args.root.mkdir(parents=True)
    wh=args.root/'wheelhouse';wh.mkdir()
    deps=[next(args.dependencies.glob(pattern)) for pattern in ('pytz-*.whl','tzdata-*.whl')]
    for p in [args.old_wheel,args.new_wheel,*deps]:shutil.copyfile(p,wh/p.name)
    deps=[wh/p.name for p in deps]
    u=ManagedUpdater(args.root/'managed',allow_environment_changes=True)
    results=[]
    old=wh/args.old_wheel.name;new=wh/args.new_wheel.name
    for version,wheel in [('1.7.1',old),('1.8.0',new)]:
        raw,digest=manifest(version,[wheel,*deps]);state=u.upgrade(raw,digest,wh)
        assert state['version']==version
        result=subprocess.check_output([str(u.active_python()),'-I','-c','import importlib.metadata as m;print(m.version("aion-indian-market-calendar"))'],text=True).strip()
        assert result==version
        results.append({'case':'real install and accepted version '+version,'result':'PASS','state':state})
    active_before=u.state()
    # Version metadata is valid and installation succeeds; the real fixed smoke
    # checks must reject its deliberately broken CDS behavior.
    bad=wh/'aion_indian_market_calendar-1.8.1-py3-none-any.whl';failing_smoke_wheel(new,bad)
    raw,digest=manifest('1.8.1',[bad,*deps])
    try:u.upgrade(raw,digest,wh)
    except subprocess.CalledProcessError:pass
    else:raise AssertionError('Broken behavior was promoted')
    assert u.state()==active_before
    results.append({'case':'real compatibility failure leaves 1.8.0 active','result':'PASS'})
    state=u.rollback();assert state['version']=='1.7.1'
    results.append({'case':'rollback rechecks prior environment and restores 1.7.1','result':'PASS','state':state})
    state=u.rollback();assert state['version']=='1.8.0'
    results.append({'case':'reverse rollback rechecks accepted 1.8.0','result':'PASS','state':state})
    receipt=[json.loads(x) for x in (u.root/'upgrades.jsonl').read_text().splitlines()]
    assert [x['status'] for x in receipt]==['attempted','success','attempted','success','attempted','failed','rollback','rollback']
    (args.root/'RESULTS.json').write_text(json.dumps({'results':results,'receipts':receipt},indent=2)+'\n')
    print(json.dumps({'passed':len(results),'failed':0,'versions':['1.7.1','1.8.0'],'rollback':'verified'}))


if __name__=='__main__':main()
