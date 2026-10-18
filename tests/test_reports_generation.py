import io
from pathlib import Path
import zipfile
import pytest
from tests.test_security import upload


@pytest.mark.parametrize('failure',[None,'pdf_error','pdf_fallback','pptx_fallback'])
def test_real_report_generation_and_api_downloads(client,accounts,tmp_path,monkeypatch,failure):
    import backend.main as api
    import backend.agents.report_agent as report
    monkeypatch.setattr(api,'REPORTS_DIR',tmp_path)
    monkeypatch.setattr(report,'REPORTS_DIR',tmp_path)
    monkeypatch.setattr(report,'invoke_llm',lambda *a,**k:'SECTION 1: EXECUTIVE BRIEFING\nSales increased.\nSECTION 2: PRIORITIZED ACTION PLAN\nReview regional sales.')
    monkeypatch.setattr(report.r2_service,'upload_file',lambda *a,**k:'offline-report')
    if failure=='pdf_error':
        def failed_pdf(**kwargs):raise RuntimeError('PDF writer failed')
        monkeypatch.setattr(report,'generate_analyst_pdf_report',failed_pdf)
    elif failure in ('pdf_fallback','pptx_fallback'):
        def fallback(**kwargs):
            path=Path(kwargs['output_path']).with_suffix('.txt');path.write_text('fallback text')
            return str(path)
        monkeypatch.setattr(report,'generate_analyst_pdf_report' if failure=='pdf_fallback' else 'generate_pptx_report',fallback)
    pid=upload(client,accounts[0])
    monkeypatch.setattr(api,'run_analyst_pipeline',report.report_agent_node)
    response=client.post('/api/analyze',headers=accounts[0],json={'project_id':pid})
    assert response.status_code==200,response.text
    result=response.json()
    for format in ('pdf','pptx'):
        failed=(format=='pdf' and failure in ('pdf_error','pdf_fallback')) or (format=='pptx' and failure=='pptx_fallback')
        artifact=result['report_artifacts'][format]
        assert artifact['available'] is not failed
        url=f'/api/reports/{pid}/{format}/download'
        downloaded=client.get(url,headers=accounts[0])
        if failed:
            assert downloaded.status_code==404
            assert artifact['download_url'] is None and result['errors']
        else:
            assert downloaded.status_code==200
            assert artifact['download_url']==url
            if format=='pdf':assert downloaded.content.startswith(b'%PDF')
            else:
                with zipfile.ZipFile(io.BytesIO(downloaded.content)) as deck:
                    assert 'ppt/presentation.xml' in deck.namelist()
    assert not list((tmp_path/pid).glob('.*-*'))
