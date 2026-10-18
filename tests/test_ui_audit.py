"""Regressions reproduced from the interactive UI audit."""
import pandas as pd
import pytest
from backend.agents.kpi_agent import _compute_core_kpi
from backend.tools.python_tool import execute_python
from tests.test_security import upload


def test_numeric_duration_cannot_create_calendar_trends_or_charts(monkeypatch):
    from backend.agents import schema_agent
    from backend.agents.trend_agent import _find_date_column, _compute_time_series, trend_agent_node
    from backend.agents.visualization_agent import visualization_agent_node
    frame = pd.DataFrame({'experience_years':[1,2,3], 'income':[10.,20.,30.]})
    monkeypatch.setattr(schema_agent, 'invoke_llm', lambda **kw: '{"primary_date_column":"experience_years"}')
    state = schema_agent.schema_agent_node({'df_raw':frame})
    assert state['schema_metadata']['primary_date_column'] is None
    assert _find_date_column(frame, 'experience_years') is None
    assert 'error' in _compute_time_series(frame, 'experience_years', 'income')
    assert not trend_agent_node(state)['trend_results']['available']
    state['schema_metadata']['primary_date_column'] = 'experience_years'  # legacy result
    charts = visualization_agent_node(state)['charts']
    assert not any(c['type'] in {'time_series','trend_decomposition','mom_growth'} for c in charts)


def test_monthly_trends_require_observed_periods_and_use_mean_for_scores():
    from backend.agents.trend_agent import _compute_time_series
    frame = pd.DataFrame({'date':['2025-01-01','2025-01-20','2025-02-01'],
                          'performance_score':[10.,30.,40.], 'sales':[10.,30.,40.]})
    assert 'error' in _compute_time_series(frame.iloc[:2], 'date', 'sales')
    result = _compute_time_series(frame, 'date', 'performance_score')
    assert result['aggregation'] == 'mean'
    assert result['monthly_data'][0]['value'] == 20
    assert result['overall_total'] is None
    assert _compute_time_series(frame, 'date', 'sales')['monthly_data'][0]['value'] == 40


def test_statistical_narrative_rejects_unestablished_business_importance(monkeypatch):
    from backend.agents import hypothesis_agent
    frame = pd.DataFrame({'group':['A']*20+['B']*20, 'sales':list(range(20))+list(range(20))})
    monkeypatch.setattr(hypothesis_agent, 'invoke_llm', lambda **kw: 'The effect is too small to impact business outcomes.')
    result = hypothesis_agent.hypothesis_agent_node({'df_raw':frame,'schema_metadata':{
        'recommended_measures':['sales'],'recommended_dimensions':['group']}})['hypothesis_results']
    assert result['tests_count'] > 0
    assert 'too small to impact' not in result['executive_summary']
    assert 'Practical importance requires a domain threshold' in result['executive_summary']


def test_kpi_commentary_does_not_interpret_a_model_target_as_a_business_goal(monkeypatch):
    from backend.agents import kpi_agent
    monkeypatch.setattr(kpi_agent,'invoke_llm',lambda **kw: 'The organization aims to raise salaries to the target.')
    result = kpi_agent.kpi_agent_node({'df_raw':pd.DataFrame({'income':[10.,20.,30.],'target_salary':[20.,30.,40.]}),
        'schema_metadata':{'recommended_measures':['income','target_salary']}})['kpi_results']
    assert 'organization aims' not in result['kpi_interpretation']
    assert 'mean 20.00' in result['kpi_interpretation']
    assert 'organizational goals' in result['kpi_interpretation']


def test_quality_covers_later_numeric_columns_and_keeps_cell_counts_distinct(monkeypatch):
    from backend.agents import quality_agent
    frame = pd.DataFrame({f'metric_{i}':list(range(20))+[1000.] for i in range(10)})
    frame.loc[0,'metric_9'] = None
    monkeypatch.setattr(quality_agent,'invoke_llm',lambda **kw:'One missing cell means one missing row.')
    result=quality_agent.quality_agent_node({'df_raw':frame})['quality_audit']
    assert set(result['outlier_analysis']) == set(frame.columns)
    assert '**Missing values:** 1 cells' in result['quality_briefing']
    assert 'unique affected rows' in result['quality_briefing']
    assert 'means one missing row' not in result['quality_briefing']


