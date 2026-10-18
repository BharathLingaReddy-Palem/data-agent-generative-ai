"""
stats_tools.py — Deterministic Statistical Computation Layer
=============================================================
ALL numerical computations happen here with Pandas/NumPy/SciPy.
Agents use these results as ground truth and pass them to LLMs only for interpretation.
The LLM NEVER computes numbers — it only explains them.
"""
import pandas as pd
import numpy as np
import scipy.stats as stats
from typing import Dict, Any, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# OUTLIER DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_outliers_iqr(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """
    Detects outliers using the Interquartile Range (IQR) method.
    Upper fence: Q3 + 1.5*IQR | Lower fence: Q1 - 1.5*IQR
    """
    try:
        vals = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
        if len(vals) < 4:
            return {"error": "Insufficient data for IQR outlier detection."}
        q25 = float(np.percentile(vals, 25))
        q75 = float(np.percentile(vals, 75))
        iqr = q75 - q25
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr

        outlier_mask = (vals < lower_bound) | (vals > upper_bound)
        outliers = vals[outlier_mask]

        return {
            "method": "IQR",
            "column": col,
            "q25": round(q25, 4),
            "q75": round(q75, 4),
            "iqr": round(iqr, 4),
            "lower_bound": round(lower_bound, 4),
            "upper_bound": round(upper_bound, 4),
            "outlier_count": int(len(outliers)),
            "outlier_percentage": round((len(outliers) / len(vals)) * 100.0, 2),
            "max_outlier": round(float(outliers.max()), 4) if len(outliers) > 0 else None,
            "min_outlier": round(float(outliers.min()), 4) if len(outliers) > 0 else None,
        }
    except Exception as e:
        return {"error": str(e)}


# Backwards-compatible alias used by quality_agent
detect_outliers = detect_outliers_iqr


def detect_outliers_zscore(df: pd.DataFrame, col: str, threshold: float = 3.0) -> Dict[str, Any]:
    """
    Detects outliers using Z-score method.
    A point is an outlier if |z| > threshold (default = 3.0 standard deviations).
    More sensitive than IQR for normally distributed data.
    """
    try:
        vals = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
        if len(vals) < 4:
            return {"error": "Insufficient data for Z-score outlier detection."}

        mean = float(vals.mean())
        std = float(vals.std())
        if std == 0:
            return {"error": "Standard deviation is zero — column is constant.", "outlier_count": 0}

        z_scores = np.abs((vals - mean) / std)
        outlier_mask = z_scores > threshold

        return {
            "method": "Z-Score",
            "column": col,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "threshold": threshold,
            "outlier_count": int(outlier_mask.sum()),
            "outlier_percentage": round((outlier_mask.sum() / len(vals)) * 100.0, 2),
            "max_zscore": round(float(z_scores.max()), 4),
            "extreme_values": sorted([round(float(v), 4) for v in vals[outlier_mask].tolist()], reverse=True)[:5],
        }
    except Exception as e:
        return {"error": str(e)}


def outlier_agreement(series):
    """Intersect positional masks, even when the dataframe index is duplicated."""
    vals = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if len(vals) < 4:
        return dict(available=False, count=len(vals), agreed_outlier_count=0, union_outlier_count=0)
    q1, q3 = vals.quantile([0.25, 0.75])
    iqr = ((vals < q1 - 1.5*(q3-q1)) | (vals > q3 + 1.5*(q3-q1))).to_numpy()
    std = float(vals.std(ddof=1))
    zscore = (np.abs((vals.to_numpy()-float(vals.mean()))/std) > 3) if std > 0 else np.zeros(len(vals), dtype=bool)
    return dict(available=True, count=len(vals), agreed_outlier_count=int((iqr & zscore).sum()),
        union_outlier_count=int((iqr | zscore).sum()), iqr_only_count=int((iqr & ~zscore).sum()),
        zscore_only_count=int((zscore & ~iqr).sum()), iqr_count=int(iqr.sum()), zscore_count=int(zscore.sum()),
        lower_bound=float(q1-1.5*(q3-q1)), upper_bound=float(q3+1.5*(q3-q1)))


def detect_outliers_combined(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """
    Runs both IQR and Z-score outlier detection and returns a combined summary.
    IQR catches skewed data; Z-score catches normally distributed extremes.
    """
    iqr_res = detect_outliers_iqr(df, col)
    z_res = detect_outliers_zscore(df, col)

    iqr_count = iqr_res.get("outlier_count", 0)
    z_count = z_res.get("outlier_count", 0)

    agreement = outlier_agreement(df[col])
    agreed_count = agreement["agreed_outlier_count"]
    severity = "Severe" if agreed_count > 0 and (agreed_count / max(len(df[col].dropna()), 1)) > 0.05 else \
               "Moderate" if agreed_count > 0 else "Method disagreement" if agreement['union_outlier_count'] else "No flags" if agreement['available'] else "Unavailable"

    return {
        "column": col,
        "iqr_outliers": iqr_res,
        "zscore_outliers": z_res,
        "agreed_outlier_count": agreed_count,
        "agreement": agreement,
        "severity": severity,
        "verdict": (
            f"{agreed_count} observations in '{col}' are flagged by both rules; {agreement['iqr_only_count']} by IQR only and {agreement['zscore_only_count']} by Z-score only. Flags do not establish data errors."
            if "error" not in iqr_res and "error" not in z_res else
            f"IQR detected {iqr_count} outliers in '{col}'."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# DESCRIPTIVE STATISTICS
# ─────────────────────────────────────────────────────────────────────────────

def compute_descriptive_stats(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """
    Full rich descriptive statistics block for a single numeric column.
    Computes: mean, median, std, skewness, kurtosis, min, max, percentiles,
    coefficient of variation, normality test result.
    """
    try:
        vals = pd.to_numeric(df[col], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
        n = len(vals)
        if n < 4:
            return {"error": f"Too few values in '{col}' for descriptive stats."}

        mean = float(vals.mean())
        median = float(vals.median())
        std = float(vals.std())
        skewness = float(vals.skew())
        kurt = float(vals.kurtosis())
        cv = round((std / mean) * 100.0, 2) if mean != 0 else None

        # Percentiles
        p10 = float(np.percentile(vals, 10))
        p25 = float(np.percentile(vals, 25))
        p75 = float(np.percentile(vals, 75))
        p90 = float(np.percentile(vals, 90))

        # Normality test
        normality_pval = None
        is_normal = None
        try:
            if n <= 5000:
                _, normality_pval = stats.shapiro(vals.sample(min(n, 500), random_state=42))
            else:
                _, normality_pval = stats.normaltest(vals)
            normality_pval = float(normality_pval)
        except Exception:
            pass

        # Distribution shape classification
        if abs(skewness) < 0.5:
            shape = "Symmetric"
        elif skewness > 1.0:
            shape = "Heavy Right Skew (long tail of high values)"
        elif skewness > 0.5:
            shape = "Mild Right Skew"
        elif skewness < -1.0:
            shape = "Heavy Left Skew (long tail of low values)"
        else:
            shape = "Mild Left Skew"

        return {
            "column": col,
            "count": n,
            "mean": round(mean, 4),
            "median": round(median, 4),
            "std": round(std, 4),
            "min": round(float(vals.min()), 4),
            "max": round(float(vals.max()), 4),
            "range": round(float(vals.max() - vals.min()), 4),
            "p10": round(p10, 4),
            "p25": round(p25, 4),
            "p75": round(p75, 4),
            "p90": round(p90, 4),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurt, 4),
            "coefficient_of_variation_pct": cv,
            "distribution_shape": shape,
            "normality_pvalue": normality_pval,
            "is_approximately_normal": is_normal,
            "normality_not_rejected": bool(normality_pval >= 0.05) if normality_pval is not None and np.isfinite(normality_pval) and std > 0 else None,
        }
    except Exception as e:
        return {"error": str(e)}


def compute_group_aggregates(
    df: pd.DataFrame,
    group_col: str,
    metric_col: str,
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Deterministic group-by aggregation: sum, mean, count, share% for each group.
    Returns ranked table with statistical context.
    """
    try:
        clean = df.dropna(subset=[group_col, metric_col])
        grouped = (
            clean.groupby(group_col)[metric_col]
            .agg(["sum", "mean", "median", "count", "std"])
            .reset_index()
        )
        grouped.columns = [group_col, "total", "mean", "median", "count", "std"]
        grouped = grouped.sort_values("total", ascending=False)

        grand_total = grouped["total"].sum()
        grouped["share_pct"] = (grouped["total"] / grand_total * 100.0).round(2)
        grouped["cumulative_pct"] = grouped["share_pct"].cumsum().round(2)

        records = grouped.head(top_n).copy()
        for c in ["total", "mean", "median", "std"]:
            records[c] = records[c].round(4)

        return {
            "group_col": group_col,
            "metric_col": metric_col,
            "total_groups": int(len(grouped)),
            "grand_total": round(float(grand_total), 4),
            "top_groups": records.to_dict(orient="records"),
            "top_1_share_pct": round(float(grouped.iloc[0]["share_pct"]), 2) if len(grouped) > 0 else 0,
            "top_3_share_pct": round(float(grouped.head(3)["share_pct"].sum()), 2) if len(grouped) >= 3 else None,
        }
    except Exception as e:
        return {"error": str(e)}


