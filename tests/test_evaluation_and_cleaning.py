import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import Ridge
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

import backend.services.automl_engine as engine
from backend.services.cleaner import clean_dataset, clean_column_names, strip_column_names
from backend.services.dataset_views import active_dataframe, model_dataframe
from backend.tools.benchmarks import evaluate_metric_vs_benchmark, run_full_benchmark_audit
from backend.tools.stats_tools import pareto_analysis


@pytest.fixture
def fast_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, 'ARTIFACTS_DIR', tmp_path)
    monkeypatch.setattr(engine, 'get_candidate_models', lambda task: {'Ridge Regression': Ridge()})
    monkeypatch.setattr(engine, 'compute_feature_importance', lambda *a, **k: {'available': True})
    x = np.linspace(-10, 10, 100)
    return pd.DataFrame({'customer_id': np.arange(100), 'width': x, 'group': np.tile(['a', 'b'], 50), 'target': x*4 + np.sin(x)})


def test_preprocessing_fits_only_training_folds_and_saved_training_partition(fast_engine, monkeypatch):
    df = fast_engine
    df.loc[10, 'width'] = np.nan
    fits = []
    fit = engine.FoldPreprocessor.fit
    def observe(self, X, y=None):
        fits.append(set(X.index))
        return fit(self, X, y)
    monkeypatch.setattr(engine.FoldPreprocessor, 'fit', observe)
    result = engine.run_automl(df, 'target', 'folds', run_tuning=False, clip_outliers=True)
    train, test = train_test_split(df, test_size=0.2, random_state=42)
    assert len(fits) == result['cv_folds'] + 1
    assert all(indices <= set(train.index) and not indices & set(test.index) for indices in fits)
    assert any(len(indices) < len(train) for indices in fits)
    bundle = joblib.load(result['saved_model_path'])
    prep = bundle['pipeline'].named_steps['preprocessor']
    assert prep.numeric_columns_ == ['width']
    assert 'customer_id' in result['excluded_features']
    assert 'customer_id' not in bundle['feature_names']
    assert result['evaluation']['test_used_for_selection'] is False
    predictions = engine.predict_with_saved_model(result['saved_model_path'], {'width': 2, 'group': 'unseen'})
    assert len(predictions['predictions']) == 1


def test_only_validation_winner_reaches_holdout(fast_engine, monkeypatch):
    monkeypatch.setattr(engine, 'get_candidate_models', lambda task: {'first': Ridge(alpha=1), 'second': Ridge(alpha=2)})
    validate = engine._validate_model
    def rank(name, *args):
        entry = validate(name, *args)
        entry['cv_score_mean'] = 0.8 if name == 'second' else 0.5
        return entry
    monkeypatch.setattr(engine, '_validate_model', rank)
    seen = []
    holdout = engine._holdout_metrics
    def record(model, *args):
        seen.append(model.named_steps['model'].alpha)
        return holdout(model, *args)
    monkeypatch.setattr(engine, '_holdout_metrics', record)
    result = engine.run_automl(fast_engine, 'target', 'selection', run_tuning=False)
    assert seen == [2]
    assert result['best_model']['model_name'] == 'second'
    assert 'primary_metric' not in result['leaderboard'][1]


def test_macro_and_weighted_f1_are_distinct_and_correct(fast_engine, monkeypatch):
    monkeypatch.setattr(engine, 'get_candidate_models', lambda task: {'majority': DummyClassifier(strategy='most_frequent')})
    df = fast_engine.copy()
    df['target'] = [0]*90 + [1]*10
    result = engine.run_automl(df, 'target', 'f1', run_tuning=False)
    bundle = joblib.load(result['saved_model_path'])
    _, X_test, _, y_test = train_test_split(df.drop(columns='target'), df.target, test_size=0.2, random_state=42, stratify=df.target)
    predicted = bundle['pipeline'].predict(X_test)
    best = result['best_model']
    assert best['f1_macro'] == best['f1_score'] == best['primary_metric'] == round(f1_score(y_test, predicted, average='macro'), 4)
    assert best['f1_weighted'] == round(f1_score(y_test, predicted, average='weighted'), 4)
    assert best['f1_macro'] != best['f1_weighted']
    assert best['primary_metric_name'] == result['cv_metric'] == 'f1_macro'


