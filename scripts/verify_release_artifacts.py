"""CI-only wheel/sdist acceptance. No signing, service setup or publication.

One inventory identifies the exact artifacts built from the approved commit.
Native Windows tests calendar-library and native lease primitives. Scheduler
lifecycle and real reboot acceptance remain separately reported release gates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET

PROJECT = 'aion-indian-market-calendar'
POSIX_UPDATE_MODULES = ('test_automatic_updates.py', 'test_software_updates.py',
                        'test_update_lifecycle.py', 'test_channel_signer.py')


def inventory(directory: Path, source_sha: str) -> dict:
    if not re.fullmatch(r'[0-9a-f]{40}', source_sha):
        raise ValueError('A full approved source commit is required')
    files = sorted(p for p in directory.iterdir() if p.is_file())
    wheels = [p for p in files if p.name.startswith('aion_indian_market_calendar-') and p.suffix == '.whl']
    sdists = [p for p in files if p.name.startswith('aion_indian_market_calendar-') and p.name.endswith('.tar.gz')]
    if len(wheels) != 1 or len(sdists) != 1 or len(files) != 2:
        raise ValueError('Exactly one calendar wheel and one sdist are required')
    return {'schema_version': 1, 'purpose': 'ci-evidence-not-production-trust',
            'project': PROJECT, 'source_commit': source_sha,
            'artifacts': [{'filename':p.name, 'bytes':p.stat().st_size,
                           'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}


def validate_inventory(directory: Path, doc: dict, source_sha: str) -> None:
    if doc != inventory(directory, source_sha):
        raise ValueError('CI artifact inventory or source identity mismatch')


def extract_source(archive: Path, target: Path) -> Path:
    if target.exists():raise FileExistsError('Refuse extraction over an existing directory')
    target.mkdir()
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        for member in members:
            name=member.name
            if ('\\' in name or ':' in name or name.startswith('/') or '..' in Path(name).parts
                    or not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe source archive entry')
            if not (target / name).resolve().is_relative_to(target.resolve()):
                raise ValueError('Source archive escaped quarantine')
        tar.extractall(target, members=members)
    roots = list(target.iterdir())
    if len(roots) != 1 or not (roots[0] / 'tests').is_dir():
        raise ValueError('Source archive has no complete test context')
    return roots[0]


def run(args, *, environment: dict, cwd: Path, log: Path) -> None:
    result=subprocess.run(list(map(str,args)),env=environment,cwd=cwd,capture_output=True,text=True,timeout=600)
    log.write_text(result.stdout+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('Verification command failed; inspect '+log.name)


def verify(args) -> dict:
    if args.scope=='full' and os.name=='nt':
        raise ValueError('POSIX lifecycle fixtures require a separate scope; use library on Windows and native acceptance separately')
    directory=args.dist.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    doc=json.loads(args.inventory.read_text());validate_inventory(directory,doc,args.source_sha)
    result={'source_commit':args.source_sha,'scope':args.scope,'platform':platform.platform(),
            'python':sys.version,'inventory':doc,'runs':[], 'production_systems_used':False,
            'excluded_modules':list(POSIX_UPDATE_MODULES) if args.scope=='library' else [],
            'exclusion_reason':'Platform lifecycle tests separated from library correctness; not a universal updater claim' if args.scope=='library' else None}
    parent={k:os.environ[k] for k in ('PATH','SYSTEMROOT','WINDIR') if k in os.environ}
    with tempfile.TemporaryDirectory(prefix='calendar-artifacts-',dir=output) as temporary:
        root=Path(temporary);(root/'tmp').mkdir()
        environment={**parent,'HOME':str(root),'TEMP':str(root/'tmp'),'TMP':str(root/'tmp'),'TMPDIR':str(root/'tmp'),
                     'AION_IN_CALENDAR_OFFLINE':'1','AION_IN_CALENDAR_CACHE':str(root/'calendar-cache'),
                     'PIP_CONFIG_FILE':os.devnull,'PIP_DISABLE_PIP_VERSION_CHECK':'1','PIP_NO_CACHE_DIR':'1'}
        source=extract_source(next(directory.glob('*.tar.gz')),root/'source')
        for kind,artifact in [('wheel',next(directory.glob('*.whl'))),('sdist',next(directory.glob('*.tar.gz')))]:
            venv=root/kind
            run([sys.executable,'-I','-m','venv',venv],environment=environment,cwd=root,log=output/(kind+'-venv.log'))
            python=venv/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            package=str(artifact)+('[test,updates]' if args.scope=='full' else '')
            run([python,'-I','-m','pip','install',package,'pytest>=8,<10'],environment=environment,cwd=root,log=output/(kind+'-install.log'))
            probe='import aion_indian_market_calendar as p;from pathlib import Path;import sys;assert Path(p.__file__).resolve().is_relative_to(Path(sys.prefix).resolve());print(p.__file__)'
            run([python,'-I','-c',probe],environment=environment,cwd=root,log=output/(kind+'-identity.log'))
            xml=output/(kind+'.xml');command=[python,'-I','-m','pytest','-q',source/'tests','--junitxml='+str(xml)]
            if args.scope=='library':
                command += ['--ignore='+str(source/'tests'/name) for name in POSIX_UPDATE_MODULES]
            run(command,environment=environment,cwd=source,log=output/(kind+'-tests.log'))
            suites=[s.attrib for s in ET.parse(xml).getroot().iter('testsuite')]
            if not suites or any(int(s.get(k,0)) for s in suites for k in ('errors','failures','skipped')):
                raise ValueError('Required tests failed, errored or were skipped')
            probe_env={**environment,'CALENDAR_AUDIT_EXPECTED_MODULE_ROOT':str(venv),
                       'CALENDAR_AUDIT_OLD_FIXTURE':str(source/'tests/fixtures/dataset_2026_10_18'),
                       'CALENDAR_AUDIT_REMOTE_FIXTURE':str(source/'tests/fixtures/dataset_2026_11_03')}
            probe_out=output/(kind+'-independent-42.json')
            run([python,'-I',source/'scripts/verify_independent_contract.py',probe_out],
                environment=probe_env,cwd=root,log=output/(kind+'-independent-42.log'))
            probe=json.loads(probe_out.read_text())
            if probe['passed']!=42 or probe['failed']!=0:raise AssertionError('Independent probe failed')
            result['runs'].append({'artifact':kind,'suites':suites,'independent_probe':{'passed':probe['passed'],'failed':probe['failed']},'windows_native_scheduler':'NOT_TESTED'})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['inventory','test'])
    p.add_argument('--dist',type=Path,required=True)
    p.add_argument('--source-sha',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--inventory',type=Path)
    p.add_argument('--scope',choices=['library','full'],default='full')
    args=p.parse_args()
    if args.operation=='inventory':
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(inventory(args.dist,args.source_sha),indent=2)+'\n')
    else:
        if not args.inventory:p.error('test requires the exact build inventory')
        args.output.mkdir(parents=True,exist_ok=True)
        try:result=verify(args)
        except Exception as exc:
            (args.output/'RESULT.json').write_text(json.dumps({'status':'FAILED','error_type':type(exc).__name__})+'\n')
            raise
        (args.output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
