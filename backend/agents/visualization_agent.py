"""
visualization_agent.py — Smart Evidence Chart Generator (Phase 2 Upgrade)
==========================================================================
Phase 2 Additions:
  1. Trend Decomposition Chart (Actual + 3M Rolling Avg + STL info)
  2. MoM Growth Bars (green/red color-coded)
  3. Seasonality Profile (monthly performance vs annual avg)
  4. Distribution chart for primary metric (histogram + outlier bounds)
  5. Box plot comparison across top dimension
  6. Uses smart_chart_selector() for any additional data exploration charts

All chart choices are DATA-DRIVEN — based on what the agents actually found.
"""
import json
import logging
from typing import List, Dict, Any
import numpy as np
import pandas as pd

from backend.graph.state import AgentState
from backend.services.date_inference import infer_dates
from backend.services.profiler import numeric_analysis_columns
from backend.tools.charts import (
    create_time_series_chart,
    create_pareto_chart,
    create_waterfall_chart,
    create_bar_comparison,
    create_correlation_heatmap,
    # Phase 2 new charts
    create_mom_growth_chart,
    create_trend_decomposition_chart,
    create_seasonality_chart,
    create_distribution_chart,
    create_box_comparison,
    smart_chart_selector,
)

logger = logging.getLogger(__name__)


