"""Report headlines use computed evidence, never synthesized statistics."""


def build_evidence_briefing(state):
    quality = state.get('quality_audit', {})
    frame = state.get('df_clean')
    if frame is None:
        frame = state.get('df_raw')
    rows = quality.get('total_rows', len(frame) if frame is not None else None)
    columns = quality.get('total_columns', len(frame.columns) if frame is not None else None)
    shape = f" **Records:** {rows:,}. **Columns:** {columns:,}." if rows is not None and columns is not None else ''
    summary = f"**Dataset quality:** {state.get('health_score', 'unavailable')}/100." + shape
    if 'overall_missing_pct' in quality:
        summary += f" **Missing cells:** {quality['overall_missing_pct']}%."
    if 'duplicate_rows' in quality:
        summary += f" **Duplicate rows:** {quality['duplicate_rows']:,}."
    metrics = state.get('kpi_results', {}).get('kpi_metrics', [])
    facts = [f"**{m.get('metric_name')}**: {m.get('aggregation', 'value')} {m.get('formatted_value', m.get('formatted_total', 'unavailable'))}." for m in metrics[:6]]
    if not facts:
        profiles = state.get('eda_results', {}).get('column_profiles', {})
        for column, profile in list(profiles.items())[:6]:
            if profile.get('mean') is not None:
                facts.append(f"**{column}**: mean {profile['mean']:.4g}.")
    if facts:
        summary += '\n\n' + ' '.join(facts)
    summary += ('\n\nUnits and reporting periods are unspecified unless supplied in metric metadata. '
                'These descriptive statistics do not establish causal drivers or performance against a benchmark.')
    trend = state.get('trend_results', {})
    if trend.get('available'):
        summary += ' Time-series results are available in the detailed analysis; temporal association does not establish causation.'
    else:
        summary += ' No reliable time trend is available.'
    actions = ('1. Review missing values, duplicate records and flagged outliers in the quality audit; preserve legitimate observations.\n'
               '2. Confirm column meanings, units and any relevant comparison period before interpreting the descriptive values.\n'
               '3. Treat statistical associations as exploratory. Check test assumptions and adjusted p-values, and validate models on independent data before using predictions.')
    return summary, actions
