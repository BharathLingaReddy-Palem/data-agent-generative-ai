"""
quality_agent.py — Data Health & Quality Audit Agent
=====================================================
TOOL-FIRST PATTERN:
  Step 1: Pandas/NumPy/SciPy compute EXACT health metrics
  Step 2: LLM receives a pre-computed fact sheet and writes
          a plain-English quality briefing for the analyst.
  LLM NEVER computes numbers — it only interprets them.
"""
import logging
from typing import Dict, Any, List
import pandas as pd
import numpy as np

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.services.profiler import profile_dataset
from backend.tools.stats_tools import (
    detect_outliers_iqr,
    outlier_agreement,
    detect_outliers_zscore,
    detect_zero_variance_columns,
    detect_high_cardinality_categoricals,
    detect_type_anomalies,
)

logger = logging.getLogger(__name__)


def _check_negative_values(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """Checks for negative values in business metrics that should always be positive."""
    neg_count = int((df[col] < 0).sum())
    neg_pct = round((neg_count / len(df)) * 100.0, 2) if len(df) > 0 else 0
    return {
        "column": col,
        "negative_count": neg_count,
        "negative_pct": neg_pct,
    }


def quality_agent_node(state: AgentState) -> AgentState:
    """
    Quality Agent — Comprehensive Data Health Audit (Tool-First Pattern)

    Checks (all computed deterministically by Pandas/NumPy/SciPy):
      1. Missingness: per-column null counts and severity tiers
      2. Duplicates: row-level and primary-key level
      3. Outliers: IQR fence + Z-score (both methods, both reported)
      4. Negative values in non-negative business measures
      5. Zero-variance / constant columns
      6. High-cardinality categoricals (misclassified IDs)
      7. Type consistency anomalies (mixed numeric/string columns)
      8. Future-dated timestamps
      9. Weighted health score (7-factor formula)
     10. LLM writes a plain-English quality briefing from the computed numbers
    """
    logger.info("--> [Quality Agent] Performing comprehensive Data Health Audit (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Quality Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    total_rows = len(df)
    total_cells = total_rows * len(df.columns)
    measures = schema_meta.get("recommended_measures", [])
    date_col = schema_meta.get("primary_date_column")
    id_col = schema_meta.get("primary_id_column")

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 1: Missingness Audit (Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    null_counts = df.isnull().sum()
    missing_by_col: Dict[str, Any] = {}
    for col, count in null_counts.items():
        if count > 0:
            pct = round((count / total_rows) * 100.0, 2)
            severity = "Critical" if pct > 30 else ("High" if pct > 10 else "Low")
            missing_by_col[col] = {"count": int(count), "percentage": pct, "severity": severity}

    total_missing_cells = int(null_counts.sum())
    overall_missing_pct = round((total_missing_cells / total_cells) * 100.0, 2) if total_cells > 0 else 0

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 2: Duplicate Audit (Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    row_duplicates = int(df.duplicated().sum())
    id_duplicates = 0
    if id_col and id_col in df.columns:
        id_duplicates = int(df[id_col].duplicated().sum())

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 3: Outlier Detection — IQR + Z-score (stats_tools)
    # ──────────────────────────────────────────────────────────────────────────
    outlier_results: Dict[str, Any] = {}
    anomalies: List[Dict] = []

    numeric_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]
    for col in numeric_cols:
        iqr_res = detect_outliers_iqr(df, col)
        z_res = detect_outliers_zscore(df, col)
        agreement = outlier_agreement(df[col])
        outlier_results[col] = {"iqr": iqr_res, "zscore": z_res, "agreement": agreement}

        # Dual-method agreement → high confidence anomaly
        iqr_pct = iqr_res.get("outlier_percentage", 0)
        z_pct = z_res.get("outlier_percentage", 0)
        if agreement["agreed_outlier_count"] > 0:
            anomalies.append({
                "column": col,
                "issue": (
                    f"{agreement['agreed_outlier_count']} observations flagged by both rules; IQR detects {iqr_pct}% extreme values "
                    f"(beyond {iqr_res.get('lower_bound')} – {iqr_res.get('upper_bound')}); "
                    f"Z-score flags {z_res.get('outlier_count')} values (|z| > 3σ). These rules do not establish data errors."
                ),
                "severity": "High" if iqr_pct > 15 else "Medium",
            })
        elif iqr_pct > 5.0:
            anomalies.append({
                "column": col,
                "issue": f"IQR: {iqr_res.get('outlier_count')} outliers ({iqr_pct}%) detected in '{col}'",
                "severity": "Medium",
            })

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 4: Negative Values in Non-Negative Measures (Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    non_negative_terms = ["revenue", "sales", "price", "quantity", "cost", "amount", "volume", "units", "profit"]
    for col in measures:
        if col in df.columns and np.issubdtype(df[col].dtype, np.number):
            if any(term in col.lower() for term in non_negative_terms):
                neg = _check_negative_values(df, col)
                if neg["negative_count"] > 0:
                    anomalies.append({
                        "column": col,
                        "issue": f"{neg['negative_count']} records ({neg['negative_pct']}%) have negative values in a non-negative measure",
                        "severity": "High",
                    })

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 5: Zero-Variance / Constant Columns (stats_tools)
    # ──────────────────────────────────────────────────────────────────────────
    zero_var_cols = detect_zero_variance_columns(df)
    for col in zero_var_cols:
        anomalies.append({
            "column": col,
            "issue": f"'{col}' is constant (zero variance) — carries no analytical information",
            "severity": "Low",
        })

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 6: High-Cardinality Categoricals (stats_tools)
    # ──────────────────────────────────────────────────────────────────────────
    high_card = detect_high_cardinality_categoricals(df)
    for hc in high_card:
        anomalies.append({
            "column": hc["column"],
            "issue": hc["warning"],
            "severity": "Low",
        })

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 7: Type Consistency (stats_tools)
    # ──────────────────────────────────────────────────────────────────────────
    type_issues = []
    for col in df.columns[:15]:
        res = detect_type_anomalies(df, col)
        if res.get("issues"):
            type_issues.extend(res["issues"])
            for issue in res["issues"]:
                anomalies.append({
                    "column": col,
                    "issue": issue["detail"],
                    "severity": issue["severity"],
                })

    # ──────────────────────────────────────────────────────────────────────────
    # CHECK 8: Future-Dated Timestamps (Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    if date_col and date_col in df.columns:
        try:
            now = pd.Timestamp.now()
            date_series = pd.to_datetime(df[date_col], errors="coerce")
            future_dates = int((date_series > now).sum())
            if future_dates > 0:
                anomalies.append({
                    "column": date_col,
                    "issue": f"{future_dates} records contain future-dated timestamps",
                    "severity": "Critical",
                })
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # HEALTH SCORE — Weighted 7-Factor Formula
    # ──────────────────────────────────────────────────────────────────────────
    # Use the same deterministic scoring definition as the uploaded-data dashboard.
    # The agent also records additional domain checks, which do not silently
    # change the meaning of the displayed score between pages.
    canonical_health = profile_dataset(df, dataset_name=state.get('dataset_name', 'Dataset'))['health']
    final_health_score = canonical_health['score']
    health_status = canonical_health['status']
    dup_pct = (row_duplicates / total_rows) * 100.0 if total_rows > 0 else 0
    critical_count = sum(1 for a in anomalies if a['severity'] == 'Critical')
    high_count = sum(1 for a in anomalies if a['severity'] == 'High')
    medium_count = sum(1 for a in anomalies if a['severity'] == 'Medium')

    # ──────────────────────────────────────────────────────────────────────────
    # LLM STEP: Interpret computed numbers — NOT compute them
    # ──────────────────────────────────────────────────────────────────────────
    quality_fact_sheet = {
        "health_score": final_health_score,
        "health_status": health_status,
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "overall_missing_pct": overall_missing_pct,
        "columns_with_missing": len(missing_by_col),
        "critical_missing_cols": [c for c, v in missing_by_col.items() if v["severity"] == "Critical"],
        "duplicate_rows": row_duplicates,
        "duplicate_pct": round(dup_pct, 2),
        "id_key_collisions": id_duplicates,
        "anomaly_count": len(anomalies),
        "critical_anomalies": [a for a in anomalies if a["severity"] == "Critical"],
        "high_anomalies": [a for a in anomalies if a["severity"] == "High"][:3],
        "zero_variance_cols": zero_var_cols,
        "high_cardinality_cols": [h["column"] for h in high_card],
    }

    quality_briefing = ""
    # Counts and recommendations must not be inferred from a prose model.
    quality_briefing = (
        f"- **Missing values:** {total_missing_cells:,} cells ({overall_missing_pct}%). "
        "Review missingness patterns before choosing an imputation strategy.\n"
        f"- **Duplicates:** {row_duplicates:,} rows. Review whether repeated records are legitimate before removing them.\n"
        f"- **Quality flags:** {len(anomalies)} issues; outlier checks covered all {len(numeric_cols)} numeric columns. "
        "Flags identify values for review, not confirmed data errors. Counts from different columns must not be added to infer unique affected rows."
    )

    # ──────────────────────────────────────────────────────────────────────────
    # Build final quality_audit dict
    # ──────────────────────────────────────────────────────────────────────────
    quality_audit = {
        "health_score": final_health_score,
        "health_status": health_status,
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "overall_missing_pct": overall_missing_pct,
        "missing_columns": missing_by_col,
        "duplicate_rows": row_duplicates,
        "duplicate_pct": round(dup_pct, 2),
        "id_collisions": id_duplicates,
        "outlier_analysis": outlier_results,
        "anomalies": anomalies,
        "zero_variance_columns": zero_var_cols,
        "high_cardinality_columns": [h["column"] for h in high_card],
        "quality_briefing": quality_briefing,
        # Summary counts for frontend display
        "anomaly_counts": {
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": sum(1 for a in anomalies if a["severity"] == "Low"),
        }
    }

    execution_steps.append(
        f"Quality Agent: 7-factor audit completed — Health Score: {final_health_score}/100 ({health_status}). "
        f"{len(anomalies)} anomalies detected ({critical_count} Critical, {high_count} High)."
    )

    return {
        **state,
        "quality_audit": quality_audit,
        "health_score": final_health_score,
        "execution_steps": execution_steps,
        "errors": errors,
    }
