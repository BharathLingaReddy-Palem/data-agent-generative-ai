import numpy as np
import pandas as pd
import pytest
from backend.services.profiler import _compute_distribution
from backend.tools.stats_tools import outlier_agreement, detect_outliers_combined, holm_adjust, two_sample_ttest, chi_square_test
from backend.agents.trend_agent import _compute_seasonality_by_month, _compute_stl_decomposition, _compute_mann_kendall, _compute_time_series


def test_box_summary_uses_observations_for_whiskers_and_preserves_zero():
    values = pd.Series([0, 0, 0, 1, 2, 3, 4, 100])
    summary = _compute_distribution(values)
    box = summary['box_summary']
    assert box['q1'] == 0 and box['median'] == 1.5 and box['q3'] == 3.25
    assert box['lower_whisker'] == 0 and box['upper_whisker'] == 4
    assert box['outlier_count'] == 1
    assert sum(summary['histogram']['counts']) == len(values)
    assert summary['is_normal'] is None
    assert 'normality_not_rejected' in summary['normality_test']


def test_outlier_agreement_intersects_masks_even_for_duplicate_indexes():
    # Skewed data can yield flags from only one method; counts alone are not agreement.
    values = np.random.default_rng(14).exponential(size=150)
    series = pd.Series(values, index=[0]*len(values))
    q1, q3 = np.quantile(values, [.25, .75])
    iqr = (values < q1-1.5*(q3-q1)) | (values > q3+1.5*(q3-q1))
    z = abs((values-values.mean())/values.std(ddof=1)) > 3
    result = outlier_agreement(series)
    assert result['agreed_outlier_count'] == int((iqr & z).sum())
    assert result['union_outlier_count'] == int((iqr | z).sum())
    assert result['iqr_only_count'] == int((iqr & ~z).sum()) > 0
    combined = detect_outliers_combined(pd.DataFrame({'value':series}), 'value')
    assert 'do not establish data errors' in combined['verdict']


def test_holm_and_invalid_test_inputs():
    assert holm_adjust([.03, .04]) == pytest.approx([.06, .06])
    assert holm_adjust([.2, .001, .04]) == pytest.approx([.2, .003, .08])
    assert holm_adjust([]) == []
    frame = pd.DataFrame({'group':list('aaabbbccc'), 'value':range(9)})
    assert 'error' in two_sample_ttest(frame, 'group', 'value')
    sparse = pd.DataFrame({'a':['a','a','b','b'], 'b':['a','b','a','b']})
    assert 'error' in chi_square_test(sparse, 'a', 'b')


def test_comparison_uses_predeclared_primary_test_not_either_test(monkeypatch):
    from backend.tools import comparator
    monkeypatch.setattr(comparator.stats, 'ttest_ind', lambda *a, **k:(1, .2))
    monkeypatch.setattr(comparator.stats, 'mannwhitneyu', lambda *a, **k:(1, .001))
    monkeypatch.setattr(comparator, 'invoke_llm', lambda **kwargs:'Offline narrative')
    result = comparator.compare_datasets(pd.DataFrame({'sales':range(10)}), pd.DataFrame({'sales':range(1,11)}))
    comparison = result['metric_comparisons'][0]
    assert comparison['p_value_mann_whitney'] == .001
    assert comparison['p_value_adjusted'] == .2
    assert comparison['is_statistically_significant'] is False
    assert comparison['test_estimand'] == 'mean per record, not aggregate sum'


def test_undefined_comparison_is_unavailable_and_ids_are_never_reintroduced(monkeypatch):
    from backend.tools import comparator
    monkeypatch.setattr(comparator, 'invoke_llm', lambda **kwargs:'Offline')
    result = comparator.compare_datasets(pd.DataFrame({'sales':[1]*10}), pd.DataFrame({'sales':[2]*10}))
    metric = result['metric_comparisons'][0]
    assert metric['p_value'] is None and metric['p_value_adjusted'] is None
    assert metric['test_available'] is False and not metric['is_statistically_significant']
    assert 'unavailable' in result['executive_narrative']
    only_ids = comparator.compare_datasets(pd.DataFrame({'customer_id':range(10)}), pd.DataFrame({'customer_id':range(1,11)}))
    assert only_ids['metric_comparisons'] == []


