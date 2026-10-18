"""Real downloaded Kaggle files; fetch explicitly, then run entirely offline."""
import io
import importlib
import time
from pathlib import Path
import pandas as pd
import pytest

DATA=Path(__file__).parent/'data'/'kaggle'
FILES=[
    ('uciml__iris/Iris.csv',150,6,',','.'),
    ('uciml__red-wine-quality-cortez-et-al-2009/winequality-red.csv',1599,12,',','.'),
    ('yasserh__titanic-dataset/Titanic-Dataset.csv',891,12,',','.'),
    ('rakannimer__air-passengers/AirPassengers.csv',144,2,',','.'),
    ('shrutimechlearn__churn-modelling/Churn_Modelling.csv',10000,14,',','.'),
    ('mirichoi0218__insurance/insurance.csv',1338,7,',','.'),
    ('fedesoriano__air-quality-data-set/AirQuality.csv',9471,17,';',','),
    ('uciml__sms-spam-collection-dataset/spam.csv',5572,5,',','.'),
    ('vivek468__superstore-dataset-final/Sample - Superstore.csv',9994,21,',','.'),
    ('abcsds__pokemon/Pokemon.csv',800,13,',','.'),
]


@pytest.mark.parametrize('filename,rows,columns,separator,decimal',FILES)
def test_full_kaggle_file_upload_profile_and_round_trip(client,accounts,filename,rows,columns,separator,decimal):
    path=DATA/filename
    if not path.exists():pytest.skip('Run testing_tools/fetch_kaggle_datasets.py for real Kaggle verification.')
    response=client.post('/api/profile',headers=accounts[0],files={'file':(path.name,path.read_bytes(),'text/csv')})
    assert response.status_code==200,response.text
    profile=response.json();pid=profile['project_id']
    assert profile['overview']['total_rows']==rows
    assert profile['overview']['total_columns']==columns
    response=client.get(f'/api/datasets/{pid}/download',headers=accounts[0])
    actual=pd.read_csv(io.BytesIO(response.content))
    encoding='cp1252' if 'spam.csv' in filename or 'Superstore.csv' in filename else 'utf-8'
    expected=pd.read_csv(path,sep=separator,decimal=decimal,encoding=encoding)
    pd.testing.assert_frame_equal(actual,expected,check_dtype=False)
    assert client.get(f'/api/projects/{pid}/session',headers=accounts[0]).status_code==200
    assert client.get(f'/api/datasets/{pid}/download',headers=accounts[1]).status_code==404


@pytest.mark.parametrize('filename,rows,columns,separator,decimal',FILES)
def test_real_analysis_and_downloadable_reports(client,accounts,monkeypatch,tmp_path,filename,rows,columns,separator,decimal):
    import backend.main as api
    path=DATA/filename
    if not path.exists():pytest.skip('Fetch Kaggle test datasets first.')
    report=importlib.import_module('backend.agents.report_agent')
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    monkeypatch.setattr(report,'REPORTS_DIR',tmp_path)
    for name in ('supervisor','schema_agent','quality_agent','kpi_agent','eda_agent','diagnostic_agent','hypothesis_agent','trend_agent','report_agent'):
        module=importlib.import_module('backend.agents.'+name)
        monkeypatch.setattr(module,'invoke_llm',lambda **kwargs:'Offline narrative; deterministic fallback.')
    uploaded=client.post('/api/profile',headers=accounts[0],files={'file':(path.name,path.read_bytes())})
    assert uploaded.status_code==200,uploaded.text
    pid=uploaded.json()['project_id']
    response=client.post('/api/analyze',headers=accounts[0],json={'project_id':pid})
    assert response.status_code==200,response.text
    result=response.json()
    assert not result['errors'],result['errors']
    assert result['analysis_plan'] and result['quality_audit'] and result['kpi_results']
    assert result['charts'] and result['executive_report']
    if 'AirPassengers' in filename:
        assert result['trend_results']['available'],result['trend_results']
    for format,magic in [('pdf',b'%PDF'),('pptx',b'PK')]:
        url=result[f'report_{format}_url']
        assert url and result['report_artifacts'][format]['available']
        downloaded=client.get(url,headers=accounts[0])
        assert downloaded.status_code==200,downloaded.text
        assert downloaded.content.startswith(magic)
        assert client.get(url,headers=accounts[1]).status_code==404
    api.active_sessions.clear()
    restored=client.get(f'/api/projects/{pid}/session',headers=accounts[0])
    assert restored.status_code==200
    assert restored.json()['analysis']['report_artifacts']['pdf']['available']


