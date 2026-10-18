// Read the canonical analysis API fields in one place.
export function insightSections(analysis) {
  return [
    {id:'kpi', title:'KPI Analysis', content:analysis.kpi_results?.kpi_interpretation || 'KPI analysis not available.', data:analysis.kpi_results?.kpi_metrics?.slice(0,5)},
    {id:'diagnostic', title:'Root-Cause Diagnostics', content:analysis.diagnostic_results?.diagnostic_narrative || 'Diagnostic analysis not available.'},
    {id:'trend', title:'Trend Analysis', content:analysis.trend_results?.trend_narrative || analysis.trend_results?.reason || 'Trend analysis not available.'},
    {id:'hypothesis', title:'Hypothesis Testing', content:analysis.hypothesis_results?.executive_summary || 'Hypothesis testing not run.', data:analysis.hypothesis_results?.tests_conducted?.slice(0,4)},
  ];
}

export function planExplanation(analysis) {
  return analysis.analysis_plan?.reasoning || analysis.analysis_plan?.intent || '';
}

export function hypothesisCells(row) {
  const probability = p => typeof p === 'number' && Number.isFinite(p) ? p.toExponential(3) : 'Unavailable';
  return [row.test || 'Statistical test', row.hypothesis || `${row.value_col || 'Value'} by ${row.group_col || 'group'}`,
    probability(row.p_value), probability(row.p_value_adjusted),
    row.statistically_significant == null ? 'Unavailable' : row.statistically_significant ? 'Significant' : 'Not significant',
    row.assumptions || 'Review test assumptions'];
}
