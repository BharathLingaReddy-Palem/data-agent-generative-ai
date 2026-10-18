"""
comparator.py — Multi-Dataset Comparison Engine (Phase 3)
==========================================================
Enables C-level and senior analysts to compare two datasets:
  - Period vs. Period (e.g., Q1 vs Q2, 2023 vs 2024)
  - Region vs. Region (e.g., North America vs Europe)
  - Scenario vs. Scenario (e.g., Control vs Treatment, Actual vs Forecast)

Computes:
  1. Volume & Schema Reconciliation (records, new/dropped columns)
  2. Metric Deltas (Absolute, %, Direction) for all common numeric fields
  3. Statistical Significance (Welch's t-test, Mann-Whitney U, Cohen's d effect size)
  4. Segment/Category Mix Shift (share change, new/churned segments)
  5. Primary Growth Drivers (Pareto of which segments contributed most to metric delta)
  6. Executive Comparative Briefing via LLM (with deterministic fallback)
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats
from backend.tools.stats_tools import holm_adjust

from backend.services.llm_service import invoke_llm

logger = logging.getLogger(__name__)


def compare_datasets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    name_a: str = "Baseline (Period A)",
    name_b: str = "Comparison (Period B)",
    key_metric_col: Optional[str] = None,
    segment_col: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Performs comprehensive multi-dataset comparative analytics between two DataFrames.
    """
    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        return {
            "status": "error",
            "message": "Both datasets must be non-empty DataFrames for comparison.",
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Volume & Schema Reconciliation
    # ─────────────────────────────────────────────────────────────────────────
    rows_a, cols_a = len(df_a), len(df_a.columns)
    rows_b, cols_b = len(df_b), len(df_b.columns)
    row_delta = rows_b - rows_a
    row_pct = (row_delta / rows_a * 100) if rows_a > 0 else 0.0

    cols_set_a = set(df_a.columns)
    cols_set_b = set(df_b.columns)
    common_cols = sorted(list(cols_set_a.intersection(cols_set_b)))
    dropped_cols = sorted(list(cols_set_a - cols_set_b))
    added_cols = sorted(list(cols_set_b - cols_set_a))

    volume_summary = {
        "name_a": name_a,
        "name_b": name_b,
        "rows_a": rows_a,
        "rows_b": rows_b,
        "row_delta": row_delta,
        "row_pct_change": round(row_pct, 2),
        "direction": "Expanded" if row_delta > 0 else ("Contracted" if row_delta < 0 else "Unchanged"),
        "common_columns_count": len(common_cols),
        "dropped_columns": dropped_cols,
        "added_columns": added_cols,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Numeric Metrics Comparison & Statistical Significance
    # ─────────────────────────────────────────────────────────────────────────
    num_cols_a = set(df_a.select_dtypes(include=[np.number]).columns)
    num_cols_b = set(df_b.select_dtypes(include=[np.number]).columns)
    common_num_cols = sorted(list(num_cols_a.intersection(num_cols_b)))

    # Filter out pure ID-like numeric columns
    filtered_num_cols = [
        c for c in common_num_cols
        if not (c.lower().endswith("id") or c.lower().startswith("id_") or "index" in c.lower())
    ]

    metric_comparisons: List[Dict[str, Any]] = []

    for col in filtered_num_cols:
        s_a = df_a[col].replace([np.inf, -np.inf], np.nan).dropna()
        s_b = df_b[col].replace([np.inf, -np.inf], np.nan).dropna()

        if len(s_a) < 2 or len(s_b) < 2:
            continue

        mean_a, mean_b = float(s_a.mean()), float(s_b.mean())
        sum_a, sum_b = float(s_a.sum()), float(s_b.sum())
        median_a, median_b = float(s_a.median()), float(s_b.median())
        std_a, std_b = float(s_a.std()), float(s_b.std())

        mean_delta = mean_b - mean_a
        mean_pct = (mean_delta / abs(mean_a) * 100) if abs(mean_a) > 1e-9 else 0.0

        sum_delta = sum_b - sum_a
        sum_pct = (sum_delta / abs(sum_a) * 100) if abs(sum_a) > 1e-9 else 0.0

        # Welch's t-test (unequal variance)
        try:
            t_stat, p_val_t = stats.ttest_ind(s_a, s_b, equal_var=False)
            p_val = float(p_val_t) if np.isfinite(p_val_t) and np.isfinite(t_stat) else None
        except Exception:
            p_val = None

        # Mann-Whitney U test (non-parametric)
        try:
            u_stat, p_val_u = stats.mannwhitneyu(s_a, s_b, alternative='two-sided')
            p_val_mann = float(p_val_u) if np.isfinite(p_val_u) else None
        except Exception:
            p_val_mann = None

        is_significant = p_val is not None and p_val < 0.05

        # Cohen's d effect size
        pooled_std = np.sqrt(((len(s_a) - 1) * (std_a ** 2) + (len(s_b) - 1) * (std_b ** 2)) / (len(s_a) + len(s_b) - 2))
        cohens_d = (mean_delta / pooled_std) if (pooled_std and not np.isnan(pooled_std) and pooled_std > 1e-9) else 0.0

        if abs(cohens_d) >= 0.8:
            effect_label = "Large Effect"
        elif abs(cohens_d) >= 0.5:
            effect_label = "Moderate Effect"
        elif abs(cohens_d) >= 0.2:
            effect_label = "Small Effect"
        else:
            effect_label = "Negligible"

        metric_comparisons.append({
            "column": col,
            "mean_a": round(mean_a, 2),
            "mean_b": round(mean_b, 2),
            "mean_delta": round(mean_delta, 2),
            "mean_pct_change": round(mean_pct, 2),
            "sum_a": round(sum_a, 2),
            "sum_b": round(sum_b, 2),
            "sum_delta": round(sum_delta, 2),
            "sum_pct_change": round(sum_pct, 2),
            "median_a": round(median_a, 2),
            "median_b": round(median_b, 2),
            "std_a": round(std_a, 2),
            "std_b": round(std_b, 2),
            "p_value": p_val,
            "test_available": p_val is not None,
            "test_reason": None if p_val is not None else "Degenerate variances or an undefined Welch test; significance is unavailable.",
            "primary_test": "Welch t-test of per-record means",
            "test_estimand": "mean per record, not aggregate sum",
            "p_value_mann_whitney": p_val_mann,
            "is_statistically_significant": is_significant,
            "cohens_d": round(float(cohens_d), 2),
            "effect_size": effect_label,
            "direction": "▲ Up" if mean_delta > 0 else ("▼ Down" if mean_delta < 0 else "— Flat"),
        })

    valid_tests = [m for m in metric_comparisons if m['test_available']]
    for item in metric_comparisons:
        item['p_value_adjusted'] = None
        item['p_value_adjusted_formatted'] = 'Unavailable'
    for item, probability in zip(valid_tests, holm_adjust([m['p_value'] for m in valid_tests])):
        item['p_value_adjusted'] = probability
        item['p_value_adjusted_formatted'] = f'{probability:.4e}'
        item['multiple_testing_correction'] = 'Holm'
        item['is_statistically_significant'] = probability < 0.05

    # Sort metric comparisons: statistically significant first, then largest absolute sum pct change
    metric_comparisons.sort(
        key=lambda m: (not m["is_statistically_significant"], -abs(m["sum_pct_change"]))
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Categorical Mix Shift & Segment Analysis
    # ─────────────────────────────────────────────────────────────────────────
    cat_cols_a = set(df_a.select_dtypes(include=['object', 'category']).columns)
    cat_cols_b = set(df_b.select_dtypes(include=['object', 'category']).columns)
    common_cat_cols = sorted(list(cat_cols_a.intersection(cat_cols_b)))

    # Filter out high-cardinality ID columns (> 50% unique)
    candidate_cat_cols = []
    for c in common_cat_cols:
        uniq_a = df_a[c].nunique()
        uniq_b = df_b[c].nunique()
        if 2 <= uniq_a <= 40 and 2 <= uniq_b <= 40:
            candidate_cat_cols.append(c)

    chosen_segment_col = segment_col if (segment_col and segment_col in candidate_cat_cols) else (
        candidate_cat_cols[0] if candidate_cat_cols else (common_cat_cols[0] if common_cat_cols else None)
    )

    segment_shifts: List[Dict[str, Any]] = []
    new_segments: List[str] = []
    lost_segments: List[str] = []

    if chosen_segment_col:
        vc_a = df_a[chosen_segment_col].dropna().value_counts(normalize=True) * 100
        vc_b = df_b[chosen_segment_col].dropna().value_counts(normalize=True) * 100

        counts_a = df_a[chosen_segment_col].dropna().value_counts()
        counts_b = df_b[chosen_segment_col].dropna().value_counts()

        all_cats = sorted(list(set(vc_a.index).union(set(vc_b.index))))

        for cat in all_cats:
            share_a = float(vc_a.get(cat, 0.0))
            share_b = float(vc_b.get(cat, 0.0))
            count_a = int(counts_a.get(cat, 0))
            count_b = int(counts_b.get(cat, 0))
            share_delta = share_b - share_a

            if count_a == 0 and count_b > 0:
                new_segments.append(str(cat))
            elif count_a > 0 and count_b == 0:
                lost_segments.append(str(cat))

            segment_shifts.append({
                "segment": str(cat),
                "count_a": count_a,
                "count_b": count_b,
                "share_a_pct": round(share_a, 2),
                "share_b_pct": round(share_b, 2),
                "share_delta_pct": round(share_delta, 2),
                "trend": "▲ Share Gained" if share_delta > 0.5 else ("▼ Share Lost" if share_delta < -0.5 else "— Stable"),
            })

        segment_shifts.sort(key=lambda s: -abs(s["share_delta_pct"]))

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Primary Growth / Contraction Drivers (Pareto Contribution)
    # ─────────────────────────────────────────────────────────────────────────
    # Determine primary metric for driver analysis
    chosen_metric = key_metric_col
    if not chosen_metric and metric_comparisons:
        # Pick first significant revenue/sales/profit or highest sum metric
        for m in metric_comparisons:
            col_l = m["column"].lower()
            if any(k in col_l for k in ["revenue", "sales", "profit", "amount", "cost", "total"]):
                chosen_metric = m["column"]
                break
        if not chosen_metric:
            chosen_metric = metric_comparisons[0]["column"]

    growth_drivers: List[Dict[str, Any]] = []
    if chosen_metric and chosen_segment_col and chosen_metric in df_a.columns and chosen_metric in df_b.columns:
        grp_a = df_a.groupby(chosen_segment_col)[chosen_metric].sum()
        grp_b = df_b.groupby(chosen_segment_col)[chosen_metric].sum()
        total_delta = float(df_b[chosen_metric].sum() - df_a[chosen_metric].sum())

        all_segs = set(grp_a.index).union(set(grp_b.index))
        for seg in all_segs:
            val_a = float(grp_a.get(seg, 0.0))
            val_b = float(grp_b.get(seg, 0.0))
            delta = val_b - val_a
            pct_change = (delta / abs(val_a) * 100) if abs(val_a) > 1e-9 else 0.0
            # Contribution to overall change
            contrib_pct = (delta / total_delta * 100) if abs(total_delta) > 1e-9 else 0.0

            growth_drivers.append({
                "segment": str(seg),
                "value_a": round(val_a, 2),
                "value_b": round(val_b, 2),
                "delta": round(delta, 2),
                "pct_growth": round(pct_change, 2),
                "contribution_to_total_change_pct": round(contrib_pct, 2),
            })

        # Sort by absolute delta impact
        growth_drivers.sort(key=lambda d: -abs(d["delta"]))

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Executive Comparative Narrative Generation (LLM + Fallback)
    # ─────────────────────────────────────────────────────────────────────────
    executive_narrative = _generate_comparative_narrative(
        name_a=name_a,
        name_b=name_b,
        volume_summary=volume_summary,
        metric_comparisons=metric_comparisons,
        segment_shifts=segment_shifts,
        growth_drivers=growth_drivers,
        chosen_metric=chosen_metric,
        chosen_segment_col=chosen_segment_col,
    )

    return {
        "status": "success",
        "name_a": name_a,
        "name_b": name_b,
        "volume_summary": volume_summary,
        "metric_comparisons": metric_comparisons,
        "chosen_segment_col": chosen_segment_col,
        "candidate_segment_cols": candidate_cat_cols,
        "segment_shifts": segment_shifts[:10],
        "new_segments": new_segments,
        "lost_segments": lost_segments,
        "chosen_metric": chosen_metric,
        "growth_drivers": growth_drivers[:8],
        "executive_narrative": executive_narrative,
        "significant_metrics_count": sum(1 for m in metric_comparisons if m["is_statistically_significant"]),
    }


def _generate_comparative_narrative(
    name_a: str,
    name_b: str,
    volume_summary: dict,
    metric_comparisons: list,
    segment_shifts: list,
    growth_drivers: list,
    chosen_metric: Optional[str],
    chosen_segment_col: Optional[str],
) -> str:
    """Generates an executive briefing comparing Dataset A and Dataset B."""
    # Build concise evidence block
    top_metrics_evidence = "\n".join([
        f"- {m['column']}: {name_a}={m['sum_a']:,.1f} vs {name_b}={m['sum_b']:,.1f} "
        f"(Delta: {m['sum_delta']:+,.1f}, {m['sum_pct_change']:+.1f}%), "
        f"Significant={m['is_statistically_significant']} for per-record means (Holm-adjusted p={m['p_value_adjusted_formatted']}, effect={m['effect_size']}; test available={m['test_available']})"
        for m in metric_comparisons[:4]
    ])

    top_drivers_evidence = ""
    if growth_drivers:
        top_drivers_evidence = f"Driver analysis on {chosen_metric} by {chosen_segment_col}:\n" + "\n".join([
            f"- {d['segment']}: Delta={d['delta']:+,.1f} ({d['pct_growth']:+.1f}%), Contributed {d['contribution_to_total_change_pct']:+.1f}% of total change"
            for d in growth_drivers[:3]
        ])

    prompt = f"""You are an elite Senior Data Analyst presenting a comparative briefing to the Executive Committee.
Comparing: '{name_a}' (Baseline) vs '{name_b}' (Comparison).

Statistical tests concern per-record means, not aggregate sums. Use Holm-adjusted Welch p-values only for significance; Mann-Whitney is a sensitivity analysis. Results assume independent observations and do not establish causation or the probability of random chance.

Quantitative Findings (ground truth):
1. Volume: {name_a} had {volume_summary['rows_a']:,} records; {name_b} had {volume_summary['rows_b']:,} records ({volume_summary['row_pct_change']:+.1f}% change).
2. Key Metrics:
{top_metrics_evidence}
3. {top_drivers_evidence}

Write a structured 3-part Executive Comparative Briefing:
### 1. 📊 Executive Bottom-Line
(Clear statement of overall growth/contraction, whether key metrics changed significantly, and the financial/operational impact)

### 2. 🔍 What Drove the Difference
(Highlight the specific segments, categories, or drivers that explain the variance between {name_a} and {name_b})

### 3. 🎯 Management Recommendations
(2-3 high-impact tactical actions to sustain gains or address contractions)"""

    try:
        response = invoke_llm(
            prompt=prompt,
            system_prompt="You are a seasoned Chief Analytics Officer. Be direct, authoritative, and ground every conclusion in the provided numbers.",
            task="comparison",
        )
        if response and len(response.strip()) > 100:
            return response.strip()
    except Exception as e:
        logger.warning(f"Comparative LLM briefing generation failed: {e}")

    # Fallback deterministic briefing
    row_delta = volume_summary["row_delta"]
    row_pct = volume_summary["row_pct_change"]
    top_m = metric_comparisons[0] if metric_comparisons else None

    summary = f"""### 1. 📊 Executive Bottom-Line
Comparison between **{name_a}** and **{name_b}** shows transaction volume {volume_summary['direction'].lower()} by **{abs(row_pct):.1f}%** ({abs(row_delta):,} records).
"""
    if top_m:
        sig_str = "unavailable" if not top_m['test_available'] else "statistically significant" if top_m["is_statistically_significant"] else "not statistically significant"
        summary += f"\nThe primary metric **{top_m['column']}** moved from **{top_m['sum_a']:,.1f}** in {name_a} to **{top_m['sum_b']:,.1f}** in {name_b}, representing a **{top_m['sum_pct_change']:+.1f}%** change. The comparison of per-record means is {sig_str} (Holm-adjusted p = {top_m['p_value_adjusted_formatted']}); this does not test the change in totals.\n"

    summary += f"\n### 2. 🔍 What Drove the Difference\n"
    if growth_drivers:
        lead = growth_drivers[0]
        summary += f"The largest single variance driver was segment **{lead['segment']}**, which shifted by **{lead['delta']:+,.1f}** ({lead['pct_growth']:+.1f}%), accounting for **{lead['contribution_to_total_change_pct']:.1f}%** of total metric variance.\n"
    else:
        summary += "Metrics shifted uniformly across categories with no single outlier driver.\n"

    summary += f"""\n### 3. 🎯 Management Recommendations
- **Investigate Key Drivers**: Conduct a granular dive into the top performing and lagging segments.
- **Statistical Monitoring**: Continue monitoring {top_m['column'] if top_m else 'core metrics'} to ensure changes represent structural shifts rather than random variation.
- **Operational Alignment**: Reallocate resources to high-growth segments identified in this comparison."""

    return summary
