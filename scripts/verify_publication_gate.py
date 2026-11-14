"""Read-only release gate. Never builds, uploads, signs, or prints credentials."""
from __future__ import annotations
import argparse
import email
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile
import urllib.parse
import urllib.request
import zipfile

REPO = 'AION-Analytics-India/aion-indian-market-calendar'
PROJECT = 'aion-indian-market-calendar'
VERSION = '1.8.0'
ARTIFACT = 'calendar-candidate'
OS = ('ubuntu-24.04', 'macos-15', 'windows-2022')
PYTHON = ('3.10', '3.11', '3.12', '3.13', '3.14')
REQUIRED_JOBS = {'build'} | {f'artifacts ({system}, {version})' for system in OS for version in PYTHON}


def get_json(url, *, github=False, data=None, bearer=None):
    headers = {'Accept': 'application/json', 'User-Agent': 'AION-calendar-release-gate'}
    if github:
        bearer = os.environ.get('GITHUB_TOKEN')
    if bearer:
        headers['Authorization'] = 'Bearer ' + bearer
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, headers=headers, data=data)
    class RefuseRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise ValueError('Release-gate redirect refused')
    with urllib.request.build_opener(RefuseRedirect()).open(req, timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Response exceeds release-gate budget')
    return json.loads(raw)


def inspect_artifacts(dist, inventory, source_sha, source_root=None):
    if not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('Full source identity required')
    if inventory.get('source_commit') != source_sha or inventory.get('project') != PROJECT:
        raise ValueError('Artifact inventory source/project mismatch')
    expected = {f'aion_indian_market_calendar-{VERSION}-py3-none-any.whl', f'aion_indian_market_calendar-{VERSION}.tar.gz'}
    rows = inventory.get('artifacts', [])
    if len(rows) != 2 or {x['filename'] for x in rows} != expected or {p.name for p in dist.iterdir()} != expected:
        raise ValueError('Exactly the two approved artifacts are required')
    for row in rows:
        p = dist / row['filename']
        if p.is_symlink() or p.stat().st_size != row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Artifact bytes/hash differ')
    with zipfile.ZipFile(next(dist.glob('*.whl'))) as wheel, tarfile.open(next(dist.glob('*.tar.gz'))) as source:
        names = wheel.namelist()
        metadata_name = f'aion_indian_market_calendar-{VERSION}.dist-info/METADATA'
        metadata = email.message_from_bytes(wheel.read(metadata_name))
        if metadata['Name'] != PROJECT or metadata['Version'] != VERSION or metadata['Requires-Python'] != '>=3.10' or metadata['License-Expression'] != 'MIT':
            raise ValueError('Distribution identity/Python/license mismatch')
        members = {m.name.split('/', 1)[1]: m for m in source.getmembers() if m.isfile() and '/' in m.name}
        def read(name):
            stream = source.extractfile(members[name])
            if stream is None: raise ValueError('Missing source artifact member')
            return stream.read()
        readme = read('README.md')
        if metadata.get_payload().replace('\r\n', '\n').strip() != readme.decode().replace('\r\n', '\n').strip():
            raise ValueError('Wheel long description and sdist README differ')
        if source_root and readme != (source_root / 'README.md').read_bytes():
            raise ValueError('Artifact README differs from approved source')
        for name in names:
            if name.startswith('aion_indian_market_calendar/') and not name.endswith('/'):
                if wheel.read(name) != read('src/' + name):
                    raise ValueError('Wheel/sdist package bytes differ')
        license_names = [n for n in names if n.endswith('/licenses/LICENSE')]
        if len(license_names) != 1 or wheel.read(license_names[0]) != read('LICENSE'):
            raise ValueError('Wheel/sdist licenses differ')
        if not any(n.startswith('tests/fixtures/') for n in members):
            raise ValueError('Source fixtures missing')
        if any(n.startswith('.locks/') or n.endswith(('.env', '.pyc')) for n in members):
            raise ValueError('Unwanted private/runtime files in source artifact')
    return {'source_commit': source_sha, 'version': VERSION, 'artifact_identity': 'PASS',
            'wheel_sdist_code_data_license_readme': 'IDENTICAL', 'production_upload': False}


def validate_gate(run, jobs, artifact, inventory, *, source_sha, wheel_sha, sdist_sha,
                  current_sha, ref, mode, approval, version_exists):
    if source_sha != current_sha or not re.fullmatch('[0-9a-f]{40}', source_sha):
        raise ValueError('Running workflow differs from approved source')
    if mode not in ('preflight', 'publish'):
        raise ValueError('Unknown publication mode')
    if mode == 'publish' and (ref != 'refs/tags/v1.8.0' or approval != 'GO CALENDAR 1.8.0 CORRECTNESS ONLY'):
        raise ValueError('Exact tag and founder approval required')
    if run.get('head_sha') != source_sha or run.get('conclusion') != 'success' or run.get('status') != 'completed':
        raise ValueError('Accepted run is not green for approved source')
    if run.get('repository', {}).get('full_name') != REPO or run.get('head_repository', {}).get('full_name') != REPO:
        raise ValueError('Foreign/fork run refused')
    if run.get('path') != '.github/workflows/verify-candidate.yml' or run.get('event') not in ('push', 'workflow_dispatch'):
        raise ValueError('Wrong acceptance workflow/event')
    by_name = {j['name']: j for j in jobs}
    if any(by_name.get(name, {}).get('conclusion') != 'success' for name in REQUIRED_JOBS):
        raise ValueError('Required artifact acceptance jobs missing/failed')
    if any(j.get('conclusion') not in ('success', 'skipped') for j in jobs):
        raise ValueError('Unaccounted failed/pending CI job')
    if artifact.get('name') != ARTIFACT or artifact.get('expired') or artifact.get('workflow_run', {}).get('id') != run['id']:
        raise ValueError('Wrong/expired accepted artifact')
    rows = {r['filename']: r['sha256'] for r in inventory['artifacts']}
    if rows != {f'aion_indian_market_calendar-{VERSION}-py3-none-any.whl': wheel_sha,
                f'aion_indian_market_calendar-{VERSION}.tar.gz': sdist_sha} or not all(re.fullmatch('[0-9a-f]{64}', x) for x in (wheel_sha, sdist_sha)):
        raise ValueError('Approved artifact hashes differ')
    if version_exists:
        raise ValueError('PyPI version exists; no retry/replacement/skip-existing')
    return {'mode': mode, 'source_commit': source_sha, 'accepted_run_id': run['id'],
            'release_gate': 'PASS', 'publication_permitted': mode == 'publish',
            'auto_update_production': 'BLOCKED', 'windows_updater_rollout': 'PAUSED'}


def publisher_identity():
    """Mint and discard a short-lived PyPI credential; no artifact is uploaded."""
    url = os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.actions.githubusercontent.com'):
        raise ValueError('Unexpected GitHub OIDC origin')
    query = urllib.parse.parse_qsl(parsed.query)
    url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query + [('audience', 'pypi')])))
    oidc = get_json(url, bearer=os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN'])['value']
    minted = get_json('https://pypi.org/_/oidc/mint-token', data={'token': oidc})
    if not isinstance(minted.get('token'), str) or not minted['token'].startswith('pypi-'):
        raise ValueError('Trusted publishing exchange refused')
    del oidc, minted
    return {'publisher': REPO, 'workflow': 'publish.yml', 'environment': 'pypi',
            'oidc_exchange': 'PASS', 'upload_performed': False, 'credential_saved': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation', choices=['inspect', 'gate', 'identity'])
    p.add_argument('--dist', type=Path);p.add_argument('--inventory', type=Path)
    p.add_argument('--source-sha');p.add_argument('--source-root', type=Path)
    p.add_argument('--run-id', type=int);p.add_argument('--wheel-sha');p.add_argument('--sdist-sha')
    p.add_argument('--mode', choices=['preflight', 'publish'], default='preflight')
    p.add_argument('--approval', default='');p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.operation == 'identity': result = publisher_identity()
    else:
        inventory = json.loads(a.inventory.read_text())
        result = inspect_artifacts(a.dist, inventory, a.source_sha, a.source_root)
        if a.operation == 'gate':
            base = 'https://api.github.com/repos/' + REPO + '/actions/'
            run = get_json(base + 'runs/' + str(a.run_id), github=True)
            jobs = get_json(base + 'runs/' + str(a.run_id) + '/jobs?per_page=100', github=True)['jobs']
            artifacts = get_json(base + 'runs/' + str(a.run_id) + '/artifacts?per_page=100', github=True)['artifacts']
            accepted = [x for x in artifacts if x['name'] == ARTIFACT]
            if len(accepted) != 1: raise ValueError('Ambiguous accepted artifact')
            releases = get_json('https://pypi.org/pypi/' + PROJECT + '/json')['releases']
            result.update(validate_gate(run, jobs, accepted[0], inventory, source_sha=a.source_sha,
                wheel_sha=a.wheel_sha, sdist_sha=a.sdist_sha, current_sha=os.environ['GITHUB_SHA'],
                ref=os.environ['GITHUB_REF'], mode=a.mode, approval=a.approval,
                version_exists=bool(releases.get(VERSION))))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        # No upstream body, token, JWT, environment or private diagnostic output.
        raise SystemExit('Release gate failed: ' + type(exc).__name__)