@pytest.mark.parametrize('filename,target,task',[
    (FILES[0][0],'Species','classification'),
    (FILES[1][0],'quality','regression'),
    (FILES[2][0],'Survived','classification'),
    (FILES[4][0],'Exited','classification'),
    (FILES[5][0],'charges','regression'),
])
def test_real_automl_job_saved_model_and_predictions(client,accounts,monkeypatch,tmp_path,filename,target,task):
    import backend.main as api
    import backend.services.automl_engine as engine
    path=DATA/filename
    if not path.exists():pytest.skip('Fetch Kaggle test datasets first.')
    monkeypatch.setattr(api,'BASE_DIR',tmp_path)
    monkeypatch.setattr(engine,'ARTIFACTS_DIR',tmp_path/'artifacts')
    uploaded=client.post('/api/profile',headers=accounts[0],files={'file':(path.name,path.read_bytes())})
    assert uploaded.status_code==200,uploaded.text
    pid=uploaded.json()['project_id']
    response=client.post('/api/automl/start',headers=accounts[0],json={
        'project_id':pid,'target_column':target,'task_type':task,'run_tuning':False})
    assert response.status_code==200,response.text
    job=response.json();deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        status=client.get(job['poll_url'],headers=accounts[0]).json()
        if status['status'] in ('completed','failed'):break
        time.sleep(0.2)
    assert status['status']=='completed',status
    result=client.get(job['result_url'],headers=accounts[0]).json()
    assert not result['failed_models'],result['failed_models']
    assert len(result['leaderboard'])>=5
    assert result['dataset_shape']['rows']==len(pd.read_csv(path))
    assert result['evaluation']['test_used_for_selection'] is False
    assert result['best_model']['primary_metric_name']==('f1_macro' if task=='classification' else 'r2_score')
    frame=pd.read_csv(path).drop(columns=target).head(3).astype(object)
    inputs=frame.where(frame.notna(),None).to_dict('records')
    predicted=client.post('/api/predict',headers=accounts[0],json={'project_id':pid,'input_data':inputs})
    assert predicted.status_code==200,predicted.text
    assert predicted.json()['count']==3
    assert client.get(f'/api/models/{pid}/download',headers=accounts[0]).status_code==200
    api.active_sessions.clear()
    restored=client.post('/api/predict',headers=accounts[0],json={'project_id':pid,'input_data':inputs})
    assert restored.json()==predicted.json()
    assert client.post('/api/predict',headers=accounts[1],json={'project_id':pid,'input_data':inputs}).status_code==404


def test_real_time_series_chat_uses_full_dataset_and_persists(client,accounts,monkeypatch):
    import backend.main as api
    path=DATA/FILES[3][0]
    if not path.exists():pytest.skip('Fetch Kaggle test datasets first.')
    uploaded=client.post('/api/profile',headers=accounts[0],files={'file':(path.name,path.read_bytes())})
    pid=uploaded.json()['project_id']
    source=pd.read_csv(path)
    total=int(source['#Passengers'].sum())
    replies=iter(["result = df['#Passengers'].sum()",f'Total passenger count: {total}'])
    monkeypatch.setattr(api,'invoke_llm',lambda *args,**kwargs:next(replies))
    response=client.post('/api/chat',headers=accounts[0],json={'project_id':pid,'message':'What is the total passenger count?'})
    assert response.status_code==200,response.text
    assert int(float(response.json()['calculated_evidence']))==total
    api.active_sessions.clear()
    session=client.get(f'/api/projects/{pid}/session',headers=accounts[0]).json()
    assert len(session['messages'])==2
    assert str(total) in session['messages'][-1]['content']
    unsuitable=client.post('/api/automl/start',headers=accounts[0],json={
        'project_id':pid,'target_column':'#Passengers','task_type':'regression','run_tuning':False})
    assert unsuitable.status_code==400 and 'No usable features' in unsuitable.json()['detail']
