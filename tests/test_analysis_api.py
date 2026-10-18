import json
from pathlib import Path
import time
import numpy as np
import pytest
from backend.services.report_artifacts import report_path, report_metadata
from tests.test_security import upload

CONTRACT=Path(__file__).with_name('data')/'analysis_contract.json'


def test_sync_and_background_analysis_share_complete_contract(client,accounts,tmp_path,monkeypatch):
    import backend.main as api
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    pid=upload(client,accounts[0])
    state=json.loads(CONTRACT.read_text())
    for format,content in [('pdf',b'%PDF-1.4\nreport'),('pptx',b'PK presentation')]:
        path=report_path(pid,format,tmp_path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        state['report_'+format+'_path']=str(path)
    state['health_score']=np.float64(92.5)
    state['trend_results']['missing_value']=float('nan')
    state['executive_report']={'local_pdf_path':'private-server-path'}
    state['df_raw']='not-public'
    def pipeline(initial):
        assert initial['owner_id'] and initial['project_id']==pid
        return state
    monkeypatch.setattr(api,'run_analyst_pipeline',pipeline)
    sync=client.post('/api/analyze',headers=accounts[0],json={'project_id':pid})
    assert sync.status_code==200,sync.text
    job=client.post('/api/analyze/start',headers=accounts[0],json={'project_id':pid}).json()
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        status=client.get(job['poll_url'],headers=accounts[0]).json()
        if status['status'] in ('completed','failed'):break
        time.sleep(0.01)
    assert status['status']=='completed',status
    queued=client.get(job['result_url'],headers=accounts[0])
    assert queued.status_code==200,queued.text
    result=sync.json()
    assert queued.json()==result
    for key in ('analysis_plan','trend_results','benchmark_results','hypothesis_results','executive_report','report_artifacts'):
        assert result[key],key
    assert result['trend_results']['missing_value'] is None
    assert result['errors']==['KPI warning','EDA warning']
    assert 'df_raw' not in result and 'private-server-path' not in sync.text
    for format in ('pdf','pptx'):
        assert result['report_artifacts'][format]['available']
        assert result['report_'+format+'_url']==f'/api/reports/{pid}/{format}/download'


@pytest.mark.parametrize('format,content,media_type',[
    ('pdf',b'%PDF-1.4\ntest','application/pdf'),
    ('pptx',b'PK\x03\x04test','application/vnd.openxmlformats-officedocument.presentationml.presentation'),
])
def test_report_downloads_require_owner_and_survive_session_loss(client,accounts,tmp_path,monkeypatch,format,content,media_type):
    import backend.main as api
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    pid=upload(client,accounts[0]);path=report_path(pid,format,tmp_path)
    path.parent.mkdir(parents=True);path.write_bytes(content)
    url=f'/api/reports/{pid}/{format}/download'
    assert client.get(url).status_code==401
    assert client.get(url,headers=accounts[1]).status_code==404
    api.active_sessions.clear()
    response=client.get(url,headers=accounts[0])
    assert response.status_code==200 and response.content==content
    assert response.headers['content-type']==media_type
    assert 'attachment' in response.headers['content-disposition']


def test_missing_exports_and_invalid_locations(client,accounts,tmp_path,monkeypatch):
    import backend.main as api
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    pid=upload(client,accounts[0])
    for format in ('pdf','pptx','zip'):
        assert client.get(f'/api/reports/{pid}/{format}/download',headers=accounts[0]).status_code==404
    for project in ('../escape','x/../../escape','C:\\escape','..'):
        with pytest.raises(ValueError):report_path(project,'pdf',tmp_path)
    for metadata in report_metadata(pid,{},tmp_path).values():
        assert metadata['available'] is False and metadata['download_url'] is None


def test_model_download_prefers_new_champion(client,accounts,tmp_path,monkeypatch):
    import backend.main as api
    monkeypatch.setattr(api,'BASE_DIR',tmp_path)
    pid=upload(client,accounts[0]);directory=tmp_path/'artifacts'/'models'/pid
    directory.mkdir(parents=True)
    (directory/'a_old_model.joblib').write_bytes(b'old')
    (directory/'champion.joblib').write_bytes(b'tuned champion')
    response=client.get(f'/api/models/{pid}/download',headers=accounts[0])
    assert response.content==b'tuned champion'
