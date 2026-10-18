"""
charts.py — Smart Chart Library (Phase 2 Upgrade)
==================================================
Phase 2 Additions:
  1. create_trend_decomposition_chart() — STL trend + seasonal overlay
  2. create_mom_growth_chart()          — MoM growth bars with color gradient
  3. create_seasonality_radar()         — Monthly performance vs annual average
  4. create_distribution_chart()        — Histogram + KDE with outlier markers
  5. create_box_comparison()            — Box plots across segments
  6. smart_chart_selector()             — Auto-picks right chart from data semantics

All existing charts preserved and upgraded to consistent dark-mode styling.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from backend.config import CHARTS_DIR

# ── Shared Theme ──────────────────────────────────────────────────────────────
_DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0f172a",
    plot_bgcolor="#0f172a",
    font=dict(color="#e2e8f0", family="Inter, sans-serif", size=13),
    margin=dict(l=50, r=50, t=65, b=50),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(0,0,0,0)",
    ),
    xaxis=dict(gridcolor="#1e3a5f", linecolor="#334155"),
    yaxis=dict(gridcolor="#1e3a5f", linecolor="#334155"),
)

_COLORS = {
    "primary": "#3b82f6",
    "success": "#10b981",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "purple": "#8b5cf6",
    "cyan": "#06b6d4",
}


def save_fig_json(fig: go.Figure, filename: str) -> str:
    """Saves Plotly figure to CHARTS_DIR as JSON and returns path."""
    filepath = CHARTS_DIR / f"{filename}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(fig.to_json())
    return str(filepath)


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING CHARTS (upgraded with consistent dark theme)
# ─────────────────────────────────────────────────────────────────────────────

def create_time_series_chart(
    df: pd.DataFrame,
    date_col: str,
    value_col: str,
    group_col: Optional[str] = None,
    title: str = "Trend Analysis",
) -> Dict[str, Any]:
    """Interactive line chart for temporal trends with rolling average overlay."""
    from backend.services.date_inference import infer_dates
    from backend.services.metric_semantics import metric_aggregation
    parsed = infer_dates(df[date_col])
    if parsed is None or parsed.dt.to_period('M').nunique() < 2:
        return {}
    clean_df = df.copy()
    clean_df[date_col] = parsed
    clean_df = clean_df.dropna(subset=[date_col, value_col]).sort_values(by=date_col)

    if group_col and group_col in clean_df.columns:
        agg = clean_df.groupby(
            [pd.Grouper(key=date_col, freq="ME"), group_col]
        )[value_col].agg(metric_aggregation(value_col)).reset_index()
        fig = px.line(agg, x=date_col, y=value_col, color=group_col, title=title, markers=True)
    else:
        agg = clean_df.groupby(pd.Grouper(key=date_col, freq="ME"))[value_col].agg(metric_aggregation(value_col)).reset_index()
        fig = px.line(agg, x=date_col, y=value_col, title=title, markers=True,
                      color_discrete_sequence=[_COLORS["primary"]])

        # Add 3-month rolling average overlay
        if len(agg) >= 3:
            agg["rolling_3m"] = agg[value_col].rolling(3, min_periods=1).mean()
            fig.add_scatter(
                x=agg[date_col], y=agg["rolling_3m"],
                mode="lines", name="3M Rolling Avg",
                line=dict(color=_COLORS["warning"], width=2, dash="dash"),
            )

    layout = dict(**_DARK_LAYOUT)
    layout["xaxis_title"] = date_col
    layout["yaxis_title"] = value_col
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_pareto_chart(
    pareto_data: Dict[str, Any],
    title: str = "Pareto 80/20 Analysis",
) -> Dict[str, Any]:
    """Dual-axis Pareto chart: bar (volume) + line (cumulative %)."""
    top_cats = pareto_data.get("top_categories", [])
    if not top_cats:
        return {}

    cats = [str(r[list(r.keys())[0]]) for r in top_cats]
    vals = [r[list(r.keys())[1]] for r in top_cats]
    cum_pct = [r.get("cumulative_pct", 0) for r in top_cats]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=cats, y=vals, name="Volume", marker_color=_COLORS["primary"],
               opacity=0.85),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=cats, y=cum_pct, name="Cumulative %",
                   line=dict(color=_COLORS["danger"], width=3),
                   mode="lines+markers",
                   marker=dict(size=7, color=_COLORS["danger"])),
        secondary_y=True,
    )
    fig.add_hline(y=80, line_dash="dash", line_color=_COLORS["success"],
                  secondary_y=True, annotation_text="80% Cutoff",
                  annotation_position="bottom right")

    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title
    fig.update_layout(**layout)
    fig.update_yaxes(title_text="Metric Value", secondary_y=False, gridcolor="#1e3a5f")
    fig.update_yaxes(title_text="Cumulative %", range=[0, 105], secondary_y=True)
    return json.loads(fig.to_json())


def create_waterfall_chart(
    categories: List[str],
    deltas: List[float],
    title: str = "Variance Drivers (Waterfall)",
) -> Dict[str, Any]:
    """Waterfall chart showing period-over-period positive/negative contributions."""
    fig = go.Figure(
        go.Waterfall(
            name="Impact",
            orientation="v",
            measure=["relative"] * len(categories),
            x=categories,
            textposition="outside",
            text=[f"{'+' if d > 0 else ''}{d:,.1f}" for d in deltas],
            y=deltas,
            connector={"line": {"color": "#334155"}},
            decreasing={"marker": {"color": _COLORS["danger"]}},
            increasing={"marker": {"color": _COLORS["success"]}},
        )
    )
    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_bar_comparison(
    df: pd.DataFrame,
    category_col: str,
    value_col: str,
    top_n: int = 10,
    title: str = "Segment Comparison",
) -> Dict[str, Any]:
    """Sorted horizontal bar chart for top contributors."""
    if category_col == value_col:
        return {}  # Comparing a measurement to itself is a tautology.
    from backend.services.metric_semantics import metric_aggregation
    agg = (
        df.groupby(category_col)[value_col]
        .agg(metric_aggregation(value_col))
        .reset_index()
        .sort_values(by=value_col, ascending=False)
        .head(top_n)
    )
    fig = px.bar(
        agg, x=value_col, y=category_col, orientation="h", title=title,
        color=value_col,
        color_continuous_scale=[[0, "#1e3a5f"], [0.5, "#3b82f6"], [1, "#06b6d4"]],
    )
    layout = dict(**_DARK_LAYOUT)
    layout["yaxis"] = {"categoryorder": "total ascending", "gridcolor": "#1e3a5f"}
    layout["coloraxis_showscale"] = False
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_correlation_heatmap(
    corr_df: pd.DataFrame,
    title: str = "Correlation Matrix",
) -> Dict[str, Any]:
    """Annotated Pearson correlation heatmap."""
    fig = px.imshow(
        corr_df.round(2), text_auto=True, aspect="auto",
        color_continuous_scale="RdBu_r", range_color=[-1, 1], title=title,
    )
    layout = dict(**_DARK_LAYOUT)
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 NEW CHARTS
# ─────────────────────────────────────────────────────────────────────────────

def create_mom_growth_chart(
    monthly_data: List[Dict[str, Any]],
    metric_name: str,
    title: str = "Month-over-Month Growth %",
) -> Dict[str, Any]:
    """
    Bar chart showing MoM growth % per month.
    Green bars = positive growth, Red bars = negative growth.
    Includes a zero baseline reference line.
    """
    periods = [r["period"] for r in monthly_data if r.get("mom_pct") is not None]
    mom_pcts = [r["mom_pct"] for r in monthly_data if r.get("mom_pct") is not None]

    if not periods:
        return {}

    colors = [_COLORS["success"] if v >= 0 else _COLORS["danger"] for v in mom_pcts]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=periods, y=mom_pcts,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in mom_pcts],
        textposition="outside",
        name="MoM Growth %",
    ))
    fig.add_hline(y=0, line_color="#64748b", line_width=1)

    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title
    layout["yaxis_title"] = "MoM Growth %"
    layout["xaxis_title"] = "Month"
    layout["xaxis"] = dict(tickangle=-45, gridcolor="#1e3a5f")
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_trend_decomposition_chart(
    monthly_data: List[Dict[str, Any]],
    stl_data: Dict[str, Any],
    metric_name: str,
    title: str = "Trend & Seasonality Decomposition",
) -> Dict[str, Any]:
    """
    2-panel chart:
      Top: Actual values + Rolling 3M average (trend line)
      Bottom: MoM growth bars with color-coded positive/negative
    Shows the decomposed trend clearly.
    """
    if not monthly_data:
        return {}

    periods = [r["period"] for r in monthly_data]
    values = [r["value"] for r in monthly_data]
    rolling_3m = [r.get("rolling_3m") for r in monthly_data]
    mom_pcts = [r.get("mom_pct") for r in monthly_data]

    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=["Actual Values + 3-Month Trend", "Month-over-Month Growth %"],
        row_heights=[0.65, 0.35],
        shared_xaxes=True,
        vertical_spacing=0.08,
    )

    # Top panel: Actual + Rolling avg
    fig.add_trace(go.Scatter(
        x=periods, y=values, mode="lines+markers",
        name="Actual", line=dict(color=_COLORS["primary"], width=2),
        marker=dict(size=5),
    ), row=1, col=1)

    if any(r is not None for r in rolling_3m):
        fig.add_trace(go.Scatter(
            x=periods, y=rolling_3m, mode="lines",
            name="3M Rolling Avg", line=dict(color=_COLORS["warning"], width=2, dash="dash"),
        ), row=1, col=1)

    # Bottom panel: MoM growth bars
    colors = [_COLORS["success"] if v is not None and v >= 0 else _COLORS["danger"] if v is not None else "#64748b" for v in mom_pcts[1:]]
    fig.add_trace(go.Bar(
        x=periods[1:], y=mom_pcts[1:],
        marker_color=colors,
        name="MoM %",
        showlegend=False,
    ), row=2, col=1)

    # Add seasonality annotation if available
    if stl_data.get("available"):
        fig.add_annotation(
            text=f"Seasonality: {stl_data.get('seasonality_label')} (strength={stl_data.get('seasonal_strength', 0):.2f})",
            x=0.01, y=1.08, xref="paper", yref="paper",
            showarrow=False, font=dict(size=11, color=_COLORS["cyan"]),
            align="left",
        )

    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title
    layout["height"] = 520
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_seasonality_chart(
    seasonality_profile: Dict[str, Any],
    metric_name: str,
    title: str = "Monthly Seasonality Profile",
) -> Dict[str, Any]:
    """
    Bar chart showing each calendar month's average performance vs annual average.
    Green = above average, Red = below average.
    """
    monthly_perf = seasonality_profile.get("monthly_performance", {})
    if not monthly_perf:
        return {}

    month_order = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]

    months = [m for m in month_order if m in monthly_perf and monthly_perf[m].get("pct_vs_annual_avg") is not None]
    if not months:
        return {}
    pcts = [monthly_perf[m]["pct_vs_annual_avg"] for m in months]
    colors = [
        _COLORS["success"] if monthly_perf[m]["performance"] == "Above Average"
        else _COLORS["danger"] if monthly_perf[m]["performance"] == "Below Average"
        else "#64748b"
        for m in months
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=months, y=pcts,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in pcts],
        textposition="outside",
        name="vs Annual Avg %",
    ))
    fig.add_hline(y=0, line_color="#64748b", line_width=1)

    best = seasonality_profile.get("best_month")
    worst = seasonality_profile.get("worst_month")
    if best:
        fig.add_annotation(
            text=f"🟢 Peak: {best}",
            x=best, y=max(pcts) + 3,
            showarrow=False, font=dict(color=_COLORS["success"], size=11),
        )
    if worst:
        fig.add_annotation(
            text=f"🔴 Trough: {worst}",
            x=worst, y=min(pcts) - 3,
            showarrow=False, font=dict(color=_COLORS["danger"], size=11),
        )

    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title
    layout["yaxis_title"] = "% vs Annual Average"
    layout["xaxis_title"] = "Calendar Month"
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_distribution_chart(
    df: pd.DataFrame,
    col: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Histogram with KDE overlay. Marks outlier threshold lines (±3σ).
    Shows mean and median reference lines.
    """
    vals = df[col].dropna().astype(float)
    if len(vals) < 4:
        return {}

    mean_val = float(vals.mean())
    std_val = float(vals.std())
    median_val = float(vals.median())

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=vals, nbinsx=30,
        name="Distribution",
        marker_color=_COLORS["primary"],
        opacity=0.7,
        histnorm="probability density",
    ))

    # Mean line
    fig.add_vline(x=mean_val, line_color=_COLORS["warning"],
                  line_dash="solid", line_width=2,
                  annotation_text=f"Mean: {mean_val:.2f}",
                  annotation_position="top right")
    # Median line
    fig.add_vline(x=median_val, line_color=_COLORS["cyan"],
                  line_dash="dash", line_width=2,
                  annotation_text=f"Median: {median_val:.2f}",
                  annotation_position="top left")
    # ±3σ outlier bounds
    fig.add_vline(x=mean_val + 3*std_val, line_color=_COLORS["danger"],
                  line_dash="dot", line_width=1.5,
                  annotation_text="+3σ")
    if mean_val - 3*std_val > vals.min():
        fig.add_vline(x=mean_val - 3*std_val, line_color=_COLORS["danger"],
                      line_dash="dot", line_width=1.5,
                      annotation_text="-3σ")

    layout = dict(**_DARK_LAYOUT)
    layout["title"] = title or f"Distribution of {col}"
    layout["xaxis_title"] = col
    layout["yaxis_title"] = "Density"
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


