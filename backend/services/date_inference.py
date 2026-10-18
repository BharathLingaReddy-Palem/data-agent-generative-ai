"""Conservative date inference shared by profiling and semantic analysis."""
import pandas as pd


def infer_dates(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    if not (pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)):
        return None
    values = series.dropna().astype(str).str.strip()
    if values.empty:
        return None
    # Require a date shape. Numbers, names, status text and clock-only values
    # should not become timestamps (or disappear as NaT).
    shapes = values.str.match(r'^\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?(?:[ T].*)?$|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:[ T].*)?$')
    if shapes.mean() < 0.8:
        return None
    slash = values.str.extract(r'^(\d{1,2})/(\d{1,2})/\d{2,4}')
    first = pd.to_numeric(slash[0], errors='coerce')
    second = pd.to_numeric(slash[1], errors='coerce')
    has_day_first, has_month_first = (first > 12).any(), (second > 12).any()
    if has_day_first and has_month_first:
        return None  # Mixed conventions cannot be inferred safely.
    # Ambiguous slash dates require an explicit convention from the caller.
    if first.notna().any() and not (has_day_first or has_month_first):
        return None
    parsed = pd.to_datetime(series, errors='coerce', format='mixed', dayfirst=bool(has_day_first))
    return parsed if parsed.notna().sum() / len(values) >= 0.8 else None
