from contextlib import closing
import sqlite3
import uuid
import pytest
import jwt
from backend.services.auth_service import AuthService, auth_service
from backend.services.supabase_service import db_service, DatabaseService
from backend.config import DB_PATH


def upload(client, headers):
    response=client.post('/api/upload',headers=headers,files={'file':('sales.csv',b'region,sales,profit\nEast,100,20\nWest,200,-20\nEast,50,0\n','text/csv')})
    assert response.status_code==200,response.text
    return response.json()['project_id']


def test_auth_and_revocation(client,accounts):
    assert client.get('/api/sample-datasets').status_code==401
    assert client.get('/api/experiments',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert client.get('/api/auth/me',headers=accounts[0]).status_code==200
    assert client.post('/api/auth/logout',headers=accounts[0]).status_code==200
    assert client.get('/api/auth/me',headers=accounts[0]).status_code==401


@pytest.mark.parametrize('method,path,payload',[
    ('get','/api/profile/{pid}',None), ('get','/api/models/{pid}/download',None),
    ('get','/api/experiments/{pid}',None), ('post','/api/analyze',{}),
    ('post','/api/analyze/start',{}), ('post','/api/chat',{'message':'Sales?'}),
    ('post','/api/clean',{}), ('post','/api/automl/start',{}),
    ('post','/api/predict',{'input_data':{'sales':10}}),
])
def test_cross_user_access_denied(client,accounts,method,path,payload):
    pid=upload(client,accounts[0])
    kwargs={'headers':accounts[1]}
    if payload is not None: kwargs['json']=dict(payload,project_id=pid)
    assert client.request(method,path.format(pid=pid),**kwargs).status_code==404
    assert client.request(method,path.format(pid=pid),**({k:v for k,v in kwargs.items() if k!='headers'})).status_code==401


def test_project_registration_and_chat(client,accounts,monkeypatch):
    import backend.main as api
    pid=upload(client,accounts[0])
    user=client.get('/api/auth/me',headers=accounts[0]).json()
    assert db_service.get_project(pid)['owner_id']==user['id']
    assert client.get('/api/profile/'+pid,headers=accounts[0]).status_code==200
    answers=iter(["result = df['profit'].sum()",'Profit is exactly zero.'])
    monkeypatch.setattr(api,'invoke_llm',lambda *a,**k:next(answers))
    response=client.post('/api/chat',headers=accounts[0],json=dict(project_id=pid,message='Total profit?'))
    assert response.status_code==200,response.text
    assert response.json()['calculated_evidence']=='0'
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        assert conn.execute('SELECT count(*) FROM chat_messages WHERE project_id=?',(pid,)).fetchone()[0]==2


def test_job_ownership(client,accounts,monkeypatch):
    import backend.main as api
    pid=upload(client,accounts[0])
    monkeypatch.setattr(api.job_queue,'get_status',lambda job:dict(project_id=pid,status='completed',progress=100))
    monkeypatch.setattr(api.job_queue,'get_result',lambda job:dict(project_id=pid,answer='private'))
    for suffix in ('status','result'):
        assert client.get('/api/job/job-1/'+suffix,headers=accounts[1]).status_code==404
        assert client.get('/api/job/job-1/'+suffix,headers=accounts[0]).status_code==200


def test_experiments_filtered_before_limit(client,accounts):
    pid=upload(client,accounts[0]); other=upload(client,accounts[1])
    with closing(sqlite3.connect(DB_PATH)) as conn, conn:
        for project in (pid,other):
            conn.execute('INSERT INTO experiments(id,project_id) VALUES(?,?)',(str(uuid.uuid4()),project))
    results=client.get('/api/experiments',headers=accounts[0]).json()
    assert results and all(r['project_id']==pid for r in results)


def test_expired_token_and_password_hash(tmp_path):
    service=AuthService(tmp_path/'auth.db',secret='s'*64)
    user=service.register('sampleuser','a-valid-password')
    token=service.login('sampleuser','a-valid-password')['access_token']
    claims=jwt.decode(token,service.secret,algorithms=['HS256'],audience='ds-agent-api')
    claims['exp']=1
    with pytest.raises(ValueError):service.authenticate(jwt.encode(claims,service.secret,algorithm='HS256'))
    with closing(sqlite3.connect(service.db_path)) as conn, conn:
        stored=conn.execute('SELECT password_hash FROM users').fetchone()[0]
    assert stored.startswith('$argon2') and stored!='a-valid-password'
    for _ in range(10):
        with pytest.raises(ValueError):service.login('sampleuser','wrongpassword')
    with pytest.raises(PermissionError):service.login('sampleuser','a-valid-password')


def test_same_id_and_children(tmp_path):
    service=DatabaseService(tmp_path/'local.db')
    pid=str(uuid.uuid4())
    service.save_project('sales','',project_id=pid,owner_id='alice')
    service.save_project('sales','cloud-url',project_id=pid)
    service.save_report(pid,'report-url');service.save_chat_message(pid,'user','Question')
    assert service.get_project(pid)['owner_id']=='alice'
    with closing(sqlite3.connect(service.local_db_path)) as conn, conn:
        assert conn.execute('SELECT count(*) FROM projects').fetchone()[0]==1
        assert conn.execute('SELECT project_id FROM reports').fetchone()[0]==pid
    with pytest.raises(ValueError):service.save_project('sales','',project_id=pid,owner_id='bob')
    with pytest.raises(ValueError):service.save_chat_message('missing','user','no parent')


def test_legacy_migration_preserves_and_backs_up(tmp_path):
    path=tmp_path/'old.db'
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript('''CREATE TABLE projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,csv_url TEXT NOT NULL,task_type TEXT,target_column TEXT,status TEXT,created_at TEXT NOT NULL);
            CREATE TABLE reports(id TEXT PRIMARY KEY,project_id TEXT,pdf_url TEXT NOT NULL,summary TEXT,created_at TEXT NOT NULL);
            INSERT INTO reports VALUES('r','orphan','pdf','summary','today');''')
    service=DatabaseService(path)
    assert service.get_project('orphan')['owner_id'] is None
    assert list(tmp_path.glob('old.db.bak-*'))


def test_profile_and_samples_register_owned_id(client,accounts):
    for sample in ('ecommerce_sales','saas_churn','ops_fulfillment'):
        response=client.post('/api/load-sample',headers=accounts[0],data={'sample_id':sample})
        assert response.status_code==200,response.text
        assert db_service.get_project(response.json()['project_id'])['owner_id']
    response=client.post('/api/profile',headers=accounts[0],files={'file':('simple.csv',b'x,y\n1,2\n3,4\n','text/csv')})
    assert response.status_code==200,response.text
    assert db_service.get_project(response.json()['project_id'])['owner_id']


def test_persistent_signing_key(tmp_path,monkeypatch):
    import backend.services.auth_service as module
    monkeypatch.setattr(module,'JWT_SECRET_KEY','')
    service=AuthService(tmp_path/'auth.db')
    service.register('persistent','long-secure-password')
    token=service.login('persistent','long-secure-password')['access_token']
    restarted=AuthService(tmp_path/'auth.db')
    assert restarted.secret==service.secret
    assert restarted.authenticate(token)['username']=='persistent'
    assert not list(tmp_path.glob('.auth-key-*'))


def test_successful_cloud_mirror_retains_local_id(tmp_path):
    from unittest.mock import MagicMock
    service=DatabaseService(tmp_path/'mirror.db')
    service.supabase=MagicMock()
    pid=str(uuid.uuid4())
    assert service.save_project('sales','url',project_id=pid,owner_id='alice')==pid
    assert service.get_project(pid)['owner_id']=='alice'
    record=service.supabase.table.return_value.upsert.call_args.args[0]
    assert record['id']==pid and record['owner_id']=='alice'
    service.save_chat_message(pid,'user','Question')
    with closing(sqlite3.connect(service.local_db_path)) as conn, conn:
        assert conn.execute('SELECT project_id FROM chat_messages').fetchone()[0]==pid


def test_owner_can_download_model(client,accounts,tmp_path,monkeypatch):
    import backend.main as api
    pid=upload(client,accounts[0])
    artifact=tmp_path/'artifacts'/'models'/pid
    artifact.mkdir(parents=True)
    (artifact/'model.joblib').write_bytes(b'model-bytes')
    monkeypatch.setattr(api,'BASE_DIR',tmp_path)
    assert client.get('/api/models/'+pid+'/download',headers=accounts[0]).content==b'model-bytes'
    assert client.get('/api/models/'+pid+'/download',headers=accounts[1]).status_code==404