def compute_mom_yoy(
    df: pd.DataFrame,
    date_col: str,
    metric_col: str,
) -> Dict[str, Any]:
    """
    Computes Month-over-Month (MoM) and Year-over-Year (YoY) growth rates
    for a numeric metric against a date column.
    Returns time-series trend data with exact computed growth rates.
    """
    try:
        clean = df.dropna(subset=[date_col, metric_col]).copy()
        clean[date_col] = pd.to_datetime(clean[date_col], errors="coerce")
        clean = clean.dropna(subset=[date_col])

        if len(clean) == 0:
            return {"error": "No valid date rows for time-series computation."}

        # Monthly aggregation
        clean["_month"] = clean[date_col].dt.to_period("M")
        monthly = clean.groupby("_month")[metric_col].sum().reset_index()
        monthly.columns = ["period", "value"]
        monthly["period"] = monthly["period"].astype(str)
        monthly["mom_pct"] = monthly["value"].pct_change() * 100.0
        monthly["mom_pct"] = monthly["mom_pct"].round(2)

        # Yearly aggregation
        clean["_year"] = clean[date_col].dt.to_period("Y")
        yearly = clean.groupby("_year")[metric_col].sum().reset_index()
        yearly.columns = ["period", "value"]
        yearly["period"] = yearly["period"].astype(str)
        yearly["yoy_pct"] = yearly["value"].pct_change() * 100.0
        yearly["yoy_pct"] = yearly["yoy_pct"].round(2)

        # Latest period stats
        latest_mom = float(monthly["mom_pct"].iloc[-1]) if len(monthly) >= 2 else None
        best_month = monthly.loc[monthly["value"].idxmax(), "period"] if len(monthly) > 0 else None
        worst_month = monthly.loc[monthly["value"].idxmin(), "period"] if len(monthly) > 0 else None

        return {
            "metric_col": metric_col,
            "date_range": f"{clean[date_col].min().date()} to {clean[date_col].max().date()}",
            "monthly_trend": monthly.to_dict(orient="records"),
            "yearly_trend": yearly.to_dict(orient="records"),
            "latest_mom_pct": round(latest_mom, 2) if latest_mom is not None else None,
            "best_month": best_month,
            "worst_month": worst_month,
            "total_months": len(monthly),
            "peak_value": round(float(monthly["value"].max()), 4),
            "trough_value": round(float(monthly["value"].min()), 4),
            "overall_trend": "Growing" if latest_mom and latest_mom > 0 else "Declining" if latest_mom and latest_mom < 0 else "Flat",
        }
    except Exception as e:
        return {"error": str(e)}