@pytest.mark.parametrize('values,expected', [([70, 20, 10], 2), ([80, 15, 5], 1), ([90, 5, 5], 1), ([50, 30, 20], 2), ([1]*10, 8)])
def test_pareto_includes_threshold_crossing(values, expected):
    result = pareto_analysis(pd.DataFrame({'cat': list(map(str, range(len(values)))), 'amount': values}), 'cat', 'amount')
    assert result['categories_driving_80pct'] == expected


def test_pareto_rejects_negative_contributions():
    assert 'error' in pareto_analysis(pd.DataFrame({'cat': ['a', 'b'], 'amount': [100, -10]}), 'cat', 'amount')


@pytest.mark.parametrize('key,value,unit,period', [
    ('profit', 10000, '%', 'reporting_period'), ('profit_margin_pct', 20, '$', 'reporting_period'),
    ('profit_margin_pct', .2, 'ratio', 'reporting_period'), ('profit_margin_pct', 20, None, None),
    ('profit_margin_pct', float('inf'), '%', 'reporting_period'),
    ('churn_rate_monthly_pct', 3, '%/mo', 'annual'),
])
def test_benchmarks_reject_ambiguous_or_incompatible_metrics(key, value, unit, period):
    domain = 'SaaS / Subscription' if key.startswith('churn') else 'E-Commerce / Retail'
    assert evaluate_metric_vs_benchmark(key, value, domain, unit=unit, period=period) is None


def test_benchmarks_accept_explicit_zero_and_report_skips():
    result = run_full_benchmark_audit([
        {'column': 'profit', 'mean': 10000, 'total': 20000},
        {'metric_key': 'profit_margin_pct', 'value': 0, 'unit': '%', 'period': 'reporting_period'},
    ], 'E-Commerce / Retail')
    assert result['metrics_benchmarked'] == 1 and len(result['skipped_metrics']) == 1
    assert result['benchmark_verdicts'][0]['actual_value'] == 0
    assert result['benchmark_verdicts'][0]['period'] == 'reporting_period'


def test_column_collisions_and_suffixes_are_deterministic():
    df = pd.DataFrame([[1]*6], columns=['A B', 'a-b', 'a_b_2', '!!!', 'col_3', ''])
    cleaned, mapping = clean_column_names(df)
    assert cleaned.columns.is_unique
    assert mapping['a-b'] == 'a_b_3' and mapping['a_b_2'] == 'a_b_2'
    pd.testing.assert_frame_equal(clean_column_names(df)[0], cleaned)
    with pytest.raises(ValueError, match='Duplicate'):
        clean_column_names(pd.DataFrame([[1, 2]], columns=['a', 'a']))


def test_whitespace_header_collisions_at_ingestion(client, accounts):
    response = client.post('/api/upload', headers=accounts[0], files={
        'file': ('headers.csv', ' Amount ,Amount,Amount_2\n1,2,3\n4,5,6\n', 'text/csv')})
    assert response.status_code == 200, response.text
    assert response.json()['columns'] == ['Amount', 'Amount_3', 'Amount_2']
    assert strip_column_names(pd.DataFrame([[1, 2]], columns=['a', ' a '])).columns.is_unique


def test_numeric_categorical_input_keeps_training_encoding(fast_engine):
    df = fast_engine.assign(group=np.tile(['0', '1'], 50))
    result = engine.run_automl(df, 'target', 'category-inference', run_tuning=False)
    text = engine.predict_with_saved_model(result['saved_model_path'], {'width': '2', 'group': '0'})
    numeric = engine.predict_with_saved_model(result['saved_model_path'], {'width': 2, 'group': 0})
    assert text == numeric


