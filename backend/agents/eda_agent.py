"""
eda_agent.py — Exploratory Data Analysis Agent
===============================================
TOOL-FIRST PATTERN:
  Step 1: NumPy/Pandas/SciPy computes ALL statistical measures
          (skewness, kurtosis, normality tests, Pearson/Spearman correlations)
  Step 2: LLM receives a structured fact sheet of computed values
          and writes the analytical narrative.
  LLM NEVER computes statistics — it only interprets them.
"""
import json
import logging
from typing import Dict, Any, List
import numpy as np
import pandas as pd

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.services.profiler import numeric_analysis_columns
from backend.tools.stats_tools import compute_descriptive_stats, detect_outliers_zscore

logger = logging.getLogger(__name__)


def _classify_skewness(skew_val: float) -> str:
    if abs(skew_val) < 0.5:
        return "Approximately Symmetric"
    elif skew_val > 2.0:
        return "Extreme Right Skew (many outliers on high end)"
    elif skew_val > 0.5:
        return "Right Skewed (positive tail)"
    elif skew_val < -2.0:
        return "Extreme Left Skew (many outliers on low end)"
    else:
        return "Left Skewed (negative tail)"


def _classify_kurtosis(kurt_val: float) -> str:
    """Excess kurtosis interpretation (Fisher's definition, normal = 0)."""
    if kurt_val > 3.0:
        return "Leptokurtic (heavy tails, extreme values likely)"
    elif kurt_val < -1.0:
        return "Platykurtic (thin tails, data concentrated near mean)"
    else:
        return "Approximately Mesokurtic (normal-like)"


