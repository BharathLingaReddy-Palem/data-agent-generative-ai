"""
trend_agent.py — Time-Series Intelligence Agent
================================================
TOOL-FIRST PATTERN — Phase 2 Addition

Computes with Pandas / statsmodels / scipy:
  1. Monthly & Yearly aggregations (exact sums via Pandas resample)
  2. MoM / YoY growth rates — exact Pandas pct_change()
  3. Rolling averages (3-month, 6-month) — exact Pandas rolling()
  4. STL Decomposition — trend + seasonality + residual (statsmodels)
  5. Mann-Kendall trend test — monotonic trend significance (scipy)
  6. Peak / Trough / Best / Worst period detection
  7. Seasonality classification — which months consistently over/underperform

LLM receives fully-computed time-series evidence and writes a narrative.
LLM NEVER computes growth rates or trend directions.
"""
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.services.date_inference import infer_dates
from backend.services.metric_semantics import metric_aggregation

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Detect date column from df if schema missed it
# ─────────────────────────────────────────────────────────────────────────────
def _find_date_column(df: pd.DataFrame, hint: Optional[str] = None) -> Optional[str]:
    """Find the most likely date column in the DataFrame."""
    if hint and hint in df.columns and infer_dates(df[hint]) is not None:
        return hint

    date_keywords = ["date", "time", "day", "month", "year", "created", "updated", "timestamp", "period"]
    for col in df.columns:
        if any(kw in col.lower() for kw in date_keywords):
            try:
                parsed = infer_dates(df[col])
                if parsed is not None:
                    return col
            except Exception:
                pass

    # Last resort: check datetime dtype columns
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col

    return None


