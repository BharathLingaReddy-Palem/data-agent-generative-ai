"""
diagnostic_agent.py — Root Cause & Diagnostic Agent
=====================================================
TOOL-FIRST PATTERN:
  Step 1: Pandas computes ALL segment aggregates, Pareto rankings,
          period-over-period decompositions, and HHI concentration index
  Step 2: Publish a deterministic briefing from the computed evidence.
          Segment associations do not establish causal drivers.

The diagnostic follows the analyst's 'WHY' framework:
  WHY did the metric change?
  → Pareto: WHO (which segments) caused it?
  → Delta Decomp: WHEN and by HOW MUCH?
  → HHI: HOW CONCENTRATED is the risk?
  → Drilldown: WHERE is the sub-segment impact?
"""
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.tools.stats_tools import (
    pareto_analysis,
    delta_decomposition,
    compute_hhi,
    compute_group_aggregates,
)

logger = logging.getLogger(__name__)
from backend.services.metric_semantics import metric_aggregation
from backend.services.date_inference import infer_dates


def diagnostic_agent_node(state: AgentState) -> AgentState:
    """
    Diagnostic Agent — Root-Cause Analysis (Tool-First Pattern)

    Computes with Pandas/NumPy:
      1. Pareto 80/20 analysis per dimension
      2. Period-over-Period delta decomposition (which segments drove the change)
      3. HHI concentration index (single-number risk score)
      4. Multi-level sub-segment drilldown pivot table
      5. Bottom-performer identification (segments losing share)
    The published narrative states computed evidence and its limits.
    """
    logger.info("--> [Diagnostic Agent] Root-Cause & Pareto Analysis (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    plan = state.get("analysis_plan", {})
    user_question = state.get("user_question") or ""
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Diagnostic Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    # Resolve target metric
    measures = schema_meta.get("recommended_measures", [])
    dimensions = schema_meta.get("recommended_dimensions", [])
    target_metric = plan.get("target_metric") or (measures[0] if measures else None)

    if not target_metric or target_metric not in df.columns or \
            not np.issubdtype(df[target_metric].dtype, np.number):
        numeric_cols = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)]
        target_metric = numeric_cols[0] if numeric_cols else None

    # Resolve valid dimensions
    valid_dims = [d for d in dimensions if d != target_metric and d in df.columns and 1 < df[d].nunique() < 200]
    if not valid_dims:
        valid_dims = [
            c for c in df.columns
            if c != target_metric and df[c].dtype == "object" and 1 < df[c].nunique() < 200
        ][:4]

    if not target_metric:
        if valid_dims:
            # For non-numeric datasets (catalogs, directories, taxonomies),
            # use item/record count as frequency metric for Pareto & concentration analysis
            target_metric = "record_count"
            df = df.copy()
            df[target_metric] = 1
        else:
            logger.info("Diagnostic Agent: No numeric measure and no categorical dimensions — skipping diagnostic.")
            diagnostic_results = {
                "available": False,
                "reason": "No numeric measure or suitable categorical dimensions in dataset.",
                "diagnostic_narrative": "Diagnostic analysis skipped: no numeric metrics or categorical dimensions found.",
            }
            execution_steps.append("Diagnostic Agent: Skipped — insufficient metrics/dimensions.")
            return {
                **state,
                "diagnostic_results": diagnostic_results,
                "execution_steps": execution_steps,
                "errors": errors,
            }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Pareto Analysis per Dimension (stats_tools — exact Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    pareto_results: Dict[str, Any] = {}
    additive_metric = metric_aggregation(target_metric) == "sum"
    for dim in valid_dims[:3] if additive_metric else []:
        p_res = pareto_analysis(df, category_col=dim, value_col=target_metric)
        if "error" not in p_res:
            pareto_results[dim] = p_res

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Period-over-Period Variance Decomposition (stats_tools — Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    date_col = schema_meta.get("primary_date_column")
    variance_decomp: Optional[Dict] = None
    if additive_metric and date_col in df.columns and valid_dims and infer_dates(df[date_col]) is not None:
        try:
            df_dated = df.dropna(subset=[date_col]).copy()
            df_dt = pd.to_datetime(df_dated[date_col], errors="coerce")
            valid_dt = df_dt.notna()
            df_dated = df_dated[valid_dt].copy()
            df_dated["_period"] = df_dt[valid_dt].dt.to_period("M").astype(str)
            periods = sorted([p for p in df_dated["_period"].unique() if p != "NaT"])
            if len(periods) >= 2:
                p1, p2 = periods[-2], periods[-1]
                primary_dim = valid_dims[0]
                variance_decomp = delta_decomposition(
                    df=df_dated,
                    time_col="_period",
                    metric_col=target_metric,
                    dimension_col=primary_dim,
                    period_1=p1,
                    period_2=p2,
                )
        except Exception as e:
            logger.warning(f"Variance decomposition skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: HHI Concentration Index (stats_tools — deterministic)
    # ──────────────────────────────────────────────────────────────────────────
    hhi_results: Dict[str, Any] = {}
    for dim in valid_dims[:2] if additive_metric else []:
        hhi = compute_hhi(df, group_col=dim, metric_col=target_metric)
        if "error" not in hhi:
            hhi_results[dim] = hhi

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Full Group Aggregates per Dimension (stats_tools — Pandas)
    # ──────────────────────────────────────────────────────────────────────────
    group_agg_results: Dict[str, Any] = {}
    for dim in valid_dims[:2]:
        agg = compute_group_aggregates(df, group_col=dim, metric_col=target_metric)
        if "error" not in agg:
            group_agg_results[dim] = agg

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Multi-Level Sub-Segment Drilldown (Pandas pivot)
    # ──────────────────────────────────────────────────────────────────────────
    drilldown: Dict[str, Any] = {}
    if len(valid_dims) >= 2 and additive_metric:
        try:
            d1, d2 = valid_dims[0], valid_dims[1]
            pivot = (
                df.groupby([d1, d2])[target_metric]
                .agg(["sum", "count", "mean"])
                .reset_index()
                .sort_values("sum", ascending=False)
                .head(12)
            )
            pivot.columns = [d1, d2, "total", "count", "mean"]
            pivot["total"] = pivot["total"].round(2)
            pivot["mean"] = pivot["mean"].round(2)
            drilldown = {
                "level_1_dim": d1,
                "level_2_dim": d2,
                "top_subsegments": pivot.to_dict(orient="records"),
                "total_combinations": len(df.groupby([d1, d2])),
            }
        except Exception as e:
            logger.warning(f"Drilldown skipped: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: Build Structured Evidence Brief for LLM
    # ──────────────────────────────────────────────────────────────────────────
    pareto_evidence = []
    for dim, p_res in pareto_results.items():
        top3 = p_res.get("top_categories", [])[:3]
        pareto_evidence.append(
            f"• [{dim}] Top 3 segments: "
            + ", ".join([
                f"{r.get(dim, r.get(list(r.keys())[0], '?'))}="
                f"{r.get('share_pct', 0):.1f}% share"
                for r in top3
            ])
            + f" | {p_res.get('summary', '')}"
        )

    decomp_evidence = ""
    if variance_decomp and "error" not in variance_decomp:
        decomp_evidence = (
            f"Period {variance_decomp['period_1']} → {variance_decomp['period_2']}: "
            f"{target_metric} changed by {variance_decomp['total_delta']:+.2f} "
            f"({variance_decomp['growth_pct']:+.2f}% {variance_decomp['trend']}). "
            f"Top positive driver: {variance_decomp['top_positive_drivers'][0].get(variance_decomp['dimension'], 'N/A') if variance_decomp.get('top_positive_drivers') else 'None'}. "
            f"Top negative driver: {variance_decomp['top_negative_drivers'][0].get(variance_decomp['dimension'], 'N/A') if variance_decomp.get('top_negative_drivers') else 'None'}."
        )

    hhi_evidence = []
    for dim, hhi in hhi_results.items():
        hhi_evidence.append(
            f"• [{dim}] HHI={hhi['hhi_score']:.4f}: {hhi['interpretation']}. "
            f"Top segment '{hhi.get('top_segment', 'N/A')}' holds {hhi.get('top_segment_share_pct', 0):.1f}%."
        )

    top_subseg = ""
    if drilldown.get("top_subsegments"):
        segs = drilldown["top_subsegments"][:3]
        d1 = drilldown.get("level_1_dim", "dim1")
        d2 = drilldown.get("level_2_dim", "dim2")
        top_subseg = " | ".join(
            [f"{s.get(d1, '?')} × {s.get(d2, '?')} = {s.get('total', 0):,.2f} ({s.get('count', 0)} records)" for s in segs]
        )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: Publish computed diagnostic evidence
    # Keep the published briefing tied to computed evidence. In particular,
    # skipped additive decomposition must not become a claim that dates are absent.
    diagnostic_narrative = (
        f"**Segment analysis of {target_metric}**\n\n"
        + ("\n".join(pareto_evidence) if pareto_evidence else
           "No Pareto shares were computed. Additive metrics and suitable categories are required.")
        + "\n\n**Period comparison**\n\n"
        + (decomp_evidence or "No period decomposition was computed. This requires an additive measure, valid dates, comparison periods and suitable segments. See the separate trend analysis for available time-series results.")
        + "\n\n**Concentration**\n\n"
        + ("\n".join(hhi_evidence) if hhi_evidence else "No concentration index was computed.")
        + ("\n\n**Cross-segment observations**\n\n" + top_subseg if top_subseg else "")
        + "\n\nThese are descriptive distributions and associations, not established causes. Confirm units, periods and missing-value conventions before drawing conclusions."
    )

    diagnostic_results = {
        "target_metric": target_metric,
        "analyzed_dimensions": valid_dims,
        "pareto_analysis": pareto_results,
        "variance_decomposition": variance_decomp,
        "hhi_concentration": hhi_results,
        "group_aggregates": group_agg_results,
        "subsegment_drilldown": drilldown,
        "diagnostic_narrative": diagnostic_narrative,
    }

    hhi_summary = ", ".join([
        f"{d}={v.get('hhi_score', 0):.3f}" for d, v in hhi_results.items()
    ]) or "N/A"
    execution_steps.append(
        f"Diagnostic Agent: Root-cause analysis across {len(valid_dims)} dimensions. "
        f"Pareto: {len(pareto_results)} dims. "
        f"HHI: {hhi_summary}."
    )

    return {
        **state,
        "diagnostic_results": diagnostic_results,
        "execution_steps": execution_steps,
        "errors": errors,
    }