def compute_hhi(df: pd.DataFrame, group_col: str, metric_col: str) -> Dict[str, Any]:
    """
    Herfindahl-Hirschman Index (HHI) — measures market/segment concentration.
    HHI = sum of squared market shares.
    HHI < 0.15: Competitive | 0.15-0.25: Moderate | > 0.25: Concentrated
    """
    try:
        clean = df.dropna(subset=[group_col, metric_col])
        shares = clean.groupby(group_col)[metric_col].sum()
        total = shares.sum()
        if total == 0:
            return {"error": "Total metric value is zero."}
        share_fractions = shares / total
        hhi = float((share_fractions ** 2).sum())

        if hhi < 0.15:
            interpretation = "Competitive — no single segment dominates"
        elif hhi < 0.25:
            interpretation = "Moderately concentrated — a few segments drive most value"
        else:
            interpretation = "Highly concentrated — heavy dependence on a few segments (HIGH RISK)"

        return {
            "hhi_score": round(hhi, 4),
            "interpretation": interpretation,
            "top_segment": shares.idxmax(),
            "top_segment_share_pct": round(float(share_fractions.max()) * 100.0, 2),
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# STATISTICAL TESTS
# ─────────────────────────────────────────────────────────────────────────────

def holm_adjust(p_values):
    """Family-wise error control; retain raw p-values separately."""
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    maximum = 0.0
    for rank, index in enumerate(order):
        maximum = max(maximum, min(1.0, float(values[index]) * (len(values)-rank)))
        adjusted[index] = maximum
    return adjusted.tolist()


def two_sample_ttest(
    df: pd.DataFrame, group_col: str, value_col: str, alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Performs Welch's Two-Sample T-Test.
    Includes Cohen's d effect size for practical significance.
    """
    try:
        clean_df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[group_col, value_col])
        groups = clean_df[group_col].value_counts().index.tolist()
        if len(groups) != 2:
            return {"error": f"Group column '{group_col}' needs exactly 2 distinct values."}

        g1_name, g2_name = groups[0], groups[1]
        g1_vals = clean_df[clean_df[group_col] == g1_name][value_col].astype(float)
        g2_vals = clean_df[clean_df[group_col] == g2_name][value_col].astype(float)

        if min(len(g1_vals), len(g2_vals)) < 3:
            return {"error": "Each group requires at least 3 observations."}
        t_stat, p_val = stats.ttest_ind(g1_vals, g2_vals, equal_var=False)
        if not np.isfinite(t_stat) or not np.isfinite(p_val):
            return {"error": "Degenerate group variances make the t-test undefined."}
        is_sig = bool(p_val < alpha)

        # Cohen's d effect size
        pooled_std = np.sqrt(((len(g1_vals)-1)*g1_vals.var() + (len(g2_vals)-1)*g2_vals.var()) / (len(g1_vals)+len(g2_vals)-2))
        cohens_d = float((g1_vals.mean() - g2_vals.mean()) / pooled_std) if pooled_std > 0 else 0.0
        effect_label = "Negligible" if abs(cohens_d) < 0.2 else \
                       "Small" if abs(cohens_d) < 0.5 else \
                       "Medium" if abs(cohens_d) < 0.8 else "Large"

        return {
            "test": "Welch's Two-Sample T-Test",
            "group_col": group_col,
            "value_col": value_col,
            "group_1": {"name": str(g1_name), "mean": round(float(g1_vals.mean()), 4), "std": round(float(g1_vals.std()), 4), "count": int(len(g1_vals))},
            "group_2": {"name": str(g2_name), "mean": round(float(g2_vals.mean()), 4), "std": round(float(g2_vals.std()), 4), "count": int(len(g2_vals))},
            "mean_difference": round(float(g1_vals.mean() - g2_vals.mean()), 4),
            "pct_difference": round(((g1_vals.mean() - g2_vals.mean()) / (g2_vals.mean() or 1)) * 100.0, 2),
            "t_statistic": round(float(t_stat), 4),
            "p_value": float(p_val),
            "p_value_formatted": f"{p_val:.4e}",
            "statistically_significant": is_sig,
            "significance_level": alpha,
            "cohens_d": round(cohens_d, 4),
            "effect_size_label": effect_label,
            "conclusion": (
                f"The difference between '{g1_name}' (mean={g1_vals.mean():.4f}) and '{g2_name}' "
                f"(mean={g2_vals.mean():.4f}) IS statistically significant (p = {p_val:.4e} < {alpha}). "
                f"Effect size: {effect_label} (Cohen's d = {cohens_d:.2f})."
                if is_sig else
                f"No statistically significant difference between '{g1_name}' (mean={g1_vals.mean():.4f}) "
                f"and '{g2_name}' (mean={g2_vals.mean():.4f}) (p = {p_val:.4f} >= {alpha})."
            )
        }
    except Exception as e:
        return {"error": str(e)}


def mannwhitney_test(
    df: pd.DataFrame, group_col: str, value_col: str, alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Mann-Whitney U Test (non-parametric alternative to t-test).
    Use when data is not normally distributed. More robust to skewed data.
    """
    try:
        clean_df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[group_col, value_col])
        groups = clean_df[group_col].value_counts().index.tolist()
        if len(groups) != 2:
            return {"error": "Need exactly 2 groups for Mann-Whitney test."}

        g1_vals = clean_df[clean_df[group_col] == groups[0]][value_col].astype(float)
        g2_vals = clean_df[clean_df[group_col] == groups[1]][value_col].astype(float)

        if min(len(g1_vals), len(g2_vals)) < 3:
            return {"error": "Each group requires at least 3 observations."}
        u_stat, p_val = stats.mannwhitneyu(g1_vals, g2_vals, alternative="two-sided")
        is_sig = bool(p_val < alpha)

        # Common language effect size (probability of superiority)
        cls_effect = float(u_stat) / (len(g1_vals) * len(g2_vals))

        return {
            "test": "Mann-Whitney U Test (Non-Parametric)",
            "group_col": group_col,
            "value_col": value_col,
            "group_1": {"name": str(groups[0]), "median": round(float(g1_vals.median()), 4), "count": int(len(g1_vals))},
            "group_2": {"name": str(groups[1]), "median": round(float(g2_vals.median()), 4), "count": int(len(g2_vals))},
            "u_statistic": round(float(u_stat), 4),
            "p_value": float(p_val),
            "p_value_formatted": f"{p_val:.4e}",
            "statistically_significant": is_sig,
            "significance_level": alpha,
            "common_language_effect_size": round(cls_effect, 4),
            "conclusion": (
                f"Mann-Whitney confirms a statistically significant rank difference between "
                f"'{groups[0]}' and '{groups[1]}' (p = {p_val:.4e})."
                if is_sig else
                f"No significant rank-order difference between '{groups[0]}' and '{groups[1]}' (p = {p_val:.4f})."
            )
        }
    except Exception as e:
        return {"error": str(e)}


def one_way_anova(
    df: pd.DataFrame, group_col: str, value_col: str, alpha: float = 0.05
) -> Dict[str, Any]:
    """
    One-Way ANOVA: tests whether means of 3+ groups are significantly different.
    Use when comparing more than 2 groups.
    """
    try:
        clean_df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[group_col, value_col])
        groups = clean_df[group_col].unique()
        if len(groups) < 3:
            return {"error": f"ANOVA requires 3+ groups, found {len(groups)}."}

        group_samples = [
            clean_df[clean_df[group_col] == g][value_col].astype(float).values
            for g in groups
        ]
        if min(map(len, group_samples)) < 3:
            return {"error": "Each ANOVA group requires at least 3 observations."}
        f_stat, p_val = stats.f_oneway(*group_samples)
        if not np.isfinite(f_stat) or not np.isfinite(p_val):
            return {"error": "Degenerate group variances make ANOVA undefined."}
        is_sig = bool(p_val < alpha)

        group_stats = {
            str(g): {
                "mean": round(float(clean_df[clean_df[group_col] == g][value_col].mean()), 4),
                "std": round(float(clean_df[clean_df[group_col] == g][value_col].std()), 4),
                "count": int((clean_df[group_col] == g).sum()),
            }
            for g in groups
        }

        return {
            "test": "One-Way ANOVA",
            "assumptions": "Independent observations, approximately normal within-group errors and equal variances; exploratory group comparison.",
            "group_col": group_col,
            "value_col": value_col,
            "n_groups": int(len(groups)),
            "f_statistic": round(float(f_stat), 4),
            "p_value": float(p_val),
            "p_value_formatted": f"{p_val:.4e}",
            "statistically_significant": is_sig,
            "significance_level": alpha,
            "group_stats": group_stats,
            "conclusion": (
                f"ANOVA reveals at least one group mean is significantly different across {len(groups)} groups "
                f"(F = {f_stat:.4f}, p = {p_val:.4e})."
                if is_sig else
                f"No significant difference in means across {len(groups)} groups (F = {f_stat:.4f}, p = {p_val:.4f})."
            )
        }
    except Exception as e:
        return {"error": str(e)}