@pytest.mark.parametrize('column', ['attendance_rate', 'performance_score', 'monthly_income', 'target_salary', 'price', 'temperature'])
def test_non_additive_metrics_are_not_summed_or_assigned_currency(column):
    row = _compute_core_kpi(pd.DataFrame({column: [10., 20., 30.]}), column, None)
    assert row['aggregation'] == 'mean'
    assert row['value'] == 20
    assert row['total'] is None
    assert row['unit'] == 'unspecified'
    assert '$' not in row['formatted_value']


def test_additive_metrics_retain_sum_without_inventing_currency():
    row = _compute_core_kpi(pd.DataFrame({'sales':[10.,20.,30.]}), 'sales', None)
    assert row['total'] == row['value'] == 60
    assert row['aggregation'] == 'sum'
    assert '$' not in row['formatted_total']


def test_duplicate_and_correlation_expression_runs_inside_limited_worker():
    df = pd.DataFrame({'x':[1,2,3,3], 'y':[2,4,6,6]})
    code = "corr = df.corr(numeric_only=True).abs()\npairs = corr.where((corr > 0.8) & (corr < 1)).stack().head(10)\nresult = {'duplicates': df.duplicated().sum(), 'correlation': corr.to_dict(), 'pairs': pairs.to_dict()}"
    result = execute_python(code, df)
    # The UI's previous snippet also used where(), a safe dataframe operation.
    assert result['success'], result
    assert result['result']['duplicates'] == 1
    assert result['result']['correlation']['x']['y'] == pytest.approx(1)


def test_chat_failure_is_never_calculated_evidence_or_speculative_answer(client, accounts, monkeypatch):
    import backend.main as api
    pid = upload(client, accounts[0])
    calls=[]
    def llm(prompt, **kwargs):
        calls.append(prompt)
        return "result = open('secret').read()"
    monkeypatch.setattr(api, 'invoke_llm', llm)
    response = client.post('/api/chat', headers=accounts[0], json={'project_id':pid,'message':'Count duplicates'})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['execution_status'] == 'failed'
    assert data['calculated_evidence'] is None
    assert 'PolicyError' in data['calculation_error']
    assert 'couldn’t verify' in data['reply']
    assert len(calls) == 2  # planning + bounded repair; no speculative synthesis
    restored=client.get(f'/api/projects/{pid}/session', headers=accounts[0]).json()['messages'][-1]
    assert restored['execution_status'] == 'failed' and restored['evidence'] is None


def test_chat_repairs_once_and_synthesizes_only_successful_evidence(client, accounts, monkeypatch):
    import backend.main as api
    pid=upload(client, accounts[0])
    outputs=iter(["result=df.query('sales > 0')", "result=df.duplicated().sum()", '**Duplicate rows:** 0'])
    calls=[]
    def llm(prompt, **kwargs):
        calls.append(prompt)
        return next(outputs)
    monkeypatch.setattr(api,'invoke_llm',llm)
    response=client.post('/api/chat', headers=accounts[0], json={'project_id':pid,'message':'Count duplicates'})
    data=response.json()
    assert data['execution_status']=='succeeded',data
    assert data['calculated_evidence']=='0'
    assert data['calculation_error'] is None
    assert 'execution_status: succeeded' in calls[-1]


def test_narrative_checks_reject_invented_units_trends_and_causality():
    from backend.services.narrative_checks import unsupported_claims
    assert unsupported_claims('Average income is $500. The trend is positive.')
    assert unsupported_claims('Payroll appears stable.')
    assert unsupported_claims('The root cause is tenure. This proves that age causes salary.')
    assert not unsupported_claims('Average score is 70. Causality is not established.')


def test_report_replaces_unsupported_model_claims_with_computed_facts(monkeypatch, tmp_path):
    import backend.agents.report_agent as report
    monkeypatch.setattr(report, 'REPORTS_DIR', tmp_path)
    monkeypatch.setattr(report, 'invoke_llm', lambda *a,**k: 'SECTION 1: EXECUTIVE BRIEFING\nSalary is $500 and appears stable.\nSECTION 2: PRIORITIZED ACTION PLAN\nGuaranteed high-ROI savings.')
    monkeypatch.setattr(report.r2_service, 'upload_file', lambda *a,**k:'offline')
    state = {'project_id':'audit-report', 'dataset_name':'audit', 'health_score':80,
             'kpi_results':{'kpi_metrics':[_compute_core_kpi(pd.DataFrame({'income':[10.,20.,30.]}),'income',None)]}}
    result = report.report_agent_node(state)
    assert '$500' not in result['report_summary']
    assert 'mean 20.00' in result['report_summary']
    assert 'No reliable time trend' in result['report_summary']
    assert 'Aggregation / Value' in result['report_markdown']
    assert not result.get('errors'), result.get('errors')
