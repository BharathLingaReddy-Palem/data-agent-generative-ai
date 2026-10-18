"""Conservative aggregation hints; column names never establish currency or units."""
import re


def metric_aggregation(column):
    tokens = set(re.split(r'[^a-z0-9]+', str(column).lower()))
    non_additive = tokens & {'rate', 'ratio', 'pct', 'percent', 'percentage', 'score',
        'age', 'price', 'salary', 'income', 'duration', 'days', 'years', 'hours', 'temperature'}
    additive = tokens & {'sales', 'revenue', 'profit', 'cost', 'amount', 'quantity', 'units', 'count', 'volume'} or str(column).lstrip().startswith('#')
    return 'sum' if additive and not non_additive else 'mean'