def chi_square_test(
    df: pd.DataFrame, col1: str, col2: str, alpha: float = 0.05
) -> Dict[str, Any]:
    """
    Pearson's Chi-Square Test of Independence between two categorical columns.
    Includes Cramér's V effect size.
    """
    try:
        clean_df = df.dropna(subset=[col1, col2])
        contingency = pd.crosstab(clean_df[col1], clean_df[col2])
        if contingency.shape[0] < 2 or contingency.shape[1] < 2:
            return {"error": "Contingency table must be at least 2x2."}

        chi2, p_val, dof, expected = stats.chi2_contingency(contingency, correction=False)
        if (expected < 1).any() or (expected < 5).mean() > 0.2:
            return {"error": "Expected cell counts are too small for the chi-square approximation; use an exact test or more data."}
        is_sig = bool(p_val < alpha)

        # Cramér's V effect size
        n = float(contingency.sum().sum())
        cramers_v = float(np.sqrt(chi2 / (n * (min(contingency.shape) - 1)))) if n > 0 else 0.0
        cramers_label = "Negligible" if cramers_v < 0.1 else \
                        "Weak" if cramers_v < 0.3 else \
                        "Moderate" if cramers_v < 0.5 else "Strong"

        return {
            "test": "Chi-Square Test of Independence",
            "col1": col1,
            "col2": col2,
            "chi2_statistic": round(float(chi2), 4),
            "p_value": float(p_val),
            "p_value_formatted": f"{p_val:.4e}",
            "degrees_of_freedom": int(dof),
            "statistically_significant": is_sig,
            "significance_level": alpha,
            "cramers_v": round(cramers_v, 4),
            "association_strength": cramers_label,
            "conclusion": (
                f"Significant association between '{col1}' and '{col2}' (χ²={chi2:.4f}, p={p_val:.4e}). "
                f"Association strength: {cramers_label} (Cramér's V = {cramers_v:.3f})."
                if is_sig else
                f"No significant association between '{col1}' and '{col2}' (p = {p_val:.4f})."
            )
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# PARETO & DECOMPOSITION
# ─────────────────────────────────────────────────────────────────────────────

def pareto_analysis(
    df: pd.DataFrame, category_col: str, value_col: str, top_n: int = 15
) -> Dict[str, Any]:
    """
    Pareto 80/20 analysis: finds categories responsible for 80% of the metric.
    Returns structured contribution table with share % and cumulative %.
    """
    try:
        clean_df = df.dropna(subset=[category_col, value_col])
        grouped = (
            clean_df.groupby(category_col)[value_col]
            .sum()
            .reset_index()
            .sort_values(by=value_col, ascending=False)
        )
        total_val = grouped[value_col].sum()
        if total_val <= 0 or (clean_df[value_col] < 0).any():
            return {"error": "Pareto analysis requires non-negative contributions and a positive total."}

        grouped["share_pct"] = (grouped[value_col] / total_val) * 100.0
        grouped["cumulative_pct"] = grouped["share_pct"].cumsum()

        # Include the first category that reaches or crosses the threshold.
        cutoff = int(np.searchsorted(grouped["cumulative_pct"].to_numpy(), 80.0 - 1e-10)) + 1
        top_80_cats = grouped.iloc[:cutoff]

        cutoff_count = len(top_80_cats)
        total_cats = len(grouped)
        concentration_ratio = round((cutoff_count / total_cats) * 100.0, 2) if total_cats > 0 else 0

        records = grouped.head(top_n).copy()
        records[value_col] = records[value_col].round(2)
        records["share_pct"] = records["share_pct"].round(2)
        records["cumulative_pct"] = records["cumulative_pct"].round(2)

        return {
            "total_value": round(float(total_val), 2),
            "total_categories": total_cats,
            "categories_driving_80pct": cutoff_count,
            "concentration_ratio_pct": concentration_ratio,
            "pareto_rule_holds": concentration_ratio <= 30.0,
            "top_categories": records.to_dict(orient="records"),
            "summary": (
                f"{cutoff_count} out of {total_cats} categories ({concentration_ratio}%) "
                f"drive 80% of total {value_col}."
            )
        }
    except Exception as e:
        return {"error": str(e)}


def delta_decomposition(
    df: pd.DataFrame,
    time_col: str,
    metric_col: str,
    dimension_col: str,
    period_1: Any,
    period_2: Any,
) -> Dict[str, Any]:
    """
    Decomposes the metric change between period_1 and period_2 across dimension_col.
    Identifies which segments drove growth vs. decline with exact contribution %.
    """
    try:
        p1_df = df[df[time_col] == period_1].groupby(dimension_col)[metric_col].sum()
        p2_df = df[df[time_col] == period_2].groupby(dimension_col)[metric_col].sum()

        combined = pd.DataFrame({"p1": p1_df, "p2": p2_df}).fillna(0)
        combined["delta"] = combined["p2"] - combined["p1"]
        total_delta = combined["delta"].sum()

        if total_delta != 0:
            combined["contribution_pct"] = (combined["delta"] / abs(total_delta)) * 100.0
        else:
            combined["contribution_pct"] = 0.0

        combined = combined.sort_values(by="delta", ascending=False)

        top_positive = combined[combined["delta"] > 0].head(5).reset_index().to_dict(orient="records")
        top_negative = (
            combined[combined["delta"] < 0]
            .tail(5)
            .sort_values(by="delta", ascending=True)
            .reset_index()
            .to_dict(orient="records")
        )

        p1_total = float(combined["p1"].sum())
        p2_total = float(combined["p2"].sum())
        growth_pct = round(((p2_total - p1_total) / (p1_total or 1)) * 100.0, 2)

        return {
            "period_1": str(period_1),
            "period_2": str(period_2),
            "dimension": dimension_col,
            "metric": metric_col,
            "total_p1": round(p1_total, 2),
            "total_p2": round(p2_total, 2),
            "total_delta": round(float(total_delta), 2),
            "growth_pct": growth_pct,
            "trend": "Growth" if total_delta > 0 else "Decline" if total_delta < 0 else "Flat",
            "top_positive_drivers": top_positive,
            "top_negative_drivers": top_negative,
            "summary": (
                f"From {period_1} to {period_2}: {metric_col} changed by "
                f"{'+' if total_delta >= 0 else ''}{total_delta:.2f} ({growth_pct:+.2f}%)."
            )
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# DATA QUALITY TOOLS
# ─────────────────────────────────────────────────────────────────────────────

def detect_type_anomalies(df: pd.DataFrame, col: str) -> Dict[str, Any]:
    """
    Detects type inconsistencies in object/mixed columns.
    e.g. a 'revenue' column with embedded strings like '$1,234' or 'N/A'.
    """
    try:
        vals = df[col].dropna()
        if len(vals) == 0:
            return {"column": col, "issues": [], "clean": True}

        issues = []
        # Check if numeric-looking strings have non-numeric content
        if df[col].dtype == object:
            numeric_parseable = pd.to_numeric(vals, errors="coerce").notna().sum()
            total = len(vals)
            if numeric_parseable / total > 0.5 and numeric_parseable < total:
                non_parseable = total - numeric_parseable
                issues.append({
                    "type": "Mixed numeric-string",
                    "detail": f"{non_parseable} values cannot be parsed as numbers in a mostly-numeric column",
                    "severity": "High"
                })

        return {
            "column": col,
            "dtype": str(df[col].dtype),
            "issues": issues,
            "clean": len(issues) == 0,
        }
    except Exception as e:
        return {"error": str(e)}


def detect_zero_variance_columns(df: pd.DataFrame) -> List[str]:
    """
    Identifies columns with zero or near-zero variance (constant or near-constant).
    These columns carry no analytical value.
    """
    zero_var = []
    for col in df.columns:
        if df[col].dtype in [np.float64, np.int64, float, int]:
            if df[col].std() == 0:
                zero_var.append(col)
        elif df[col].dtype == object:
            if df[col].nunique() <= 1:
                zero_var.append(col)
    return zero_var


def detect_high_cardinality_categoricals(df: pd.DataFrame, threshold_ratio: float = 0.5) -> List[Dict]:
    """
    Finds categorical columns with suspiciously high cardinality
    (e.g. a 'Region' column with 9000 unique values in a 10,000 row dataset).
    These may be misclassified IDs or free-text fields.
    """
    issues = []
    for col in df.select_dtypes(include=["object", "category"]).columns:
        n = len(df)
        unique = df[col].nunique()
        ratio = unique / n
        if ratio > threshold_ratio and unique > 10:
            issues.append({
                "column": col,
                "unique_values": unique,
                "total_rows": n,
                "cardinality_ratio": round(ratio, 3),
                "warning": f"'{col}' has {unique:,} unique values ({ratio:.1%} of rows) — may be an ID column, not a dimension."
            })
    return issues
