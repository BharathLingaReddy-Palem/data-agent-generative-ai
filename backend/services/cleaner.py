"""
cleaner.py — Intelligent Data Cleaning Service
===============================================
Deterministic, reproducible data cleaning without hallucinations.
Handles:
- Column name standardization (snake_case, special character stripping)
- Duplicate row detection and removal
- Missing value imputation (median for skewed, mean for normal, mode for categorical)
- Outlier winsorization / clipping (IQR method)
- Type conversion & whitespace trimming
- Produces a structured audit log of all transformations applied.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


def _unique_names(names):
    used, reserved, result = set(), set(names), []
    for base in names:
        name, suffix = base, 2
        while name in used or (name != base and name in reserved):
            name = f"{base}_{suffix}"
            suffix += 1
        used.add(name)
        result.append(name)
    return result


def strip_column_names(df):
    """Trim headers without introducing duplicates during ingestion."""
    result = df.copy()
    result.columns = _unique_names([str(c).strip() or f"col_{i}" for i, c in enumerate(df.columns)])
    return result


def clean_column_names(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Standardizes column names to clean snake_case."""
    df_clean = df.copy()
    if not df.columns.is_unique:
        raise ValueError("Duplicate input column names must be resolved before cleaning.")
    names = []
    for index, col in enumerate(df_clean.columns):
        clean_name = str(col).strip()
        clean_name = re.sub(r"[^\w\s-]", "", clean_name)
        clean_name = re.sub(r"[\s-]+", "_", clean_name).lower()
        if not clean_name:
            clean_name = f"col_{index}"
        names.append(clean_name)
    rename_map = dict(zip(df.columns, _unique_names(names)))
    df_clean.rename(columns=rename_map, inplace=True)
    return df_clean, rename_map


def clean_dataset(
    df: pd.DataFrame,
    handle_missing: bool = True,
    handle_outliers: bool = True,
    remove_duplicates: bool = True,
    standardize_names: bool = True,
    target_column: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Cleans a pandas DataFrame intelligently and produces an audit report.
    """
    df_clean = df.copy()
    if not df.columns.is_unique:
        raise ValueError("Duplicate input column names must be resolved before cleaning.")
    if target_column is not None and target_column not in df.columns:
        raise ValueError(f"Target column '{target_column}' does not exist.")
    initial_rows, initial_cols = df_clean.shape
    audit_log: Dict[str, Any] = {
        "initial_shape": {"rows": initial_rows, "columns": initial_cols},
        "duplicates_removed": 0,
        "renamed_columns": {},
        "missing_imputations": [],
        "outliers_clipped": [],
        "type_conversions": [],
    }

    # 1. Standardize column names
    if standardize_names:
        df_clean, rename_map = clean_column_names(df_clean)
        audit_log["renamed_columns"] = {k: v for k, v in rename_map.items() if k != v}
        target_column = rename_map.get(target_column, target_column)
    audit_log["protected_target"] = target_column
    # Without a selected target, only structural cleanup is safe for future ML.
    if target_column is None:
        handle_missing = handle_outliers = False
        audit_log["notice"] = "Select a target to enable imputation and clipping; potential labels are preserved."

    # 2. Trim string columns & strip extra spaces
    for col in df_clean.select_dtypes(include=["object"]).columns:
        if target_column is None or col == target_column:
            continue
        df_clean[col] = df_clean[col].map(lambda value: value.strip() if isinstance(value, str) else value)
        # Replace empty strings or literal 'nan', 'null', 'None' with np.nan
        df_clean[col] = df_clean[col].replace(["", "nan", "NaN", "null", "NULL", "None"], np.nan)

    # 2b. Drop completely empty columns and phantom unnamed columns from trailing commas
    empty_cols = [
        c for c in df_clean.columns
        if target_column is not None and c != target_column and (df_clean[c].isna().all() or (str(c).startswith("unnamed") and df_clean[c].isna().mean() > 0.8))
    ]
    if empty_cols:
        df_clean.drop(columns=empty_cols, inplace=True)
        audit_log["dropped_empty_columns"] = empty_cols

    # 3. Detect & Remove Duplicates
    if remove_duplicates:
        dups_count = int(df_clean.duplicated().sum())
        if dups_count > 0:
            df_clean = df_clean.drop_duplicates().reset_index(drop=True)
            audit_log["duplicates_removed"] = dups_count

    # 4. Handle Missing Values
    if handle_missing:
        audit_log['nonfinite_replacements'] = []
        for col in df_clean.select_dtypes(include=[np.number]).columns:
            if col == target_column:
                continue
            count = int(np.isinf(df_clean[col]).sum())
            if count:
                df_clean[col] = df_clean[col].replace([np.inf, -np.inf], np.nan)
                audit_log['nonfinite_replacements'].append({'column': col, 'count': count})
        for col in df_clean.columns:
            if col == target_column:
                continue
            missing_count = int(df_clean[col].isna().sum())
            if missing_count == 0:
                continue

            if pd.api.types.is_numeric_dtype(df_clean[col]):
                series_clean = df_clean[col].dropna()
                if len(series_clean) > 0:
                    skew = stats.skew(series_clean)
                    strategy = "median" if abs(skew) > 0.5 else "mean"
                    fill_val = round(float(series_clean.median() if strategy == "median" else series_clean.mean()), 4)
                    df_clean[col] = df_clean[col].fillna(fill_val)
                    audit_log["missing_imputations"].append({
                        "column": col,
                        "missing_count": missing_count,
                        "strategy": strategy,
                        "imputed_value": fill_val,
                    })
            else:
                mode_vals = df_clean[col].mode()
                fill_val = str(mode_vals.iloc[0]) if len(mode_vals) > 0 else "Unknown"
                df_clean[col] = df_clean[col].fillna(fill_val)
                audit_log["missing_imputations"].append({
                    "column": col,
                    "missing_count": missing_count,
                    "strategy": "mode",
                    "imputed_value": fill_val,
                })

    # 5. Handle Outliers (IQR Winsorization/Clipping)
    if handle_outliers:
        for col in df_clean.select_dtypes(include=[np.number]).columns:
            if col == target_column:
                continue
            clean_series = df_clean[col].dropna()
            if len(clean_series) < 10:
                continue

            q1 = clean_series.quantile(0.25)
            q3 = clean_series.quantile(0.75)
            iqr = q3 - q1
            if iqr <= 0:
                continue

            lower_bound = round(float(q1 - 1.5 * iqr), 4)
            upper_bound = round(float(q3 + 1.5 * iqr), 4)

            outlier_mask = (df_clean[col] < lower_bound) | (df_clean[col] > upper_bound)
            outlier_count = int(outlier_mask.sum())

            if outlier_count > 0:
                # Clip values to bounds
                df_clean[col] = df_clean[col].clip(lower=lower_bound, upper=upper_bound)
                audit_log["outliers_clipped"].append({
                    "column": col,
                    "outlier_count": outlier_count,
                    "lower_bound": lower_bound,
                    "upper_bound": upper_bound,
                })

    final_rows, final_cols = df_clean.shape
    audit_log["final_shape"] = {"rows": final_rows, "columns": final_cols}
    audit_log["summary_message"] = (
        f"Cleaned dataset: {audit_log['duplicates_removed']} duplicates removed, "
        f"{len(audit_log['missing_imputations'])} columns imputed, "
        f"{len(audit_log['outliers_clipped'])} columns winsorized."
    )

    return df_clean, audit_log