def visualization_agent_node(state: AgentState) -> AgentState:
    """
    Visualization Agent — Smart Evidence Charts (Phase 2 Tool-First)

    Chart generation is DATA-DRIVEN — charts are selected based on what agents found:
      1. Trend Decomposition (if trend agent ran + date column exists)
      2. MoM Growth Bars (if trend data has monthly series)
      3. Seasonality Profile (if seasonal pattern detected)
      4. Pareto 80/20 Dual-Axis (if diagnostic found pareto data)
      5. Waterfall Variance Bridge (if period-over-period decomposition ran)
      6. Segment Bar Comparison (always, for primary metric × primary dimension)
      7. Distribution Histogram (for primary metric with outlier bounds)
      8. Box Plot Comparison (if 2-10 unique groups exist in primary dimension)
      9. Correlation Heatmap (if ≥ 2 numeric measures)
    """
    logger.info("--> [Visualization Agent] Generating smart evidence charts (Phase 2)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    diagnostic = state.get("diagnostic_results", {})
    kpi_results = state.get("kpi_results", {})
    trend_results = state.get("trend_results", {})          # Phase 2
    eda_results = state.get("eda_results", {})
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Visualization Agent: DataFrame is empty.")
        return {**state, "charts": [], "errors": errors}

    charts: List[Dict[str, Any]] = []

    try:
        measures = schema_meta.get("recommended_measures", [])
        dimensions = schema_meta.get("recommended_dimensions", [])
        date_col = schema_meta.get("primary_date_column")
        if date_col not in df.columns or infer_dates(df[date_col]) is None:
            date_col = None
        target_metric = diagnostic.get("target_metric") or (measures[0] if measures else None)

        # Diagnostics uses a local frequency measure for text-only datasets.
        # Recreate it locally; never add synthetic columns to the user's dataset.
        if target_metric == "record_count" and target_metric not in df.columns:
            df = df.assign(record_count=1)
        elif target_metric not in df.columns:
            target_metric = None

        # Resolve numeric fallback
        if not target_metric:
            numeric_cols = numeric_analysis_columns(df)
            target_metric = numeric_cols[0] if numeric_cols else None

        dimensions = [c for c in dimensions if c != target_metric]

        def _add_chart(title: str, chart_type: str, fig_dict: Dict[str, Any]):
            if not fig_dict:
                return
            charts.append({
                "title": title,
                "type": chart_type,
                "json": json.dumps(fig_dict),
                "data": fig_dict.get("data", []),
                "layout": fig_dict.get("layout", {}),
            })

        # ── CHART 1: Trend Decomposition (Phase 2) ────────────────────────────
        # Replaces simple time-series line — richer with rolling avg + STL info
        if trend_results.get("available") and "time_series_data" in trend_results:
            ts_data = trend_results["time_series_data"]
            stl_data = trend_results.get("stl_decomposition", {})
            monthly_data = ts_data.get("monthly_data", [])

            if len(monthly_data) >= 2 and date_col:
                metric_label = trend_results.get("primary_metric", target_metric or "Metric")
                td_json = create_trend_decomposition_chart(
                    monthly_data=monthly_data,
                    stl_data=stl_data,
                    metric_name=metric_label,
                    title=f"📈 Trend Decomposition: {metric_label.replace('_', ' ').title()}",
                )
                _add_chart(
                    f"Trend Decomposition ({metric_label.replace('_', ' ').title()})",
                    "trend_decomposition",
                    td_json
                )

        elif date_col and date_col in df.columns and target_metric:
            # Fallback to simple time-series if trend agent didn't run
            ts_json = create_time_series_chart(
                df=df, date_col=date_col, value_col=target_metric,
                title=f"📈 Historical Trajectory: {target_metric.title()}",
            )
            _add_chart(
                f"Historical Trajectory ({target_metric.title()})",
                "time_series",
                ts_json
            )

        # ── CHART 2: MoM Growth Bars (Phase 2) ───────────────────────────────
        if trend_results.get("available") and "time_series_data" in trend_results:
            monthly_data = trend_results["time_series_data"].get("monthly_data", [])
            metric_label = trend_results.get("primary_metric", target_metric or "Metric")
            if len(monthly_data) >= 3:
                mom_json = create_mom_growth_chart(
                    monthly_data=monthly_data,
                    metric_name=metric_label,
                    title=f"📊 Month-over-Month Growth: {metric_label.replace('_', ' ').title()}",
                )
                _add_chart(
                    "Month-over-Month Growth %",
                    "mom_growth",
                    mom_json
                )

        # ── CHART 3: Seasonality Profile (Phase 2) ────────────────────────────
        if trend_results.get("available"):
            seasonality = trend_results.get("seasonality_profile", {})
            if seasonality.get("seasonal_pattern_detected"):
                metric_label = trend_results.get("primary_metric", target_metric or "Metric")
                seas_json = create_seasonality_chart(
                    seasonality_profile=seasonality,
                    metric_name=metric_label,
                    title=f"📅 Seasonal Pattern: {metric_label.replace('_', ' ').title()} by Month",
                )
                _add_chart(
                    "Seasonal Performance by Month",
                    "seasonality",
                    seas_json
                )

        # ── CHART 4: Pareto 80/20 ─────────────────────────────────────────────
        pareto_dict = diagnostic.get("pareto_analysis", {})
        if pareto_dict and target_metric:
            first_dim = list(pareto_dict.keys())[0]
            p_data = pareto_dict[first_dim]
            pareto_json = create_pareto_chart(
                pareto_data=p_data,
                title=f"🎯 Pareto 80/20: {target_metric.title()} by {first_dim.title()}",
            )
            _add_chart(
                f"Pareto 80/20 ({first_dim.title()})",
                "pareto",
                pareto_json
            )

        # ── CHART 5: Waterfall Variance Bridge ───────────────────────────────
        variance_decomp = diagnostic.get("variance_decomposition")
        if variance_decomp and "top_negative_drivers" in variance_decomp:
            drivers = []
            deltas = []
            dim_name = variance_decomp.get("dimension", "Category")
            for d in variance_decomp.get("top_positive_drivers", [])[:3]:
                seg = d.get(dim_name, d.get(list(d.keys())[0], "?"))
                drivers.append(f"{seg} (+)")
                deltas.append(float(d.get("delta", 0)))
            for d in variance_decomp.get("top_negative_drivers", [])[:3]:
                seg = d.get(dim_name, d.get(list(d.keys())[0], "?"))
                drivers.append(f"{seg} (-)")
                deltas.append(float(d.get("delta", 0)))

            if drivers and deltas:
                wf_json = create_waterfall_chart(
                    categories=drivers, deltas=deltas,
                    title=f"🌊 Variance Bridge: {variance_decomp.get('period_1')} → {variance_decomp.get('period_2')}",
                )
                _add_chart(
                    "Period-over-Period Variance Drivers",
                    "waterfall",
                    wf_json
                )

        # ── CHART 6: Segment Bar Comparison ──────────────────────────────────
        if target_metric and dimensions:
            for dim in dimensions[:2]:
                if dim in df.columns and 1 < df[dim].nunique() <= 50:
                    bar_json = create_bar_comparison(
                        df=df, category_col=dim, value_col=target_metric, top_n=10,
                        title=f"📊 Top Segments: {target_metric.title()} by {dim.title()}",
                    )
                    _add_chart(
                        f"Top Segments by {dim.title()}",
                        "bar_comparison",
                        bar_json
                    )
                    break

        # ── CHART 7: Distribution (Phase 2) ───────────────────────────────────
        if target_metric and target_metric in df.columns:
            dist_json = create_distribution_chart(
                df=df, col=target_metric,
                title=f"📐 Distribution: {target_metric.replace('_', ' ').title()} (with Outlier Bounds)",
            )
            _add_chart(
                f"Distribution of {target_metric.replace('_', ' ').title()}",
                "distribution",
                dist_json
            )

        # ── CHART 8: Box Plot Comparison (Phase 2) ────────────────────────────
        if target_metric and dimensions:
            for dim in dimensions[:2]:
                if dim in df.columns and 2 <= df[dim].nunique() <= 10:
                    box_json = create_box_comparison(
                        df=df, group_col=dim, value_col=target_metric,
                        title=f"📦 {target_metric.replace('_', ' ').title()} Spread by {dim.title()}",
                    )
                    _add_chart(
                        f"Distribution Spread by {dim.title()}",
                        "boxplot",
                        box_json
                    )
                    break

        # ── CHART 9: Correlation Heatmap ──────────────────────────────────────
        numeric_cols = numeric_analysis_columns(df)
        if len(numeric_cols) >= 2:
            corr_df = df[numeric_cols[:8]].corr()
            corr_json = create_correlation_heatmap(
                corr_df=corr_df,
                title="🔥 Correlation Matrix of Key Measures",
            )
            _add_chart(
                "Correlation Matrix",
                "heatmap",
                corr_json
            )

        execution_steps.append(
            f"Visualization Agent: Generated {len(charts)} evidence charts "
            f"(Phase 2: trend decomp, MoM growth, seasonality, distribution, box plots)."
        )

    except Exception as e:
        logger.error(f"Visualization Agent failed: {e}")
        errors.append(f"Visualization Agent Error: {str(e)}")

    return {
        **state,
        "charts": charts,
        "execution_steps": execution_steps,
        "errors": errors,
    }