def _compute_normality(vals: pd.Series) -> Dict[str, Any]:
    """Run Shapiro-Wilk (small) or D'Agostino-Pearson (large) normality test."""
    try:
        import scipy.stats as stats
        sample = pd.to_numeric(vals, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna().astype(float)
        n = len(sample)
        if n < 8 or sample.std() == 0:
            return {"test": "N/A", "p_value": None, "is_normal": None}
        if n <= 5000:
            stat, p = stats.shapiro(sample.sample(min(n, 300), random_state=42))
            test_name = "Shapiro-Wilk"
        else:
            stat, p = stats.normaltest(sample)
            test_name = "D'Agostino-Pearson"
        return {
            "test": test_name,
            "statistic": round(float(stat), 6),
            "p_value": float(p),
            "sample_size": min(n, 300) if n <= 5000 else n,
            "is_normal": None,
            "normality_not_rejected": bool(p >= 0.05),
            "verdict": "Normality not rejected; this does not prove a normal distribution" if p >= 0.05 else "Normality rejected at alpha=0.05"
        }
    except Exception:
        return {"test": "N/A", "p_value": None, "is_normal": None}


def _compute_mutual_information(df: pd.DataFrame, numeric_cols: List[str]) -> List[Dict[str, Any]]:
    """
    Computes pairwise correlation (Pearson + Spearman) for numeric columns.
    Returns top correlated pairs with strength labels.
    Spearman is more robust for non-normal / skewed data.
    """
    try:
        import scipy.stats as stats
        pairs = []
        cols = numeric_cols[:8]  # cap for performance

        seen = set()
        for i, c1 in enumerate(cols):
            for c2 in cols[i+1:]:
                if (c1, c2) in seen or (c2, c1) in seen:
                    continue
                seen.add((c1, c2))

                clean = df[[c1, c2]].dropna()
                if len(clean) < 10:
                    continue

                pearson_r, pearson_p = stats.pearsonr(clean[c1], clean[c2])
                spearman_r, spearman_p = stats.spearmanr(clean[c1], clean[c2])

                abs_r = abs(pearson_r)
                strength = "Very Strong" if abs_r > 0.85 else \
                           "Strong" if abs_r > 0.70 else \
                           "Moderate" if abs_r > 0.40 else \
                           "Weak" if abs_r > 0.20 else "Negligible"
                direction = "Positive" if pearson_r > 0 else "Negative"

                pairs.append({
                    "col1": c1,
                    "col2": c2,
                    "pearson_r": round(float(pearson_r), 4),
                    "pearson_p": float(round(pearson_p, 6)),
                    "spearman_r": round(float(spearman_r), 4),
                    "spearman_p": float(round(spearman_p, 6)),
                    "abs_correlation": round(abs_r, 4),
                    "strength": strength,
                    "direction": direction,
                    "significant": bool(pearson_p < 0.05),
                    "label": f"{direction} {strength} correlation between {c1} and {c2} (r={pearson_r:.3f})"
                })

        # Sort by absolute correlation, descending
        pairs.sort(key=lambda x: x["abs_correlation"], reverse=True)
        return pairs[:8]
    except Exception as e:
        return []


def eda_agent_node(state: AgentState) -> AgentState:
    """
    EDA Agent — Statistical Profiling (Tool-First Pattern)

    Computes with NumPy/Pandas/SciPy:
      1. Full descriptive stats per numeric column (mean, std, IQR, skew, kurtosis)
      2. Distribution shape classification and normality test
      3. Pearson + Spearman correlation matrix with strength labels
      4. Categorical distribution summaries (value counts, entropy)
      5. Top outlier columns via Z-score
    LLM receives all computed values and writes 3-bullet analytical narrative.
    """
    logger.info("--> [EDA Agent] Statistical profiling (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    dataset_name = state.get("dataset_name", "Dataset")
    schema_meta = state.get("schema_metadata", {})
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("EDA Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    eda_results = {}
    num_rows, num_cols = df.shape

    try:
        numeric_cols = numeric_analysis_columns(df)
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

        # ──────────────────────────────────────────────────────────────────────
        # 1. Full Descriptive Stats per Numeric Column (stats_tools)
        # ──────────────────────────────────────────────────────────────────────
        column_profiles: Dict[str, Any] = {}
        for col in numeric_cols[:10]:
            profile = compute_descriptive_stats(df, col)
            # Add normality test
            profile["normality"] = _compute_normality(df[col])
            # Add distribution shape label
            if "skewness" in profile and "error" not in profile:
                profile["skewness_label"] = _classify_skewness(profile["skewness"])
                profile["kurtosis_label"] = _classify_kurtosis(profile.get("kurtosis", 0))
            column_profiles[col] = profile

        eda_results["column_profiles"] = column_profiles

        # ──────────────────────────────────────────────────────────────────────
        # 2. Correlation Analysis — Pearson + Spearman (SciPy)
        # ──────────────────────────────────────────────────────────────────────
        correlation_pairs = _compute_mutual_information(df, numeric_cols)
        eda_results["correlation_pairs"] = correlation_pairs

        # Also store the full Pearson correlation matrix for heatmap rendering
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr().round(4)
            eda_results["correlation_matrix"] = corr_matrix.to_dict()

        # ──────────────────────────────────────────────────────────────────────
        # 3. Categorical Distribution Summaries
        # ──────────────────────────────────────────────────────────────────────
        cat_summary: Dict[str, Any] = {}
        for col in categorical_cols[:8]:
            value_counts = df[col].value_counts()
            n_valid = value_counts.sum()
            # Shannon entropy (diversity measure)
            probs = value_counts / n_valid
            entropy = float(-(probs * np.log2(probs + 1e-10)).sum()) if n_valid > 0 else 0

            cat_summary[col] = {
                "unique_count": int(df[col].nunique()),
                "total_valid": int(n_valid),
                "missing_count": int(df[col].isna().sum()),
                "top_categories": value_counts.head(6).to_dict(),
                "top_1_share_pct": round(float(value_counts.iloc[0] / n_valid) * 100.0, 2) if n_valid > 0 else 0,
                "diversity_entropy": round(entropy, 4),
                "is_binary": int(df[col].nunique()) == 2,
            }
        eda_results["categorical_summary"] = cat_summary

        # ──────────────────────────────────────────────────────────────────────
        # 4. Top Outlier Columns (Z-score)
        # ──────────────────────────────────────────────────────────────────────
        outlier_flags: List[Dict] = []
        for col in numeric_cols[:8]:
            z_res = detect_outliers_zscore(df, col)
            if "error" not in z_res and z_res.get("outlier_count", 0) > 0:
                outlier_flags.append({
                    "column": col,
                    "outlier_count": z_res["outlier_count"],
                    "outlier_pct": z_res["outlier_percentage"],
                    "max_zscore": z_res.get("max_zscore"),
                })
        outlier_flags.sort(key=lambda x: x["outlier_pct"], reverse=True)
        eda_results["outlier_flags"] = outlier_flags

        # ──────────────────────────────────────────────────────────────────────
        # 5. High-level dataset overview stats
        # ──────────────────────────────────────────────────────────────────────
        eda_results["overview"] = {
            "rows": num_rows,
            "columns": num_cols,
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
            "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 2),
            "total_missing_pct": round(df.isnull().sum().sum() / (num_rows * num_cols) * 100.0, 2),
        }

        # ──────────────────────────────────────────────────────────────────────
        # 6. LLM Receives Computed Facts → Writes Narrative (NOT computes)
        # ──────────────────────────────────────────────────────────────────────
        # Build a structured fact sheet for the LLM
        distrib_facts = []
        for col, profile in list(column_profiles.items())[:4]:
            if "error" not in profile:
                fact = (
                    f"• {col}: mean={profile.get('mean')}, median={profile.get('median')}, "
                    f"std={profile.get('std')}, skewness={profile.get('skewness')} "
                    f"({profile.get('skewness_label', '')}), "
                    f"kurtosis={profile.get('kurtosis')} ({profile.get('kurtosis_label', '')}), "
                    f"normality: {profile.get('normality', {}).get('verdict', 'N/A')}"
                )
                distrib_facts.append(fact)

        corr_facts = [
            f"• {p['col1']} ↔ {p['col2']}: r={p['pearson_r']}, ρ={p['spearman_r']} → {p['strength']} {p['direction']} (p={p['pearson_p']:.4f})"
            for p in correlation_pairs[:4]
        ]

        top_cat = []
        for col, stats_dict in list(cat_summary.items())[:3]:
            top_val = list(stats_dict["top_categories"].items())[0] if stats_dict["top_categories"] else ("N/A", 0)
            top_cat.append(
                f"• {col}: {stats_dict['unique_count']} unique values, "
                f"top={top_val[0]} ({stats_dict.get('top_1_share_pct', 0):.1f}% share), "
                f"diversity entropy={stats_dict.get('diversity_entropy', 0):.2f}"
            )

        outlier_lead = (
            f"Highest: {outlier_flags[0]['column']} ({outlier_flags[0].get('outlier_pct', 0):.1f}% of values are extreme)"
            if outlier_flags else "No extreme outliers detected."
        )

        prompt = f"""You are a Senior Exploratory Data Analyst writing a briefing for a business analyst.

DATASET: {dataset_name} ({num_rows:,} rows × {num_cols} columns)

EXACT COMPUTED DISTRIBUTION STATISTICS (do NOT change any numbers):
{chr(10).join(distrib_facts) if distrib_facts else "No numeric columns."}

CORRELATION FINDINGS (computed by SciPy):
{chr(10).join(corr_facts) if corr_facts else "No significant correlations detected."}

TOP CATEGORICAL BREAKDOWNS:
{chr(10).join(top_cat) if top_cat else "No categorical columns."}

OUTLIER SUMMARY: {len(outlier_flags)} columns flagged with Z-score > 3σ outliers.
{outlier_lead}

Write exactly 3 analytical bullet points:
1. Most important distribution finding (shape, skew, normality) and what it means analytically
2. Most significant correlation finding and the business hypothesis it suggests
3. One categorical insight and the concentration risk or opportunity it reveals

Be specific — use the exact numbers. Do NOT restate what distributions look like — tell the analyst what it MEANS."""

        insights_text = invoke_llm(
            prompt=prompt,
            system_prompt="You are an expert EDA analyst. Ground every insight in the provided computed statistics.",
            tier="fast_reasoning",
            task="eda",
            temperature=0.15,
        ).strip()

        eda_results["summary_insights"] = insights_text
        execution_steps.append(
            f"EDA Agent: Profiled {len(numeric_cols)} numeric + {len(categorical_cols)} categorical columns. "
            f"Found {len(correlation_pairs)} correlation pairs, {len(outlier_flags)} outlier-flagged columns."
        )

    except Exception as e:
        logger.error(f"EDA Agent failed: {e}")
        errors.append(f"EDA Agent Error: {str(e)}")
        insights_text = f"EDA profiling completed for {dataset_name}."
        eda_results["summary_insights"] = insights_text

    return {
        **state,
        "eda_results": eda_results,
        "eda_insights": eda_results.get("summary_insights", ""),
        "execution_steps": execution_steps,
        "errors": errors,
    }
