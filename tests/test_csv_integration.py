import importlib
import io
import json
from pathlib import Path
import uuid
import pandas as pd
import pytest
from backend.tools.python_tool import execute_python

DATA=Path(__file__).with_name('data')


@pytest.mark.parametrize('name,column,expected_key',[
    ('retail_orders.csv','sales','retail_sales_total'),
    ('retail_orders.csv','profit','retail_profit_total'),
    ('saas_churn.csv','churned','churn_count'),
])
def test_csv_evidence(name,column,expected_key):
    expected=json.loads((DATA/'expected.json').read_text())
    df=pd.read_csv(DATA/name)
    result=execute_python(f"result=round(df['{column}'].sum(),2)",df)
    assert result['success'],result
    assert result['result']==expected[expected_key]


@pytest.mark.parametrize('name',['customers-1000.csv','dataset.csv','kc_house_data.csv','noisy_regression_2000x13.csv','tested.csv'])
def test_existing_real_csv_upload(client,accounts,name):
    source = Path('test') / name
    if not source.is_file():
        pytest.skip('Optional local CSV download is absent; synthetic integration fixtures remain available.')
    df=pd.read_csv(source,nrows=200)
    response=client.post('/api/upload',headers=accounts[0],files={'file':(name,df.to_csv(index=False).encode(),'text/csv')})
    assert response.status_code==200,response.text
    payload=response.json()
    assert payload['shape']==dict(rows=len(df),columns=len(df.columns))
    assert client.get('/api/profile/'+payload['project_id'],headers=accounts[0]).status_code==200


def test_actual_pipeline_trend_charts_and_report(monkeypatch,tmp_path):
    import backend.graph.workflow as workflow
    from backend.services.supabase_service import DatabaseService
    database=DatabaseService(tmp_path/'pipeline.db')
    loader=importlib.import_module('backend.agents.csv_loader')
    report=importlib.import_module('backend.agents.report_agent')
    monkeypatch.setattr(loader,'db_service',database)
    monkeypatch.setattr(report,'db_service',database)
    monkeypatch.setattr(report,'REPORTS_DIR',tmp_path)
    monkeypatch.setattr(loader.r2_service,'upload_dataframe_csv',lambda *a,**k:'local-dataset')
    monkeypatch.setattr(report.r2_service,'upload_file',lambda *a,**k:'local-report')
    for name in ('supervisor','schema_agent','quality_agent','kpi_agent','eda_agent','diagnostic_agent','hypothesis_agent','trend_agent','report_agent'):
        module=importlib.import_module('backend.agents.'+name)
        def offline(*args,**kwargs):
            return 'Offline test narrative based on calculated evidence.'
        monkeypatch.setattr(module,'invoke_llm',offline)
    df=pd.read_csv(DATA/'retail_orders.csv')
    pid=str(uuid.uuid4())
    result=workflow.run_analyst_pipeline(dict(project_id=pid,owner_id='fixture-owner',dataset_name='retail',df_raw=df,execution_steps=[],errors=[]))
    assert not result['errors'],result['errors']
    assert pd.api.types.is_datetime64_any_dtype(result['df_clean']['order_date'])
    assert result['quality_audit'] and result['trend_results']['available']
    assert any('trend' in str(chart).lower() for chart in result['charts'])
    assert Path(result['report_pdf_path']).read_bytes().startswith(b'%PDF')
    assert Path(result['report_pptx_path']).suffix=='.pptx'
    assert Path(result['report_pptx_path']).read_bytes().startswith(b'PK')
    assert database.get_project(pid)['owner_id']=='fixture-owner'
