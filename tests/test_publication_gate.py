"""Actual publication gate: no upload, credentials, OIDC exchange or live account."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('publication_gate', Path(__file__).parents[1] / 'scripts/verify_publication_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def valid():
    sha = 'a' * 40
    run = {'id': 10, 'head_sha': sha, 'status': 'completed', 'conclusion': 'success',
           'repository': {'full_name': gate.REPO}, 'head_repository': {'full_name': gate.REPO},
           'path': '.github/workflows/verify-candidate.yml', 'event': 'push'}
    jobs = [{'name': name, 'conclusion': 'success'} for name in gate.REQUIRED_JOBS]
    artifact = {'name': gate.ARTIFACT, 'expired': False, 'workflow_run': {'id': 10}}
    inventory = {'artifacts': [
        {'filename': 'aion_indian_market_calendar-1.8.0-py3-none-any.whl', 'sha256': 'b' * 64},
        {'filename': 'aion_indian_market_calendar-1.8.0.tar.gz', 'sha256': 'c' * 64}]}
    kwargs = dict(source_sha=sha, current_sha=sha, wheel_sha='b' * 64, sdist_sha='c' * 64,
                  ref='refs/tags/v1.8.0', mode='publish', approval='GO CALENDAR 1.8.0 CORRECTNESS ONLY', version_exists=False)
    return run, jobs, artifact, inventory, kwargs


def test_exact_approved_candidate_can_pass_gate_without_upload():
    run, jobs, artifact, inventory, kw = valid()
    result = gate.validate_gate(run, jobs, artifact, inventory, **kw)
    assert result['publication_permitted'] and result['auto_update_production'] == 'BLOCKED'


def test_preflight_never_grants_publication_permission():
    run, jobs, artifact, inventory, kw = valid()
    kw.update(mode='preflight', ref='refs/heads/ci/calendar-1.8-acceptance', approval='')
    assert not gate.validate_gate(run, jobs, artifact, inventory, **kw)['publication_permitted']


@pytest.mark.parametrize('change', [
    'missing_go', 'wrong_go', 'wrong_tag', 'wrong_source', 'wrong_run_source', 'failed_run',
    'incomplete_run', 'fork', 'wrong_repo', 'wrong_workflow', 'pull_request', 'missing_job',
    'failed_job', 'pending_job', 'expired_artifact', 'wrong_artifact_run', 'wrong_artifact_name',
    'wrong_wheel', 'wrong_sdist', 'existing_version', 'unexpected_failed_job'])
def test_publication_refuses_unsafe_or_ambiguous_acceptance(change):
    run, jobs, artifact, inventory, kw = valid()
    if change == 'missing_go': kw['approval'] = ''
    elif change == 'wrong_go': kw['approval'] = 'GO'
    elif change == 'wrong_tag': kw['ref'] = 'refs/heads/main'
    elif change == 'wrong_source': kw['current_sha'] = 'd' * 40
    elif change == 'wrong_run_source': run['head_sha'] = 'd' * 40
    elif change == 'failed_run': run['conclusion'] = 'failure'
    elif change == 'incomplete_run': run['status'] = 'in_progress'
    elif change == 'fork': run['head_repository']['full_name'] = 'foreign/fork'
    elif change == 'wrong_repo': run['repository']['full_name'] = 'foreign/repo'
    elif change == 'wrong_workflow': run['path'] = '.github/workflows/other.yml'
    elif change == 'pull_request': run['event'] = 'pull_request'
    elif change == 'missing_job': jobs.pop()
    elif change == 'failed_job': jobs[0]['conclusion'] = 'failure'
    elif change == 'pending_job': jobs[0]['conclusion'] = None
    elif change == 'expired_artifact': artifact['expired'] = True
    elif change == 'wrong_artifact_run': artifact['workflow_run']['id'] = 11
    elif change == 'wrong_artifact_name': artifact['name'] = 'unrelated'
    elif change == 'wrong_wheel': kw['wheel_sha'] = 'e' * 64
    elif change == 'wrong_sdist': kw['sdist_sha'] = 'e' * 64
    elif change == 'existing_version': kw['version_exists'] = True
    elif change == 'unexpected_failed_job': jobs.append({'name': 'additional', 'conclusion': 'cancelled'})
    with pytest.raises(ValueError): gate.validate_gate(run, jobs, artifact, inventory, **kw)