# ─────────────────────────────────────────────────────────────────────────────
# CORE COMPUTATIONS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_time_series(df: pd.DataFrame, date_col: str, metric_col: str) -> Dict[str, Any]:
    """
    Full time-series computation for one metric:
    - Monthly & Yearly aggregations
    - MoM and YoY growth
    - Rolling 3M and 6M averages
    - Peak/Trough detection
    """
    if date_col not in df.columns or metric_col not in df.columns:
        return {"error": f"Required columns ('{date_col}', '{metric_col}') not found in dataset."}

    parsed = infer_dates(df[date_col])
    if parsed is None:
        return {"error": "No validated calendar dates; numeric durations are not dates."}
    clean = df.dropna(subset=[date_col, metric_col]).copy()
    clean[date_col] = parsed.loc[clean.index]
    clean = clean.dropna(subset=[date_col]).sort_values(date_col)

    if len(clean) < 2:
        return {"error": "Insufficient data points for time-series analysis."}

    # Monthly aggregation
    clean["_month"] = clean[date_col].dt.to_period("M")
    aggregation = metric_aggregation(metric_col)
    monthly_values = clean.groupby("_month")[metric_col].agg(aggregation)
    if len(monthly_values) < 2:
        return {"error": "At least two observed calendar months are required for a monthly trend."}
    periods = pd.period_range(monthly_values.index.min(), monthly_values.index.max(), freq="M")
    monthly = monthly_values.reindex(periods).rename_axis("_month").reset_index()
    monthly.columns = ["period", "value"]
    monthly["period_str"] = monthly["period"].astype(str)
    monthly["mom_pct"] = monthly["value"].pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan) * 100.0
    monthly["rolling_3m"] = monthly["value"].rolling(3, min_periods=1).mean()
    monthly["rolling_6m"] = monthly["value"].rolling(6, min_periods=1).mean()

    # Yearly aggregation
    clean["_year"] = clean[date_col].dt.to_period("Y")
    yearly = clean.groupby("_year")[metric_col].agg(aggregation).reset_index()
    yearly.columns = ["period", "value"]
    yearly["period_str"] = yearly["period"].astype(str)
    yearly["yoy_pct"] = yearly["value"].pct_change() * 100.0

    # Peak and trough
    peak_idx = monthly["value"].idxmax()
    trough_idx = monthly["value"].idxmin()
    peak_month = monthly.loc[peak_idx, "period_str"]
    trough_month = monthly.loc[trough_idx, "period_str"]
    peak_value = float(monthly.loc[peak_idx, "value"])
    trough_value = float(monthly.loc[trough_idx, "value"])

    # Latest MoM
    latest_mom = float(monthly["mom_pct"].iloc[-1]) if len(monthly) >= 2 else None
    latest_period = monthly["period_str"].iloc[-1] if len(monthly) > 0 else None

    # Overall trend direction
    if len(monthly) >= 3:
        first_half_avg = float(monthly["value"].iloc[:len(monthly)//2].mean())
        second_half_avg = float(monthly["value"].iloc[len(monthly)//2:].mean())
        trend_direction = "Growing" if second_half_avg > first_half_avg * 1.02 else \
                          "Declining" if second_half_avg < first_half_avg * 0.98 else "Flat"
        trend_pct = round(((second_half_avg - first_half_avg) / (first_half_avg or 1)) * 100.0, 2)
    else:
        trend_direction = "Insufficient data"
        trend_pct = None

    return {
        "metric": metric_col,
        "aggregation": aggregation,
        "date_col": date_col,
        "date_range": f"{clean[date_col].min().date()} to {clean[date_col].max().date()}",
        "total_months": len(monthly),
        "missing_months": int(monthly["value"].isna().sum()),
        "monthly_data": [
            {
                "period": r["period_str"],
                "value": round(float(r["value"]), 2) if pd.notna(r["value"]) else None,
                "mom_pct": round(float(r["mom_pct"]), 2) if not pd.isna(r["mom_pct"]) else None,
                "rolling_3m": round(float(r["rolling_3m"]), 2),
            }
            for _, r in monthly.iterrows()
        ],
        "yearly_data": [
            {
                "year": r["period_str"],
                "value": round(float(r["value"]), 2) if pd.notna(r["value"]) else None,
                "yoy_pct": round(float(r["yoy_pct"]), 2) if not pd.isna(r["yoy_pct"]) else None,
            }
            for _, r in yearly.iterrows()
        ],
        "latest_period": latest_period,
        "latest_mom_pct": round(latest_mom, 2) if latest_mom is not None else None,
        "peak_month": peak_month,
        "peak_value": round(peak_value, 2),
        "trough_month": trough_month,
        "trough_value": round(trough_value, 2),
        "peak_to_trough_drop_pct": round(((trough_value - peak_value) / (peak_value or 1)) * 100.0, 2),
        "trend_direction": trend_direction,
        "trend_pct": trend_pct,
        "overall_total": round(float(monthly["value"].sum()), 2) if aggregation == "sum" else None,
        "overall_avg_monthly": round(float(monthly["value"].mean()), 2),
    }


def _compute_stl_decomposition(df: pd.DataFrame, date_col: str, metric_col: str) -> Dict[str, Any]:
    """
    STL (Seasonal and Trend decomposition using Loess) via statsmodels.
    Splits a time series into: Trend + Seasonal + Residual components.
    Requires at least 2 full seasonal cycles (24 monthly observations).
    """
    try:
        from statsmodels.tsa.seasonal import STL

        if date_col not in df.columns or metric_col not in df.columns:
            return {"available": False, "reason": f"Required columns ('{date_col}', '{metric_col}') not found."}

        clean = df.dropna(subset=[date_col, metric_col]).copy()
        parsed = infer_dates(clean[date_col])
        if parsed is None:
            return {"available": False, "error": "No validated calendar dates.", "reason": "No validated calendar dates."}
        clean[date_col] = parsed
        clean = clean.dropna(subset=[date_col]).sort_values(date_col)

        resampled = clean.set_index(date_col)[metric_col].resample("ME")
        monthly = resampled.sum(min_count=1) if metric_aggregation(metric_col) == "sum" else resampled.mean()

        if len(monthly) < 24:
            return {
                "available": False,
                "reason": f"Only {len(monthly)} monthly periods — need 24+ for reliable seasonal decomposition."
            }

        if monthly.isna().any() or not np.isfinite(monthly).all():
            return {"available": False, "reason": "Missing monthly observations; gaps are not assumed to be zero."}
        if float(monthly.var()) <= 1e-12:
            return {"available": False, "reason": "Constant series has no seasonal variation to decompose."}
        stl = STL(monthly, period=12, robust=True)
        result = stl.fit()

        trend = result.trend
        seasonal = result.seasonal
        residual = result.resid

        # Seasonal strength: how much of variance is seasonal?
        var_residual = float(np.var(residual))
        var_seasonal_residual = float(np.var(seasonal + residual))
        seasonal_strength = max(0.0, min(1.0, 1.0 - var_residual/var_seasonal_residual)) if var_seasonal_residual > 1e-12 else 0.0

        # Which months over/underperform on average?
        monthly_df = pd.DataFrame({
            "date": monthly.index,
            "seasonal_component": seasonal.values
        })
        monthly_df["month_name"] = monthly_df["date"].dt.strftime("%B")
        monthly_seasonal = monthly_df.groupby("month_name")["seasonal_component"].mean()
        peak_season_month = monthly_seasonal.idxmax()
        trough_season_month = monthly_seasonal.idxmin()

        return {
            "available": True,
            "seasonal_strength": round(seasonal_strength, 4),
            "seasonality_label": (
                "Strong Seasonality" if seasonal_strength > 0.6 else
                "Moderate Seasonality" if seasonal_strength > 0.3 else
                "Weak / No Seasonality"
            ),
            "peak_season_month": peak_season_month,
            "trough_season_month": trough_season_month,
            "trend_values_last_6": [round(float(v), 2) for v in trend.iloc[-6:].tolist()],
            "residual_std": round(float(residual.std()), 4),
        }
    except ImportError:
        return {"available": False, "reason": "statsmodels not installed."}
    except Exception as e:
        return {"available": False, "reason": str(e)}


def _compute_mann_kendall(df: pd.DataFrame, date_col: str, metric_col: str) -> Dict[str, Any]:
    """
    Mann-Kendall trend test — tests for a monotonic (consistent) upward or downward trend.
    Non-parametric: works even when data is not normally distributed.
    Returns: trend direction, p-value, and tau (strength).
    """
    try:
        if date_col not in df.columns or metric_col not in df.columns:
            return {"error": f"Required columns ('{date_col}', '{metric_col}') not found."}

        clean = df.dropna(subset=[date_col, metric_col]).copy()
        parsed = infer_dates(clean[date_col])
        if parsed is None:
            return {"available": False, "error": "No validated calendar dates.", "reason": "No validated calendar dates."}
        clean[date_col] = parsed
        clean = clean.dropna(subset=[date_col]).sort_values(date_col)

        resampled = clean.set_index(date_col)[metric_col].resample("ME")
        monthly = resampled.sum(min_count=1) if metric_aggregation(metric_col) == "sum" else resampled.mean()
        if monthly.isna().any() or not np.isfinite(monthly).all():
            return {"error": "Missing monthly observations; trend significance is not computed across gaps."}
        values = monthly.values

        if len(values) < 4:
            return {"error": "Need at least 4 monthly periods for Mann-Kendall test."}

        # Manual Mann-Kendall computation (no external library needed)
        n = len(values)
        s = 0
        for i in range(n - 1):
            for j in range(i + 1, n):
                diff = values[j] - values[i]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        # Variance of S
        _, ties = np.unique(values, return_counts=True)
        var_s = (n * (n - 1) * (2 * n + 5) - np.sum(ties*(ties-1)*(2*ties+5))) / 18.0

        # Z statistic
        if s > 0:
            z = (s - 1) / np.sqrt(var_s)
        elif s < 0:
            z = (s + 1) / np.sqrt(var_s)
        else:
            z = 0.0

        # Two-tailed p-value
        from scipy import stats as scipy_stats
        p_value = 2 * scipy_stats.norm.sf(abs(z))

        # Kendall's tau
        tau = s / (0.5 * n * (n - 1))

        trend = "Increasing" if s > 0 else "Decreasing" if s < 0 else "No trend"
        is_significant = bool(p_value < 0.05)

        return {
            "test": "Mann-Kendall Monotonic Trend Test",
            "trend": trend,
            "tau": round(float(tau), 4),
            "z_statistic": round(float(z), 4),
            "p_value": float(p_value),
            "variance_s": float(var_s),
            "assumptions": "Exploratory trend test with tie correction; assumes independent observations and does not adjust for autocorrelation or seasonality.",
            "p_value_formatted": f"{p_value:.4e}",
            "is_significant": is_significant,
            "conclusion": (
                f"A statistically significant {trend.lower()} trend exists (p={p_value:.4e}, τ={tau:.3f}). "
                f"The trend is {'monotonically ' + trend.lower() + ' over time' if is_significant else 'not clearly directional'}."
                if is_significant else
                f"No statistically significant monotonic trend detected (p={p_value:.4f} ≥ 0.05). "
                f"Evidence is insufficient to conclude a monotonic trend; this does not establish absence of change."
            )
        }
    except Exception as e:
        return {"error": str(e)}


def _compute_seasonality_by_month(df, date_col, metric_col, stl_data=None):
    """Describe mean monthly totals; repetition requires multiple complete cycles."""
    try:
        clean = df.dropna(subset=[date_col, metric_col]).copy()
        parsed = infer_dates(clean[date_col])
        if parsed is None:
            return {"available": False, "error": "No validated calendar dates.", "reason": "No validated calendar dates."}
        clean[date_col] = parsed
        clean = clean.dropna(subset=[date_col])
        resampled = clean.set_index(date_col)[metric_col].resample("ME")
        monthly = resampled.sum(min_count=1) if metric_aggregation(metric_col) == "sum" else resampled.mean()
        observed = monthly.dropna()
        if observed.empty:
            return {"error": "No observed monthly values."}
        averages = observed.groupby(observed.index.month).mean()
        average = float(averages.mean())
        result = {}
        import calendar
        for number, value in averages.items():
            difference = float((value-average)/abs(average)*100) if abs(average) > 1e-12 else None
            result[calendar.month_name[number]] = dict(avg_value=round(float(value), 2),
                pct_vs_annual_avg=round(difference, 2) if difference is not None else None,
                performance="Above Average" if difference is not None and difference > 5 else
                            "Below Average" if difference is not None and difference < -5 else "Average")
        cycles = int(observed.groupby(observed.index.month).size().min()) if len(averages) == 12 else 0
        stl = stl_data if stl_data is not None else _compute_stl_decomposition(df, date_col, metric_col)
        detected = bool(cycles >= 2 and stl.get('available') and stl.get('seasonal_strength', 0) > 0.3)
        best, worst = max(result, key=lambda m: result[m]['avg_value']), min(result, key=lambda m: result[m]['avg_value'])
        return dict(monthly_performance=result, best_month=best, worst_month=worst,
            best_month_uplift_pct=result[best]['pct_vs_annual_avg'], worst_month_drag_pct=result[worst]['pct_vs_annual_avg'],
            above_average_months=[m for m,v in result.items() if v['performance']=='Above Average'],
            below_average_months=[m for m,v in result.items() if v['performance']=='Below Average'],
            seasonal_pattern_detected=detected, repeated_cycles=cycles, basis='mean monthly total',
            interpretation_notice='Descriptive monthly differences alone do not establish recurring seasonality. STL strength is an estimate, not a significance test.',
            reason=None if detected else stl.get('reason', 'Insufficient repeating seasonal strength across complete annual cycles.'))
    except Exception as exc:
        return {"error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN AGENT NODE
# ─────────────────────────────────────────────────────────────────────────────

def trend_agent_node(state: AgentState) -> AgentState:
    """
    Trend Agent — Time-Series Intelligence (Phase 2 — Tool-First)

    Computes with Pandas/statsmodels/scipy:
      1. Monthly & Yearly aggregations with MoM/YoY growth rates
      2. Rolling 3M and 6M averages
      3. Peak/Trough/Best/Worst period detection
      4. STL Decomposition (Trend + Seasonal + Residual) — needs 24+ months
      5. Mann-Kendall monotonic trend significance test
      6. Calendar month seasonality profile (which months consistently over/underperform)

    LLM receives all computed values and writes the time-series narrative.
    """
    logger.info("--> [Trend Agent] Running time-series analysis (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    kpi_results = state.get("kpi_results", {})
    user_question = state.get("user_question") or ""
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Trend Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    # ── Resolve date column ──────────────────────────────────────────────────
    date_col = _find_date_column(df, hint=schema_meta.get("primary_date_column"))

    if not date_col:
        logger.info("Trend Agent: No date column found — skipping time-series analysis.")
        trend_results = {
            "available": False,
            "reason": "No date/time column detected in this dataset. Time-series analysis requires a date column.",
        }
        execution_steps.append("Trend Agent: Skipped — no date column detected.")
        return {
            **state,
            "trend_results": trend_results,
            "execution_steps": execution_steps,
            "errors": errors,
        }

    # ── Resolve primary metric ───────────────────────────────────────────────
    import numpy as np
    raw_measures = schema_meta.get("recommended_measures", [])
    valid_measures = [
        c for c in raw_measures
        if c in df.columns and np.issubdtype(df[c].dtype, np.number)
    ]
    if not valid_measures:
        # Fall back to any numeric column in df
        valid_measures = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]

    if not valid_measures:
        logger.info("Trend Agent: No numeric measure column available — skipping time-series analysis.")
        trend_results = {
            "available": False,
            "reason": "No numeric measure available in this dataset for time-series aggregation.",
        }
        execution_steps.append("Trend Agent: Skipped — no numeric measure available.")
        return {
            **state,
            "trend_results": trend_results,
            "execution_steps": execution_steps,
            "errors": errors,
        }

    primary_metric = valid_measures[0]
    # Prefer the KPI agent's primary metric if available
    if kpi_results.get("primary_metric"):
        kpi_primary = kpi_results["primary_metric"].lower().replace(" ", "_")
        for m in valid_measures:
            if m.lower() == kpi_primary or kpi_primary in m.lower():
                primary_metric = m
                break

    # ── STEP 1: Core Time-Series Stats (Pandas) ──────────────────────────────
    ts_data = _compute_time_series(df, date_col, primary_metric)

    # ── STEP 2: STL Decomposition (statsmodels) ──────────────────────────────
    stl_data = _compute_stl_decomposition(df, date_col, primary_metric)

    # ── STEP 3: Mann-Kendall Trend Test (scipy) ──────────────────────────────
    mk_data = _compute_mann_kendall(df, date_col, primary_metric)

    # ── STEP 4: Monthly Seasonality Profile (Pandas) ─────────────────────────
    seasonality_data = _compute_seasonality_by_month(df, date_col, primary_metric, stl_data)

    # ── STEP 5: Multi-metric MoM for secondary metrics ───────────────────────
    secondary_trends: Dict[str, Any] = {}
    for m in valid_measures[1:3]:
        if m in df.columns and np.issubdtype(df[m].dtype, np.number):
            try:
                t = _compute_time_series(df, date_col, m)
                if "error" not in t:
                    secondary_trends[m] = {
                        "latest_mom_pct": t.get("latest_mom_pct"),
                        "trend_direction": t.get("trend_direction"),
                        "peak_month": t.get("peak_month"),
                    }
            except Exception:
                pass

    # ── STEP 6: Build Evidence Brief → LLM Interprets ────────────────────────
    if "error" in ts_data:
        trend_narrative = f"Time-series analysis could not be completed: {ts_data['error']}"
    else:
        # Structured evidence blocks for LLM
        mom_recent = [
            f"  {r['period']}: {r['mom_pct']:+.1f}% MoM"
            for r in ts_data["monthly_data"][-4:]
            if r.get("mom_pct") is not None
        ]
        yoy_recent = [
            f"  {r['year']}: {r['yoy_pct']:+.1f}% YoY (total={r['value']:,.0f})"
            for r in ts_data["yearly_data"][-3:]
            if r.get("yoy_pct") is not None
        ]
        seasonality_facts = seasonality_data.get("interpretation_notice", "") + " " + str(seasonality_data.get("reason") or "")
        if "error" not in seasonality_data and seasonality_data.get("seasonal_pattern_detected"):
            seasonality_facts = (
                f"Estimated repeating monthly pattern (descriptive, not a significance test): Best month={seasonality_data.get('best_month')} "
                f"(+{seasonality_data.get('best_month_uplift_pct', 0):.1f}% vs avg), "
                f"Worst month={seasonality_data.get('worst_month')} "
                f"({seasonality_data.get('worst_month_drag_pct', 0):.1f}% vs avg). "
                f"Above-avg months: {seasonality_data.get('above_average_months', [])}. "
                f"Below-avg months: {seasonality_data.get('below_average_months', [])}."
            )

        stl_facts = ""
        if stl_data.get("available"):
            stl_facts = (
                f"STL Decomposition: {stl_data['seasonality_label']} detected "
                f"(strength={stl_data['seasonal_strength']:.2f}). "
                f"Peak seasonal month: {stl_data['peak_season_month']}, "
                f"Trough seasonal month: {stl_data['trough_season_month']}."
            )

        mk_facts = ""
        if "error" not in mk_data:
            mk_facts = f"Mann-Kendall Test: {mk_data['conclusion']}"

        secondary_facts = "\n".join([
            f"• {m}: MoM={v.get('latest_mom_pct', 'N/A')}%, Trend={v.get('trend_direction', 'N/A')}"
            for m, v in secondary_trends.items()
        ])

        # Safe string formatting for time series milestones
        pv = ts_data.get('peak_value')
        tv = ts_data.get('trough_value')
        dp = ts_data.get('peak_to_trough_drop_pct')
        tp = ts_data.get('trend_pct')

        peak_val_str = f"{pv:,.2f}" if pv is not None else "N/A"
        trough_val_str = f"{tv:,.2f}" if tv is not None else "N/A"
        drop_str = f"{dp:+.1f}%" if dp is not None else "N/A"
        trend_str = f"{tp:+.1f}%" if tp is not None else "0.0%"

        prompt = f"""You are a Senior Time-Series Business Analyst presenting to executive leadership.

METRIC ANALYZED: {primary_metric}
MONTHLY AGGREGATION: {ts_data.get("aggregation")} (units unspecified; do not invent currency)
DATE RANGE: {ts_data.get('date_range')}
TOTAL MONTHS OF DATA: {ts_data.get('total_months')}
USER QUESTION: {user_question if user_question else "Analyze the time-series trends and identify patterns."}

ALL NUMBERS BELOW WERE COMPUTED BY PYTHON — DO NOT CHANGE ANY VALUES:

RECENT MONTH-OVER-MONTH GROWTH:
{chr(10).join(mom_recent) if mom_recent else "  Insufficient data for MoM"}

YEAR-OVER-YEAR PERFORMANCE:
{chr(10).join(yoy_recent) if yoy_recent else "  Only one year of data available"}

KEY MILESTONES:
  • Peak period: {ts_data.get('peak_month')} (value={peak_val_str})
  • Trough period: {ts_data.get('trough_month')} (value={trough_val_str})
  • Peak-to-trough drop: {drop_str}
  • Latest MoM: {ts_data.get('latest_mom_pct', 'N/A')}%
  • Overall trend: {ts_data.get('trend_direction')} ({trend_str} first-half vs second-half avg)

{stl_facts}

{seasonality_facts}

{mk_facts}

SECONDARY METRICS TRENDS:
{secondary_facts if secondary_facts else "No secondary metrics available."}

Write exactly 3 executive bullet points:
**1. Overall Trend Assessment** — Is the business growing, declining, or flat? State exact MoM/YoY numbers. 
**2. Seasonality & Cyclicality** — Are there recurring patterns? Which months are peak vs trough? Can leadership plan around this?
**3. Strategic Outlook** — Based on the trend test result, is the trend direction statistically confirmed? What should leadership monitor or act on?

Every claim must cite a specific computed number from the evidence above. Do not estimate."""

        try:
            trend_narrative = invoke_llm(
                prompt=prompt,
                system_prompt=(
                    "You are an expert time-series business analyst. "
                    "Ground every claim in the computed numbers. Never invent data points."
                ),
                tier="reasoning",
                task="trend",
                temperature=0.1,
            ).strip()
        except Exception as e:
            logger.warning(f"Trend Agent LLM narrative skipped: {e}")
            trend_narrative = (
                f"Time-series analysis for {primary_metric}: "
                f"Overall trend is {ts_data.get('trend_direction', 'unknown')} "
                f"({trend_str}). "
                f"Latest MoM: {ts_data.get('latest_mom_pct', 'N/A')}%. "
                f"Peak: {ts_data.get('peak_month')}, Trough: {ts_data.get('trough_month')}."
            )

    is_ts_valid = "error" not in ts_data
    trend_results = {
        "available": is_ts_valid,
        "primary_metric": primary_metric,
        "date_col": date_col,
        "time_series_data": ts_data if is_ts_valid else {},
        "stl_decomposition": stl_data,
        "mann_kendall_test": mk_data,
        "seasonality_profile": seasonality_data,
        "secondary_trends": secondary_trends,
        "trend_narrative": trend_narrative,
    }

    if not is_ts_valid:
        trend_results["reason"] = ts_data.get("error", "Time-series computation error.")
        execution_steps.append(f"Trend Agent: Time-series skipped ({ts_data.get('error')}).")
    else:
        execution_steps.append(
            f"Trend Agent: Time-series analysis on '{primary_metric}' over {ts_data.get('total_months', 0)} months. "
            f"Trend={ts_data.get('trend_direction', 'N/A')} | "
            f"MoM={ts_data.get('latest_mom_pct', 'N/A')}% | "
            f"Seasonality={'detected' if stl_data.get('available') else 'insufficient data'}."
        )

    return {
        **state,
        "trend_results": trend_results,
        "execution_steps": execution_steps,
        "errors": errors,
    }
