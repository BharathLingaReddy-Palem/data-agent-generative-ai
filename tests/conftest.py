import os
from pathlib import Path
import tempfile

_workspace = tempfile.TemporaryDirectory(prefix='ds-agent-tests-')
os.environ['DS_AGENT_DB_PATH'] = str(Path(_workspace.name)/'test.db')
os.environ['ENABLE_CLOUD_SYNC'] = 'false'
os.environ['JWT_SECRET_KEY'] = 'test-secret-' + 'x'*64
os.environ['GROQ_API_KEY'] = ''
os.environ['NVIDIA_API_KEY'] = ''

import pytest
from fastapi.testclient import TestClient
from backend.main import app, active_sessions


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    import requests
    def blocked(*args, **kwargs):
        raise AssertionError('Offline regression tests must not call external providers.')
    monkeypatch.setattr(requests.Session, 'request', blocked)


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client
    active_sessions.clear()


@pytest.fixture
def accounts(client):
    import uuid
    headers=[]
    for prefix in ('alice','bob'):
        name=prefix+uuid.uuid4().hex[:12]
        credentials=dict(username=name,password='test-password-12345')
        assert client.post('/api/auth/register',json=credentials).status_code==201
        response=client.post('/api/auth/login',json=credentials)
        assert response.status_code==200
        headers.append({'Authorization':'Bearer '+response.json()['access_token']})
    return headers