def test_simulation_rejects_invalid_numbers_instead_of_silently_imputing(fast_engine):
    result=engine.run_automl(fast_engine,'target','simulation-validation',run_tuning=False)
    path=result['saved_model_path']
    for invalid in ('not-a-number','nan','inf','-inf'):
        with pytest.raises(ValueError,match='width: 1 invalid numeric'):
            engine.predict_with_saved_model(path,{'width':invalid,'group':'a'})
    blank=engine.predict_with_saved_model(path,{'width':'','group':'a'})
    absent=engine.predict_with_saved_model(path,{'group':'a'})
    assert blank==absent and len(blank['predictions'])==1
    assert any('Missing feature' in warning for warning in blank['warnings'])
    with pytest.raises(ValueError,match='1–10,000'):
        engine.predict_with_saved_model(path,[])


@pytest.mark.parametrize('target', [[0.]*19 + [100000., np.nan], [' Yes ']*19 + ['No', None]])
def test_cleaner_never_imputes_clips_or_trims_target(target):
    df = pd.DataFrame({'Target Value': target, 'measure': list(range(19)) + [10000., np.nan]})
    cleaned, audit = clean_dataset(df, target_column='Target Value', remove_duplicates=False)
    pd.testing.assert_series_equal(cleaned.target_value, df['Target Value'], check_names=False)
    assert cleaned.measure.notna().all() and cleaned.measure.max() < 10000
    assert not any(row['column'] == 'target_value' for row in audit['missing_imputations'] + audit['outliers_clipped'])


def test_unknown_target_defers_learned_cleaning_and_model_view_replays_source():
    df = pd.DataFrame({'Feature Value': np.r_[np.arange(30.), 100000., np.nan], 'Target': np.r_[np.arange(31.), np.nan]})
    structural, audit = clean_dataset(df, remove_duplicates=False)
    assert structural.feature_value.max() == 100000 and structural.target.isna().sum() == 1
    assert audit['notice']
    options = dict(handle_missing=True, handle_outliers=True, remove_duplicates=False, standardize_names=True)
    cleaned, _ = clean_dataset(df, target_column='Target', **options)
    session = dict(df=df, df_cleaned=cleaned, cleaning_options=options)
    assert active_dataframe(session) is cleaned
    model_df, target, clip = model_dataframe(session, 'target')
    assert target == 'target' and clip
    assert model_df.feature_value.max() == 100000 and model_df.feature_value.isna().sum() == 1
    pd.testing.assert_series_equal(model_df.target, df.Target, check_names=False)


@pytest.mark.parametrize('mutation,requested,task,message', [
    (lambda d: d, 'typo', None, 'does not exist'),
    (lambda d: d.iloc[:5], 'target', None, 'at least 20'),
    (lambda d: d.assign(target=1), 'target', None, 'distinct'),
    (lambda d: d.assign(target=['a']*99+['b']), 'target', 'classification', 'at least 5'),
    (lambda d: d.assign(target=['label'+str(i) for i in range(100)]), 'target', None, 'at most 20'),
    (lambda d: d.assign(target=np.inf), 'target', 'regression', 'distinct'),
    (lambda d: d.assign(target=np.r_[np.arange(99.), np.inf]), 'target', 'regression', 'finite numeric'),
    (lambda d: d[['customer_id', 'target']], 'target', None, 'No usable features'),
    (lambda d: d, 'customer_id', None, 'identifier'),
])
def test_unsuitable_inputs_fail_with_actionable_errors(fast_engine, mutation, requested, task, message):
    with pytest.raises(ValueError, match=message):
        engine.run_automl(mutation(fast_engine), requested, 'invalid', False, task_type=task)


def test_explicit_task_override_does_not_change_labels(fast_engine):
    df = fast_engine.copy()
    df['target'] = np.arange(100) % 10
    assert engine.detect_target_and_task(df, 'target', 'regression') == ('target', 'regression')
    assert engine.detect_target_and_task(df, 'target', 'classification') == ('target', 'classification')


def test_api_validation_happens_before_job_submission(client, accounts, monkeypatch):
    import backend.main as api
    csv = pd.DataFrame({'customer_id': range(100), 'feature': np.arange(100)/3, 'target': np.arange(100)/7}).to_csv(index=False)
    pid = client.post('/api/upload', headers=accounts[0], files={'file': ('test.csv', csv, 'text/csv')}).json()['project_id']
    monkeypatch.setattr(api.job_queue, 'submit', lambda **k: pytest.fail('Invalid inputs must not enqueue jobs'))
    response = client.post('/api/automl/start', headers=accounts[0], json=dict(project_id=pid, target_column='typo'))
    assert response.status_code == 400 and 'does not exist' in response.json()['detail']


