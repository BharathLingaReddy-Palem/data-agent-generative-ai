from contextlib import closing
import io
import json
import sqlite3
import threading
import time
from dataclasses import asdict
import numpy as np
import pandas as pd
import pytest
from backend.services.session_store import SessionStore, SessionLimitError
from backend.services.job_queue import JobQueue, Job, JobStatus, QueueFullError
from tests.test_security import upload


def wait_job(queue, job_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        status = queue.get_status(job_id)
        if status['status'] in ('completed', 'failed'):
            return status
        time.sleep(.01)
    pytest.fail('Job did not finish within 10 seconds')


@pytest.mark.parametrize('sample', ['ecommerce_sales', 'saas_churn', 'ops_fulfillment'])
def test_samples_have_full_profiles_and_authenticated_downloads(client, accounts, sample, monkeypatch):
    from frontend.datasets import fetch_sample_dataframe
    import requests
    response = client.post('/api/load-sample', headers=accounts[0], data={'sample_id': sample})
    assert response.status_code == 200, response.text
    metadata = response.json()
    assert len(metadata['preview']) == 10
    assert metadata['shape']['rows'] == metadata['profile']['overview']['total_rows'] == 600
    assert metadata['profile']['columns'] and metadata['profile']['health']
    assert metadata['profile']['correlation'] and metadata['profile']['potential_targets']
    url = f"/api/datasets/{metadata['project_id']}/download"
    csv = client.get(url, headers=accounts[0])
    assert len(pd.read_csv(io.BytesIO(csv.content))) == 600
    assert client.get(url, headers=accounts[1]).status_code == 404
    assert client.get(url).status_code == 401
    class Response:
        text = csv.text
        def raise_for_status(self): pass
    def get(url, headers, timeout):
        assert headers == accounts[0] and url.endswith('/download')
        return Response()
    monkeypatch.setattr(requests, 'get', get)
    frame = fetch_sample_dataframe('http://backend/', accounts[0]['Authorization'][7:], metadata)
    assert len(frame) == 600


def test_session_codec_and_storage_quotas(tmp_path, monkeypatch):
    import backend.services.session_store as module
    store = SessionStore(tmp_path/'sessions.db')
    frame = pd.DataFrame({'date':pd.date_range('2025-01-01', periods=3, tz='UTC'),
        'nullable':pd.Series([1, None, 3], dtype='Int64'), 'number':[np.nan, np.inf, -np.inf]})
    value = dict(owner_id='alice', df=frame, analysis={'health_score':np.float64(90)}, _progress_callback=lambda:None)
    store.save('a', value)
    pd.testing.assert_frame_equal(store.load('a', 'alice')['df'], frame)
    assert store.load('a', 'bob') is None
    assert '_progress_callback' not in store.load('a')
    with pytest.raises(ValueError, match='ownership'):
        store.save('a', dict(value, owner_id='bob'))
    monkeypatch.setattr(module, 'MAX_PROJECTS_PER_USER', 1)
    with pytest.raises(SessionLimitError): store.save('b', value)
    store.save('a', value)  # Updating an existing project is allowed at the count limit.
    store.delete('a', 'bob'); assert store.load('a')
    store.delete('a', 'alice'); assert store.load('a') is None
    monkeypatch.setattr(module, 'MAX_SESSION_STORAGE_BYTES', 1)
    with pytest.raises(SessionLimitError): store.save('b', value)


def test_api_sessions_restore_after_cache_eviction_and_are_owned(client, accounts, monkeypatch):
    import backend.main as api
    monkeypatch.setattr(api, 'MAX_CACHED_SESSIONS', 1)
    pid = upload(client, accounts[0])
    session = api.active_sessions[pid]
    session.update(analysis={'health_score':91, 'errors':[], 'execution_steps':[]},
        chat_messages=[{'role':'user', 'content':'Sales?'}],
        automl={'best_model':{'model_name':'winner'}, 'saved_model_path':'private/path'})
    api.cache_session(pid, session)
    second = upload(client, accounts[0])
    assert list(api.active_sessions) == [second]
    restored = client.get(f'/api/projects/{pid}/session', headers=accounts[0])
    assert restored.status_code == 200, restored.text
    result = restored.json()
    assert result['profile']['overview']['total_rows'] == 3
    assert result['analysis']['health_score'] == 91
    assert result['messages'][0]['content'] == 'Sales?'
    assert result['automl']['best_model']['model_name'] == 'winner'
    assert 'private/path' not in restored.text
    assert client.get(f'/api/projects/{pid}/session', headers=accounts[1]).status_code == 404
    assert {p['id'] for p in client.get('/api/projects', headers=accounts[0]).json()} == {pid, second}
    assert client.delete(f'/api/projects/{pid}', headers=accounts[1]).status_code == 404
    assert client.delete(f'/api/projects/{pid}', headers=accounts[0]).status_code == 200
    assert client.get(f'/api/profile/{pid}', headers=accounts[0]).status_code == 404


def test_upload_quota_does_not_register_orphan_project(client, accounts, monkeypatch):
    import backend.services.session_store as module
    monkeypatch.setattr(module, 'MAX_PROJECTS_PER_USER', 1)
    pid = upload(client, accounts[0])
    denied = client.post('/api/upload', headers=accounts[0], files={'file':('data.csv', b'x,y\n1,2\n')})
    assert denied.status_code == 429
    assert [p['id'] for p in client.get('/api/projects', headers=accounts[0]).json()] == [pid]


def test_job_limits_progress_failure_and_persistent_results(tmp_path):
    path = tmp_path/'jobs.db'
    queue = JobQueue(path, max_workers=1, max_pending=2, max_per_user=1)
    started, release = threading.Event(), threading.Event()
    def work(_progress_callback):
        _progress_callback(42, 'Cross-validating candidate 1')
        started.set()
        assert release.wait(10)
        return {'score': np.float64(.9)}
    try:
        first = queue.submit('a', work, owner_id='alice', kind='automl', on_progress=True)
        assert started.wait(5)
        assert queue.get_status(first)['progress'] == 42
        assert 'Cross-validating' in queue.get_status(first)['current_step']
        with pytest.raises(QueueFullError, match='project'): queue.submit('a', lambda:None, owner_id='bob')
        with pytest.raises(QueueFullError, match='active-job'): queue.submit('b', lambda:None, owner_id='alice')
        def fail(): raise ValueError('Actual agent failure')
        second = queue.submit('b', fail, owner_id='bob')
        assert queue.get_status(second)['status'] == 'queued'
        with pytest.raises(QueueFullError, match='capacity'): queue.submit('c', lambda:None)
        release.set()
        assert wait_job(queue, first)['progress'] == 100
        failed = wait_job(queue, second)
        assert failed['status'] == 'failed' and failed['error'] == 'Actual agent failure'
        assert failed['progress'] < 100
    finally:
        release.set(); queue.shutdown()
    reopened = JobQueue(path)
    try:
        assert reopened.get_result(first) == {'score':.9}
        assert reopened.get_status(second)['error'] == 'Actual agent failure'
    finally: reopened.shutdown()


def test_restart_resumes_queued_work_and_exposes_interrupted_work(tmp_path):
    path = tmp_path/'restart.db'
    queue = JobQueue(path)
    running = Job('running', 'a', owner_id='alice', kind='analysis', status=JobStatus.RUNNING, progress=42)
    queued = Job('queued', 'b', owner_id='bob', kind='analysis', payload={'revision':3})
    queue._save(running); queue._save(queued); queue.shutdown()
    restarted = JobQueue(path)
    calls = []
    def resume(pid, owner, payload, progress):
        calls.append((pid, owner, payload)); progress(50, 'Executing recovered work')
        return {'resumed':True}
    try:
        restarted.recover({'analysis':resume})
        assert wait_job(restarted, 'queued')['status'] == 'completed'
        assert restarted.get_result('queued') == {'resumed':True}
        assert calls == [('b', 'bob', {'revision':3})]
        assert restarted.get_status('running')['status'] == 'failed'
        assert 'restarted' in restarted.get_status('running')['error']
        restarted.recover({'analysis':resume})
        assert len(calls) == 1
    finally: restarted.shutdown()


def test_api_rejects_duplicate_jobs_and_cleaning_during_work(client, accounts, tmp_path, monkeypatch):
    import backend.main as api
    queue = JobQueue(tmp_path/'api-jobs.db', max_workers=1, max_pending=1)
    monkeypatch.setattr(api, 'job_queue', queue)
    pid = upload(client, accounts[0]); started, release = threading.Event(), threading.Event()
    def pipeline(state):
        state['_progress_callback'](24, 'Running schema')
        started.set(); assert release.wait(10)
        return {'errors':[], 'execution_steps':[]}
    monkeypatch.setattr(api, 'run_analyst_pipeline', pipeline)
    try:
        first = client.post('/api/analyze/start', headers=accounts[0], json={'project_id':pid})
        assert first.status_code == 200 and started.wait(5)
        denied = client.post('/api/analyze/start', headers=accounts[0], json={'project_id':pid})
        assert denied.status_code == 429 and denied.headers['retry-after'] == '30'
        assert client.post('/api/clean', headers=accounts[0], json={'project_id':pid}).status_code == 409
        assert client.delete(f'/api/projects/{pid}', headers=accounts[0]).status_code == 409
    finally: release.set(); queue.shutdown()


def test_real_process_restart_keeps_sessions_and_recovers_jobs(tmp_path):
    import os
    import subprocess
    import sys
    path = tmp_path/'process.db'
    script = '''
import threading
import pandas as pd
from backend.services.session_store import session_store
from backend.services.job_queue import JobQueue
from backend.config import DB_PATH
session_store.save('a', dict(owner_id='alice', df=pd.DataFrame({'sales':[10,20,30]})))
queue = JobQueue(DB_PATH, max_workers=1)
started = threading.Event()
def block():
    started.set()
    threading.Event().wait(90)
queue.submit('a', block, owner_id='alice', kind='analysis')
assert started.wait(10)
queue.submit('b', lambda:None, owner_id='bob', kind='analysis', payload={'revision':2})
print('READY', flush=True)
threading.Event().wait(90)
'''
    environment = dict(os.environ, DS_AGENT_DB_PATH=str(path))
    child = subprocess.Popen([sys.executable, '-c', script], env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+20
        records = []
        while time.monotonic() < deadline and child.poll() is None:
            if path.exists():
                with closing(sqlite3.connect(path)) as conn, conn:
                    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='background_jobs'").fetchone():
                        records = [json.loads(r[0]) for r in conn.execute('SELECT snapshot FROM background_jobs')]
                if {r['status'] for r in records} == {'running','queued'}: break
            time.sleep(.05)
        assert {r['status'] for r in records} == {'running','queued'}
    finally:
        child.terminate()
        child.communicate(timeout=10)
    store = SessionStore(path)
    assert store.load('a','alice')['df']['sales'].tolist() == [10,20,30]
    restarted = JobQueue(path)
    try:
        restarted.recover({'analysis':lambda pid,owner,payload,progress:{'revision':payload['revision']}})
        by_project = {r['project_id']:r['job_id'] for r in records}
        assert wait_job(restarted, by_project['b'])['status'] == 'completed'
        assert restarted.get_result(by_project['b']) == {'revision':2}
        assert restarted.get_status(by_project['a'])['status'] == 'failed'
    finally: restarted.shutdown()