def test_normality_nonrejection_is_not_proof_and_constants_are_unavailable():
    from backend.agents.eda_agent import _compute_normality
    normal = _compute_normality(pd.Series(np.random.default_rng(42).normal(size=100)))
    assert normal['is_normal'] is None
    assert 'normality_not_rejected' in normal
    assert _compute_normality(pd.Series([2.]*100))['p_value'] is None


def test_hypothesis_significance_uses_family_adjustment_and_preserves_zero_effect(monkeypatch):
    from backend.agents import hypothesis_agent as agent
    frame = pd.DataFrame({'group':['a','b']*10, 'group2':['c','d']*10, 'sales':np.arange(20)})
    def ttest(df, group_col, value_col):
        return dict(test='Welch', group_col=group_col, p_value=.03 if group_col=='group' else .04,
            statistically_significant=True, cohens_d=0., significance_level=.05)
    prompts = []
    monkeypatch.setattr(agent, '_select_test_type', lambda *a:'ttest')
    monkeypatch.setattr(agent, 'two_sample_ttest', ttest)
    monkeypatch.setattr(agent, 'chi_square_test', lambda *a, **k:{'error':'not applicable'})
    monkeypatch.setattr(agent, 'invoke_llm', lambda **k:prompts.append(k['prompt']) or 'Offline')
    result = agent.hypothesis_agent_node(dict(df_raw=frame, schema_metadata={
        'recommended_measures':['sales'], 'recommended_dimensions':['group','group2']}))['hypothesis_results']
    tests = result['tests_conducted']
    assert len(tests) == 2
    assert all(t['raw_statistically_significant'] and not t['statistically_significant'] for t in tests)
    assert all(t['p_value_adjusted'] == pytest.approx(.06) for t in tests)
    assert 'Effect size: 0.0' in prompts[0]


def monthly(values):
    return pd.DataFrame({'date':pd.date_range('2023-01-01', periods=len(values), freq='MS'), 'sales':values})


def test_one_year_differences_are_not_established_seasonality():
    result = _compute_seasonality_by_month(monthly(np.arange(12)*20+100), 'date', 'sales')
    assert result['seasonal_pattern_detected'] is False
    assert result['repeated_cycles'] == 1
    assert result['basis'] == 'mean monthly total'


def test_two_cycles_repeating_pattern_constant_series_and_gaps():
    frame = monthly(100+20*np.sin(np.arange(24)*2*np.pi/12))
    assert _compute_seasonality_by_month(frame, 'date', 'sales')['seasonal_pattern_detected'] is True
    constant = monthly([100]*24)
    assert not _compute_stl_decomposition(constant, 'date', 'sales')['available']
    assert not _compute_seasonality_by_month(constant, 'date', 'sales')['seasonal_pattern_detected']
    gap = frame.drop(index=3)
    assert not _compute_stl_decomposition(gap, 'date', 'sales')['available']
    assert 'error' in _compute_mann_kendall(gap, 'date', 'sales')
    series = _compute_time_series(gap, 'date', 'sales')
    assert series['missing_months'] == 1
    assert series['monthly_data'][3]['value'] is None
    assert series['monthly_data'][3]['mom_pct'] is None
    assert series['monthly_data'][4]['mom_pct'] is None


def test_mann_kendall_tie_correction():
    result = _compute_mann_kendall(monthly([1,1,2,2,3,3]), 'date', 'sales')
    expected = (6*5*17 - 3*(2*1*9))/18
    assert result['variance_s'] == pytest.approx(expected)
    assert 'independent observations' in result['assumptions']