def create_box_comparison(
    df: pd.DataFrame,
    group_col: str,
    value_col: str,
    title: Optional[str] = None,
    top_n: int = 8,
) -> Dict[str, Any]:
    """
    Box plots comparing distribution of a metric across segments.
    Ordered by median value descending.
    """
    top_groups = (
        df.groupby(group_col)[value_col].median()
        .sort_values(ascending=False)
        .head(top_n)
        .index.tolist()
    )
    clean = df[df[group_col].isin(top_groups)].dropna(subset=[group_col, value_col])

    fig = px.box(
        clean, x=group_col, y=value_col,
        title=title or f"{value_col} Distribution by {group_col}",
        category_orders={group_col: top_groups},
        color=group_col,
        color_discrete_sequence=px.colors.qualitative.Set2,
        points="outliers",
    )
    layout = dict(**_DARK_LAYOUT)
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return json.loads(fig.to_json())


# ─────────────────────────────────────────────────────────────────────────────
# SMART CHART SELECTOR (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

def smart_chart_selector(
    df: pd.DataFrame,
    col_x: str,
    col_y: Optional[str] = None,
    intent: str = "auto",
) -> Dict[str, Any]:
    """
    Automatically selects and generates the most appropriate chart type
    based on the data characteristics of the columns.

    Decision logic:
      - Both numeric: scatter / correlation
      - Date x + Numeric y: time-series line
      - Categorical x + Numeric y:
          ≤ 6 unique values: box plot
          > 6 unique values: horizontal bar
      - Single numeric col: distribution histogram
      - Single categorical col: donut pie chart
    """
    if col_x not in df.columns:
        return {}

    x_dtype = df[col_x].dtype
    x_is_date = pd.api.types.is_datetime64_any_dtype(df[col_x]) or \
                "date" in col_x.lower() or "time" in col_x.lower()
    x_is_numeric = np.issubdtype(x_dtype, np.number)
    x_is_categorical = x_dtype == object or x_dtype.name == "category"

    if col_y and col_y in df.columns:
        y_is_numeric = np.issubdtype(df[col_y].dtype, np.number)

        # Date + Numeric → Time Series
        if x_is_date and y_is_numeric:
            return create_time_series_chart(
                df=df, date_col=col_x, value_col=col_y,
                title=f"📈 {col_y} Over Time",
            )

        # Categorical + Numeric
        if x_is_categorical and y_is_numeric:
            n_unique = df[col_x].nunique()
            if n_unique <= 6:
                return create_box_comparison(
                    df=df, group_col=col_x, value_col=col_y,
                    title=f"📦 {col_y} Distribution by {col_x}",
                )
            else:
                return create_bar_comparison(
                    df=df, category_col=col_x, value_col=col_y,
                    title=f"📊 {col_y} by {col_x}",
                )

        # Both Numeric → Scatter
        if x_is_numeric and y_is_numeric:
            fig = px.scatter(
                df.dropna(subset=[col_x, col_y]),
                x=col_x, y=col_y,
                title=f"🔵 {col_x} vs {col_y}",
                trendline="ols",
                color_discrete_sequence=[_COLORS["primary"]],
            )
            layout = dict(**_DARK_LAYOUT)
            fig.update_layout(**layout)
            return json.loads(fig.to_json())

    else:
        # Single column
        if x_is_numeric:
            return create_distribution_chart(df=df, col=col_x)

        if x_is_categorical:
            val_counts = df[col_x].value_counts().head(8)
            fig = go.Figure(go.Pie(
                labels=val_counts.index.tolist(),
                values=val_counts.values.tolist(),
                hole=0.45,
                marker_colors=px.colors.qualitative.Set2,
            ))
            layout = dict(**_DARK_LAYOUT)
            layout["title"] = f"Distribution of {col_x}"
            fig.update_layout(**layout)
            return json.loads(fig.to_json())

    return {}
