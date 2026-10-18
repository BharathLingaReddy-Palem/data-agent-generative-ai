"""
profiler.py — Deterministic Dataset Profiler Service
======================================================
Pure Pandas/NumPy/SciPy — NO LLM calls, guaranteed accurate numbers.
This is an Architectural Improvement #1: Separating deterministic analytics
from LLM-based agents. This service can be unit tested independently.

Features:
- Column type classification (numeric, categorical, datetime, text, id, boolean)
- Missing value analysis with severity tiers
- Duplicate row/key detection
- Outlier detection (IQR + Z-score dual method)
- Distribution statistics (mean, median, std, skewness, kurtosis, percentiles)
- Potential target column identification (cardinality heuristic)
- Data quality score (0–100) with weighted 7-factor formula
- Correlation matrix for numeric columns
- Categorical value frequency distributions
- Anomaly detection per column with month-over-month bar chart data
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from backend.tools.stats_tools import outlier_agreement
from scipy import stats
from backend.services.serializer import sanitize_for_json
from backend.services.date_inference import infer_dates

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# COLUMN TYPE CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

def _classify_column(series: pd.Series, col_name: str) -> str:
    """
    Classifies a column into one of:
    'id', 'boolean', 'datetime', 'numeric_continuous', 'numeric_discrete',
    'categorical_low', 'categorical_high', 'text', 'constant'
    """
    n = len(series.dropna())
    if n == 0:
        return "empty"

    # Constant check
    if series.nunique() <= 1:
        return "constant"

    import re
    normalized_name = re.sub(r'[^a-z0-9]+', '_', col_name.lower()).strip('_')
    if col_name.strip() == "#" or normalized_name in {'postal_code', 'postcode', 'zip', 'zip_code', 'zipcode'}:
        return "id"

    # Boolean check
    if series.dtype == bool or set(series.dropna().unique()) <= {0, 1, True, False, "True", "False", "true", "false"}:
        return "boolean"

    # Dates must be recognized before high-cardinality identifiers.
    if infer_dates(series) is not None:
        return "datetime"

    # ID column heuristic: require an identifier name, not simply long strings.
    if series.dtype == object or pd.api.types.is_numeric_dtype(series):
        uniq_ratio = series.nunique() / max(n, 1)
        if uniq_ratio > 0.9 and n > 50:
            # Check if it matches typical ID patterns
            import re
            name = re.sub(r'([a-z])([A-Z])', r'\1_\2', col_name).lower()
            name = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
            id_keywords = bool(re.search(r'(^|_)(id|key|uuid|guid|code|ref|number|no)(_|$)', name))
            if id_keywords:
                return "id"

    # Datetime check
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    # Numeric check
    if pd.api.types.is_numeric_dtype(series):
        unique_count = series.nunique()
        if unique_count <= 20:
            return "numeric_discrete"
        return "numeric_continuous"

    # Categorical vs text
    if series.dtype == object:
        uniq_ratio = series.nunique() / max(n, 1)
        avg_len = series.dropna().astype(str).str.len().mean()
        if uniq_ratio < 0.05 or series.nunique() <= 20:
            return "categorical_low"
        elif uniq_ratio < 0.5 and avg_len < 30:
            return "categorical_high"
        else:
            return "text"

    return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# OUTLIER DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_outliers(series: pd.Series) -> Dict[str, Any]:
    """IQR + Z-score dual-method outlier detection."""
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 4:
        return {"iqr_count": 0, "zscore_count": 0, "confirmed": False}

    # IQR method
    Q1, Q3 = clean.quantile(0.25), clean.quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR
    upper = Q3 + 1.5 * IQR
    iqr_mask = (clean < lower) | (clean > upper)
    iqr_count = int(iqr_mask.sum())
    iqr_pct = round(iqr_count / len(clean) * 100, 2)

    # Z-score method
    z_scores = np.abs(stats.zscore(clean, nan_policy="omit", ddof=1))
    zscore_count = int((z_scores > 3).sum())
    zscore_pct = round(zscore_count / len(clean) * 100, 2)

    # Dual-method confirmation
    agreement = outlier_agreement(clean)
    confirmed = agreement["agreed_outlier_count"] > 0

    return {
        "iqr_count": iqr_count,
        "iqr_pct": iqr_pct,
        "iqr_lower_bound": round(float(lower), 4),
        "iqr_upper_bound": round(float(upper), 4),
        "zscore_count": zscore_count,
        "zscore_pct": zscore_pct,
        "confirmed": confirmed,
        "agreed_outlier_count": agreement["agreed_outlier_count"],
        "severity": "High" if (iqr_pct > 15 and confirmed) else ("Medium" if confirmed else "Low"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUTION STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_distribution(series: pd.Series) -> Dict[str, Any]:
    """Full distribution stats for a numeric column."""
    clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(clean) < 2:
        return {}

    arr = clean.astype(float)
    p = [0, 5, 10, 25, 50, 75, 90, 95, 99, 100]
    percentiles = {f"p{v}": round(float(np.percentile(arr, v)), 4) for v in p}

    q1, median, q3 = np.percentile(arr, [25, 50, 75])
    lower, upper = q1 - 1.5*(q3-q1), q3 + 1.5*(q3-q1)
    inside = arr[(arr >= lower) & (arr <= upper)]
    box_summary = dict(q1=float(q1), median=float(median), q3=float(q3),
        lower_whisker=float(inside.min()), upper_whisker=float(inside.max()),
        outlier_count=int(((arr < lower) | (arr > upper)).sum()))
    normality = None
    if len(arr) >= 8 and arr.std() > 0:
        _, probability = stats.normaltest(arr)
        normality = dict(test="D'Agostino-Pearson", p_value=float(probability),
            normality_not_rejected=bool(probability >= 0.05))

    # Compute actual histogram bins and counts
    try:
        n_bins = min(20, max(5, int(np.sqrt(len(arr)))))
        counts, bin_edges = np.histogram(arr, bins=n_bins)
        histogram = {
            "bin_edges": [round(float(b), 4) for b in bin_edges],
            "bin_centers": [round(float((bin_edges[i] + bin_edges[i+1]) / 2), 4) for i in range(len(counts))],
            "counts": [int(c) for c in counts],
        }
    except Exception:
        histogram = None

    return {
        "count": int(len(clean)),
        "mean": round(float(arr.mean()), 4),
        "median": round(float(arr.median()), 4),
        "std": round(float(arr.std()), 4),
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "skewness": round(float(stats.skew(arr)), 4),
        "kurtosis": round(float(stats.kurtosis(arr)), 4),
        "percentiles": percentiles,
        "histogram": histogram,
        "box_summary": box_summary,
        "normality_test": normality,
        "is_normal": None,
        "distribution_shape": (
            "right-skewed" if stats.skew(arr) > 0.5
            else "left-skewed" if stats.skew(arr) < -0.5
            else "symmetric"
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# TARGET COLUMN DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def _detect_potential_targets(df: pd.DataFrame, col_types: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Heuristic to suggest likely target columns for ML tasks.
    Returns ranked list with task type (classification/regression).
    """
    candidates = []
    target_keywords = ["target", "label", "churn", "fraud", "outcome", "status",
                       "churned", "converted", "approved", "default", "profit", "revenue", "sales"]

    for col, col_type in col_types.items():
        if col.lower().startswith('unnamed') or col_type in {'id', 'empty', 'constant'}:
            continue
        score = 0
        task_type = None

        # Keyword match boost
        if any(kw in col.lower() for kw in target_keywords):
            score += 3

        if col_type == "boolean":
            score += 4
            task_type = "binary_classification"
        elif col_type == "categorical_low" and df[col].nunique() <= 10:
            score += 3
            task_type = "classification" if df[col].nunique() <= 5 else "multiclass"
        elif col_type == "numeric_continuous":
            score += 2
            task_type = "regression"
        elif col_type == "numeric_discrete" and df[col].nunique() <= 20:
            score += 2
            task_type = "classification" if df[col].nunique() <= 5 else "regression"

        if score > 0:
            candidates.append({
                "column": col,
                "score": score,
                "task_type": task_type,
                "unique_values": int(df[col].nunique()),
                "dtype": str(df[col].dtype),
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:5]


# ─────────────────────────────────────────────────────────────────────────────
# CORRELATION MATRIX
# ─────────────────────────────────────────────────────────────────────────────

def _compute_correlation_matrix(df: pd.DataFrame) -> Dict[str, Any]:
    """Pearson correlations of measurements, excluding arbitrary identifiers."""
    numeric_df = df[numeric_analysis_columns(df)]
    if numeric_df.shape[1] < 2:
        return {"columns": [], "matrix": [], "high_correlations": []}

    # Cap columns for performance
    cols = numeric_df.columns[:15].tolist()
    corr = numeric_df[cols].corr(method="pearson").round(4)

    # Find high correlations (>0.7 or <-0.7) excluding diagonal
    high_corr = []
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i < j:
                val = float(corr.loc[c1, c2])
                if abs(val) >= 0.7:
                    high_corr.append({
                        "col1": c1, "col2": c2,
                        "correlation": val,
                        "type": "positive" if val > 0 else "negative",
                        "strength": "very strong" if abs(val) > 0.9 else "strong",
                    })

    return {
        "columns": cols,
        "matrix": corr.values.tolist(),
        "high_correlations": high_corr,
    }


def numeric_analysis_columns(df: pd.DataFrame) -> List[str]:
    """Keep numeric measurements; row/customer IDs are not analytical signals."""
    return [c for c in df.select_dtypes(include=[np.number]).columns
            if _classify_column(df[c], str(c)) in {'numeric_continuous', 'numeric_discrete', 'boolean'}]


# ─────────────────────────────────────────────────────────────────────────────
# MONTHLY ANOMALY BAR DATA (for the dashboard chart)
# ─────────────────────────────────────────────────────────────────────────────

def _build_anomaly_bar_data(df: pd.DataFrame, col_types: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Builds per-column anomaly counts suitable for the bar chart in the dashboard.
    Returns list of {column, anomaly_count, type} sorted descending.
    """
    bars = []
    numeric_cols = [c for c, t in col_types.items()
                    if t in ("numeric_continuous", "numeric_discrete") and c in df.columns]

    for col in numeric_cols[:12]:
        res = _detect_outliers(df[col])
        if res["iqr_count"] > 0:
            bars.append({
                "column": col,
                "anomaly_count": res["iqr_count"],
                "pct": res["iqr_pct"],
                "confirmed": res["confirmed"],
                "severity": res["severity"],
            })

    bars.sort(key=lambda x: x["anomaly_count"], reverse=True)
    return bars[:10]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PROFILER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def profile_dataset(df: pd.DataFrame, dataset_name: str = "Dataset") -> Dict[str, Any]:
    """
    Complete deterministic dataset profiling.
    
    Returns a structured dict ready to be JSON-serialized and sent to the frontend.
    All numbers are computed by Pandas/NumPy/SciPy — zero LLM hallucination risk.
    
    Args:
        df: Input DataFrame
        dataset_name: Name to display in the report
        
    Returns:
        Comprehensive profiling result dict
    """
    logger.info(f"[Profiler] Starting profile for '{dataset_name}' ({df.shape[0]}×{df.shape[1]})")

    total_rows = len(df)
    total_cols = len(df.columns)
    total_cells = total_rows * total_cols

    # ── 1. Column type classification ─────────────────────────────────────────
    col_types: Dict[str, str] = {}
    for col in df.columns:
        col_types[col] = _classify_column(df[col], col)

    # ── 2. Missing value analysis ─────────────────────────────────────────────
    null_counts = df.isnull().sum()
    missing_by_col: Dict[str, Any] = {}
    for col, count in null_counts.items():
        pct = round(count / max(total_rows, 1) * 100, 2)
        severity = "Critical" if pct > 30 else ("High" if pct > 10 else ("Low" if pct > 0 else "None"))
        missing_by_col[col] = {
            "count": int(count),
            "pct": pct,
            "severity": severity,
        }

    total_missing = int(null_counts.sum())
    overall_missing_pct = round(total_missing / max(total_cells, 1) * 100, 2)
    cols_with_missing = sum(1 for v in missing_by_col.values() if v["count"] > 0)

    # ── 3. Duplicate detection ────────────────────────────────────────────────
    dup_rows = int(df.duplicated().sum())
    dup_pct = round(dup_rows / max(total_rows, 1) * 100, 2)

    # ── 4. Per-column detailed profiling ──────────────────────────────────────
    columns_profile: Dict[str, Any] = {}
    outlier_summary: List[Dict] = []
    anomalies: List[Dict] = []

    numeric_cols = [c for c, t in col_types.items()
                    if t in ("numeric_continuous", "numeric_discrete")]
    cat_cols = [c for c, t in col_types.items()
                if t in ("categorical_low", "categorical_high", "boolean")]

    for col in df.columns:
        col_data: Dict[str, Any] = {
            "column": col,
            "dtype": str(df[col].dtype),
            "col_type": col_types[col],
            "missing": missing_by_col.get(col, {"count": 0, "pct": 0.0, "severity": "None"}),
            "unique_count": int(df[col].nunique()),
            "unique_pct": round(df[col].nunique() / max(total_rows, 1) * 100, 2),
        }

        if col in numeric_cols and df[col].nunique() > 1:
            col_data["distribution"] = _compute_distribution(df[col])
            outlier_res = _detect_outliers(df[col])
            col_data["outliers"] = outlier_res
            if outlier_res["iqr_count"] > 0:
                outlier_summary.append({"column": col, **outlier_res})
            if outlier_res["confirmed"]:
                anomalies.append({
                    "column": col,
                    "issue": f"Potential outliers: IQR flags {outlier_res['iqr_count']} values ({outlier_res['iqr_pct']}%); Z-score flags {outlier_res['zscore_count']}; both methods flag {outlier_res['agreed_outlier_count']}. Review context before removal.",
                    "severity": outlier_res["severity"],
                })
        elif col in cat_cols:
            top_values = df[col].value_counts().head(10)
            col_data["value_counts"] = {
                str(k): int(v) for k, v in top_values.items()
            }
            col_data["mode"] = str(df[col].mode().iloc[0]) if not df[col].mode().empty else None

        # Constant column anomaly
        if col_types[col] == "constant":
            anomalies.append({
                "column": col,
                "issue": f"'{col}' is a constant column (zero variance) — no analytical value",
                "severity": "Low",
            })

        columns_profile[col] = col_data

    # ── 5. Missing value anomalies ─────────────────────────────────────────────
    for col, info in missing_by_col.items():
        if info["severity"] in ("Critical", "High"):
            anomalies.append({
                "column": col,
                "issue": f"Missing data: {info['count']} nulls ({info['pct']}%) — severity: {info['severity']}",
                "severity": info["severity"],
            })

    # ── 6. Duplicate anomaly ────────────────────────────────────────────────
    if dup_pct > 5:
        anomalies.append({
            "column": "ALL ROWS",
            "issue": f"{dup_rows} duplicate rows ({dup_pct}%) detected — may skew all statistics",
            "severity": "High" if dup_pct > 10 else "Medium",
        })

    # ── 7. Health Score (7-factor weighted formula) ───────────────────────────
    score = 100.0
    score -= min(30.0, overall_missing_pct * 1.5)         # Factor 1: missingness
    score -= min(20.0, dup_pct * 2.0)                      # Factor 2: duplicates
    critical_count = sum(1 for a in anomalies if a["severity"] == "Critical")
    high_count = sum(1 for a in anomalies if a["severity"] == "High")
    medium_count = sum(1 for a in anomalies if a["severity"] == "Medium")
    low_count = sum(1 for a in anomalies if a["severity"] == "Low")
    score -= min(20.0, critical_count * 8.0 + high_count * 4.0)  # Factor 3: critical issues
    score -= min(10.0, medium_count * 2.5)                  # Factor 4: medium issues
    score -= min(5.0, low_count * 1.0)                      # Factor 5: low issues
    constant_cols = sum(1 for t in col_types.values() if t == "constant")
    score -= min(5.0, constant_cols * 1.0)                  # Factor 6: constant cols
    id_cols_misclassified = sum(1 for t in col_types.values() if t == "id")
    score -= min(5.0, max(0, id_cols_misclassified - 1) * 1.5)   # Factor 7: ambiguous IDs

    health_score = max(0.0, min(100.0, round(score, 1)))
    health_status = (
        "Excellent" if health_score >= 90 else
        "Good" if health_score >= 75 else
        "Fair" if health_score >= 50 else "Poor"
    )

    # ── 8. Correlation matrix ─────────────────────────────────────────────────
    correlation = _compute_correlation_matrix(df)

    # ── 9. Potential target columns ───────────────────────────────────────────
    potential_targets = _detect_potential_targets(df, col_types)

    # ── 10. Anomaly bar chart data ─────────────────────────────────────────────
    anomaly_bars = _build_anomaly_bar_data(df, col_types)

    # ── 11. Top categories (for pie/donut chart) ───────────────────────────────
    top_categories: List[Dict] = []
    for col in cat_cols[:4]:
        vc = df[col].value_counts(normalize=True).head(1)
        if not vc.empty:
            top_categories.append({
                "column": col,
                "top_value": str(vc.index[0]),
                "pct": round(float(vc.iloc[0]) * 100, 1),
            })

    # ── 12. Dataset overview stats ─────────────────────────────────────────────
    date_cols = [c for c, t in col_types.items() if t == "datetime"]
    date_range = None
    if date_cols:
        try:
            d_series = infer_dates(df[date_cols[0]]).dropna()
            if not d_series.empty:
                date_range = {
                    "column": date_cols[0],
                    "min": str(d_series.min().date()),
                    "max": str(d_series.max().date()),
                    "span_days": int((d_series.max() - d_series.min()).days),
                }
        except Exception:
            pass

    logger.info(
        f"[Profiler] Done — Health: {health_score}/100 ({health_status}), "
        f"{len(anomalies)} anomalies, {len(correlation['high_correlations'])} high correlations"
    )

    result_dict = {
        # ── Overview ──────────────────────────────────────────────────────────
        "dataset_name": dataset_name,
        "overview": {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "total_cells": total_cells,
            "total_missing": total_missing,
            "overall_missing_pct": overall_missing_pct,
            "cols_with_missing": cols_with_missing,
            "duplicate_rows": dup_rows,
            "duplicate_pct": dup_pct,
            "numeric_cols": len(numeric_cols),
            "categorical_cols": len(cat_cols),
            "datetime_cols": len(date_cols),
            "date_range": date_range,
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
        },
        # ── Health Score ──────────────────────────────────────────────────────
        "health": {
            "score": health_score,
            "status": health_status,
            "anomaly_counts": {
                "critical": critical_count,
                "high": high_count,
                "medium": medium_count,
                "low": low_count,
                "total": len(anomalies),
            },
        },
        # ── Column Types ──────────────────────────────────────────────────────
        "col_types": col_types,
        # ── Per-column Profiles & Column Names ───────────────────────────────
        "columns": columns_profile,
        "column_names": [str(c) for c in df.columns],
        "column_profiles": columns_profile,
        # ── Anomalies ─────────────────────────────────────────────────────────
        "anomalies": anomalies,
        "anomaly_bars": anomaly_bars,
        # ── Correlation ───────────────────────────────────────────────────────
        "correlation": correlation,
        # ── ML Target Suggestions ─────────────────────────────────────────────
        "potential_targets": potential_targets,
        # ── Dashboard Display Data ────────────────────────────────────────────
        "top_categories": top_categories,
        "outlier_summary": outlier_summary[:8],
    }

    return sanitize_for_json(result_dict)
