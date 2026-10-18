"""Regression cases found by exercising real Kaggle files in the web UI."""
import numpy as np
import pandas as pd

from backend.services.profiler import _compute_correlation_matrix, numeric_analysis_columns


def test_ordered_row_ids_do_not_create_spurious_correlations():
    frame = pd.DataFrame({'Id':range(150), 'sepal_width':np.arange(150)*2.,
                          'petal_width':np.arange(150)*3.})
    result = _compute_correlation_matrix(frame)
    assert result['columns'] == ['sepal_width','petal_width']
    assert len(result['high_correlations']) == 1
    assert all('Id' not in (pair['col1'],pair['col2']) for pair in result['high_correlations'])


def test_empty_and_constant_numeric_columns_do_not_create_blank_heatmap_axes():
    frame=pd.DataFrame({'empty':[np.nan]*100,'constant':[1.]*100,
                        'measurement':np.arange(100,dtype=float)})
    assert numeric_analysis_columns(frame) == ['measurement']


def test_schema_and_eda_cannot_promote_row_id_to_measure(monkeypatch):
    from backend.agents import schema_agent, eda_agent
    frame = pd.DataFrame({'Row ID':range(100), 'measurement':np.arange(100)*2.})
    monkeypatch.setattr(schema_agent,'invoke_llm',lambda **kw:'{"columns":{},"recommended_measures":["Row ID","measurement"]}')
    monkeypatch.setattr(eda_agent,'invoke_llm',lambda **kw:'Descriptive observations only.')
    state=schema_agent.schema_agent_node({'df_raw':frame})
    assert state['schema_metadata']['recommended_measures'] == ['measurement']
    assert state['schema_metadata']['columns']['Row ID']['semantic_type'] == 'Identifier'
    assert numeric_analysis_columns(frame) == ['measurement']
    result=eda_agent.eda_agent_node(state)['eda_results']
    assert 'Row ID' not in result['column_profiles']
    assert not result['correlation_pairs']


def test_dashboard_and_agent_health_score_share_one_definition():
    from backend.agents.quality_agent import quality_agent_node
    from backend.services.profiler import profile_dataset
    frame = pd.DataFrame({'age':[None]*20+list(range(80)), 'category':['a']*80+['b']*20})
    profile = profile_dataset(frame)
    result = quality_agent_node({'df_raw':frame})
    assert result['health_score'] == profile['health']['score']
    assert result['quality_audit']['health_status'] == profile['health']['status']


def test_report_headlines_cannot_invent_units_tests_or_missing_dates():
    from backend.services.evidence_briefing import build_evidence_briefing
    from backend.services.metric_semantics import metric_aggregation
    state={'df_raw':pd.DataFrame({'#Passengers':[1,2,3]}),'health_score':100,
           'trend_results':{'available':True},'quality_audit':{'duplicate_rows':0},
           'eda_results':{'column_profiles':{'#Passengers':{'mean':2.}}}}
    summary,actions=build_evidence_briefing(state)
    assert '**Records:** 3' in summary and 'mean 2' in summary
    assert 'Time-series results are available' in summary
    assert 'No reliable time trend' not in summary
    assert 'p=' not in summary and '$' not in summary and 'causal modeling' not in actions
    assert metric_aggregation('#Passengers') == 'sum'
    assert metric_aggregation('#age') == 'mean'


def test_duplicate_measure_dimension_does_not_abort_all_charts_or_test_itself(monkeypatch):
    from backend.agents import visualization_agent, hypothesis_agent
    from backend.tools.charts import create_bar_comparison
    frame=pd.DataFrame({'quality':[3,4,5,6,7]*20,'alcohol':np.arange(100,dtype=float)})
    state={'df_raw':frame,'schema_metadata':{'recommended_measures':['quality'],
           'recommended_dimensions':['quality']},'diagnostic_results':{'target_metric':'quality'}}
    monkeypatch.setattr(hypothesis_agent,'invoke_llm',lambda **kw:'Exploratory only.')
    result=visualization_agent.visualization_agent_node(state)
    assert not result.get('errors') and len(result['charts']) >= 2
    assert create_bar_comparison(frame,'quality','quality') == {}
    tested=hypothesis_agent.hypothesis_agent_node(state)['hypothesis_results']
    assert not tested['tests_conducted']


def test_text_only_frequency_charts_keep_original_dataset_unchanged():
    from backend.agents.visualization_agent import visualization_agent_node
    frame=pd.DataFrame({'label':['ham','spam']*20,'message':['example text']*40})
    result=visualization_agent_node({'df_raw':frame,
        'schema_metadata':{'recommended_dimensions':['label']},
        'diagnostic_results':{'target_metric':'record_count'}})
    assert not result.get('errors') and result['charts']
    assert 'record_count' not in frame.columns


def test_catalog_number_and_sparse_export_artifacts_are_not_targets():
    from backend.services.profiler import profile_dataset
    from backend.services.automl_engine import is_identifier_column
    frame=pd.DataFrame({'#':range(100),'Unnamed: 3':['a','b']*50,
                        'Legendary':[True,False]*50,'HP':np.arange(100,dtype=float)})
    profile=profile_dataset(frame)
    assert is_identifier_column('#') and not is_identifier_column('#Passengers')
    assert '#' not in numeric_analysis_columns(frame)
    assert not {'#','Unnamed: 3'} & {t['column'] for t in profile['potential_targets']}


def test_postal_codes_are_not_numeric_measurements_or_model_features():
    from backend.services.automl_engine import is_identifier_column
    frame=pd.DataFrame({'Postal Code':[10001,10002]*50,'Sales':np.arange(100,dtype=float)})
    assert numeric_analysis_columns(frame) == ['Sales']
    assert is_identifier_column('Postal Code')


def test_basic_dataset_counts_do_not_depend_on_llm_requesting_code(client, accounts, monkeypatch):
    import backend.main as api
    uploaded=client.post('/api/profile',headers=accounts[0],files={
        'file':('counts.csv',b'value,label\n1,a\n1,a\n,b\n')})
    pid=uploaded.json()['project_id']
    def no_provider(*args,**kwargs):
        raise AssertionError('Basic counts must not call a provider')
    monkeypatch.setattr(api,'invoke_llm',no_provider)
    response=client.post('/api/chat',headers=accounts[0],json={'project_id':pid,
        'message':'Calculate row count, column count, duplicate count and missing cells.'})
    assert response.status_code == 200, response.text
    result=response.json()
    assert result['execution_status'] == 'succeeded'
    assert '| Total rows | 3 |' in result['reply']
    assert '| Missing cells | 1 |' in result['reply']
    assert '| Duplicate rows | 1 |' in result['reply']


def test_skipped_non_additive_decomposition_does_not_claim_missing_dates(monkeypatch):
    from backend.agents import diagnostic_agent
    frame=pd.DataFrame({'Date':pd.date_range('2020-01-01',periods=100),
        'temperature':np.arange(100,dtype=float),'site':['a','b']*50})
    monkeypatch.setattr(diagnostic_agent,'invoke_llm',lambda **kw:'Dataset has no date column.')
    result=diagnostic_agent.diagnostic_agent_node({'df_raw':frame,'schema_metadata':{
        'primary_date_column':'Date','recommended_measures':['temperature'],
        'recommended_dimensions':['site']}})
    narrative=result['diagnostic_results']['diagnostic_narrative']
    assert 'no date column' not in narrative.lower()
    assert 'requires an additive measure' in narrative