def test_api_views_use_cleaned_data_and_automl_preserves_source_labels(client, accounts, monkeypatch):
    import backend.main as api
    raw = pd.DataFrame({'Feature Value': np.r_[np.arange(30.), 100000., np.nan], 'Target Value': np.r_[np.arange(31.), np.nan]})
    pid = client.post('/api/upload', headers=accounts[0], files={'file': ('test.csv', raw.to_csv(index=False), 'text/csv')}).json()['project_id']
    api.active_sessions[pid]['analysis'] = {'old': True}
    cleaned = client.post('/api/clean', headers=accounts[0], json=dict(project_id=pid, target_column='Target Value', remove_duplicates=False))
    assert cleaned.status_code == 200, cleaned.text
    session = api.active_sessions[pid]
    assert 'analysis' not in session and session['df_cleaned'].target_value.isna().sum() == 1
    assert cleaned.json()['profile'] == client.get('/api/profile/'+pid, headers=accounts[0]).json()
    seen = []
    def analyze(state):
        seen.append(state['df_raw']); return dict(state)
    monkeypatch.setattr(api, 'run_analyst_pipeline', analyze)
    assert client.post('/api/analyze', headers=accounts[0], json={'project_id': pid}).status_code == 200
    pd.testing.assert_frame_equal(seen[0], session['df_cleaned'])
    answers = iter(["result = df['feature_value'].max()", 'Checked.'])
    monkeypatch.setattr(api, 'invoke_llm', lambda *a, **k: next(answers))
    response = client.post('/api/chat', headers=accounts[0], json=dict(project_id=pid, message='Maximum?'))
    assert response.status_code == 200 and float(response.json()['calculated_evidence']) == session['df_cleaned'].feature_value.max()
    monkeypatch.setattr(api.job_queue, 'submit', lambda **k: 'validated-job')
    response = client.post('/api/automl/start', headers=accounts[0], json=dict(project_id=pid, target_column='target_value'))
    assert response.status_code == 200, response.text
    model_df, target, clip = model_dataframe(session, 'target_value')
    assert model_df.feature_value.max() == 100000 and model_df.target_value.isna().sum() == 1
    assert target == 'target_value' and clip


def test_changing_target_restores_original_labels(client, accounts, monkeypatch):
    import backend.main as api
    df = pd.DataFrame({'first': np.arange(40.), 'second': np.r_[np.arange(38.), 100000., np.nan], 'feature': np.sin(np.arange(40.))})
    pid = client.post('/api/upload', headers=accounts[0], files={'file': ('labels.csv', df.to_csv(index=False), 'text/csv')}).json()['project_id']
    assert client.post('/api/clean', headers=accounts[0], json=dict(project_id=pid, target_column='first')).status_code == 200
    assert api.active_sessions[pid]['df_cleaned'].second.notna().all()
    monkeypatch.setattr(api.job_queue, 'submit', lambda **k: 'validated-job')
    response = client.post('/api/automl/start', headers=accounts[0], json=dict(project_id=pid, target_column='second'))
    assert response.status_code == 200, response.text
    pd.testing.assert_series_equal(api.active_sessions[pid]['df_cleaned'].second, df.second)


def test_cleaned_target_names_resolve_unambiguously_when_names_collide():
    raw = pd.DataFrame({'A B': np.arange(30.), 'a_b': np.arange(30.)*2, 'x': np.sin(np.arange(30.))})
    options = dict(handle_missing=True, handle_outliers=True, remove_duplicates=False, standardize_names=True)
    session = dict(df=raw, cleaning_options=options)
    data, target, _ = model_dataframe(session, 'a_b')
    assert target == 'a_b'
    pd.testing.assert_series_equal(data[target], raw['A B'], check_names=False)
    data, target, _ = model_dataframe(session, 'a_b_2')
    pd.testing.assert_series_equal(data[target], raw['a_b'], check_names=False)
