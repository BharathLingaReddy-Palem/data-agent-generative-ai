"""Render the Streamlit pages with a completed analysis and a real login."""
import importlib
from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_all_streamlit_pages_render_completed_analysis(client,accounts,monkeypatch,tmp_path):
    import backend.main as api
    report=importlib.import_module('backend.agents.report_agent')
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    monkeypatch.setattr(report,'REPORTS_DIR',tmp_path)
    for name in ('supervisor','schema_agent','quality_agent','kpi_agent','eda_agent','diagnostic_agent','hypothesis_agent','trend_agent','report_agent'):
        monkeypatch.setattr(importlib.import_module('backend.agents.'+name),'invoke_llm',lambda **kwargs:'Offline deterministic narrative.')
    path=Path(__file__).parent/'data'/'retail_orders.csv'
    uploaded=client.post('/api/profile',headers=accounts[0],files={'file':(path.name,path.read_bytes())})
    pid=uploaded.json()['project_id']
    response=client.post('/api/analyze',headers=accounts[0],json={'project_id':pid})
    assert response.status_code==200,response.text
    session=api.active_sessions[pid]
    token=accounts[0]['Authorization'].split()[1]
    root=Path(__file__).resolve().parents[1]/'frontend'
    pages=[root/'app.py',*sorted((root/'pages').glob('*.py'))]
    failures=[]
    for page in pages:
        app=AppTest.from_file(str(page),default_timeout=30)
        for key,value in dict(auth_token=token, project_id=pid, dataset_name='Retail fixture',
                df=session['df'], analysis=session['analysis']).items():
            app.session_state[key]=value
        app.run()
        failures.extend((page.name,exception.message) for exception in app.exception)
    assert not failures,failures
