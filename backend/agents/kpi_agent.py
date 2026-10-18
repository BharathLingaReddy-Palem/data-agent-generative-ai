"""
kpi_agent.py — Business KPI & Domain Metrics Agent
====================================================
TOOL-FIRST PATTERN:
  Step 1: Rule-based domain detection from column signatures (NO LLM for this)
  Step 2: Pandas computes EXACT KPI values, growth rates, percentiles
  Step 3: LLM receives the pre-computed KPI table and interprets
          the business meaning — it does NOT compute numbers.
"""
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.tools.stats_tools import compute_mom_yoy, compute_group_aggregates

from backend.services.narrative_checks import unsupported_claims
from backend.services.metric_semantics import metric_aggregation

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN DETECTION — Rule-based (No LLM needed)
# ─────────────────────────────────────────────────────────────────────────────

_DOMAIN_SIGNATURES = {
    "SaaS / Subscription": ["mrr", "arr", "churn", "tier", "tenure", "subscription", "plan", "ltv", "cac", "nps"],
    "E-Commerce / Retail": ["order", "product", "category", "discount", "cart", "purchase", "sku", "refund", "return"],
    "Operations / Supply Chain": ["shipment", "delivery", "warehouse", "transit", "lead_time", "sla", "fulfillment", "logistics", "carrier"],
    "Finance / Banking": ["loan", "interest", "balance", "credit", "debit", "transaction", "account", "portfolio", "risk"],
    "Healthcare": ["patient", "diagnosis", "procedure", "claim", "icd", "cpt", "readmission", "length_of_stay"],
    "HR / People Analytics": ["employee", "headcount", "attrition", "salary", "tenure", "department", "hire", "performance"],
}


def detect_domain(columns: List[str]) -> str:
    """
    Deterministic domain detection from column name signatures.
    Scores each domain by keyword match count — picks the highest scorer.
    Falls back to 'General Business Analytics' if no match.
    """
    col_str = " ".join(c.lower() for c in columns)
    scores = {}
    for domain, keywords in _DOMAIN_SIGNATURES.items():
        scores[domain] = sum(1 for kw in keywords if kw in col_str)

    best_domain = max(scores, key=scores.get)
    return best_domain if scores[best_domain] > 0 else "General Business Analytics"


# ─────────────────────────────────────────────────────────────────────────────
# DOMAIN-SPECIFIC KPI FORMULAS
# ─────────────────────────────────────────────────────────────────────────────

def compute_saas_kpis(df: pd.DataFrame, measures: List[str]) -> List[Dict[str, Any]]:
    """Computes SaaS-specific KPIs: Churn Rate, MRR, ARR, LTV."""
    kpis = []
    cols = {c.lower(): c for c in df.columns}

    # Churn Rate
    if "churn" in cols:
        churn_col = cols["churn"]
        if df[churn_col].dtype == object:
            churn_vals = df[churn_col].str.lower()
            churned = int(churn_vals.isin(["yes", "true", "1", "churned"]).sum())
        else:
            churned = int((df[churn_col] == 1).sum())
        churn_rate = round((churned / len(df)) * 100.0, 2)
        kpis.append({
            "metric_name": "Churn Rate",
            "column": churn_col,
            "total": churn_rate,
            "formatted_total": f"{churn_rate}%",
            "mean": churn_rate,
            "formatted_mean": f"{churn_rate}%",
            "median": None,
            "growth_pct": None,
            "p25": None, "p75": None, "p90": None,
            "formula": "Churned Customers / Total Customers × 100",
            "benchmark": "Observation period required for a churn benchmark.",
        })

    # MRR
    for term in ["mrr", "monthly_revenue", "monthly_recurring"]:
        if term in cols:
            col = cols[term]
            mrr_total = float(df[col].sum())
            kpis.append({
                "metric_name": "Total MRR",
                "column": col,
                "total": mrr_total,
                "formatted_total": f"${mrr_total:,.2f}",
                "mean": round(float(df[col].mean()), 2),
                "formatted_mean": f"${float(df[col].mean()):,.2f}",
                "median": round(float(df[col].median()), 2),
                "growth_pct": None,
                "p25": None, "p75": None, "p90": None,
                "formula": "Sum of all monthly recurring revenue",
                "benchmark": "Context-dependent",
            })
            break

    return kpis


def compute_ecommerce_kpis(df: pd.DataFrame, measures: List[str]) -> List[Dict[str, Any]]:
    """Computes E-Commerce KPIs: AOV, Profit Margin %, Return Rate."""
    kpis = []
    cols = {c.lower(): c for c in df.columns}

    # Average Order Value (AOV)
    for sales_term in ["sales", "revenue", "order_value", "amount"]:
        if sales_term in cols:
            sales_col = cols[sales_term]
            aov = round(float(df[sales_col].mean()), 2)
            kpis.append({
                "metric_name": "Average Order Value (AOV)",
                "column": sales_col,
                "total": float(df[sales_col].sum()),
                "formatted_total": f"${float(df[sales_col].sum()):,.2f}",
                "mean": aov,
                "formatted_mean": f"${aov:,.2f}",
                "median": round(float(df[sales_col].median()), 2),
                "growth_pct": None,
                "p25": round(float(df[sales_col].quantile(0.25)), 2),
                "p75": round(float(df[sales_col].quantile(0.75)), 2),
                "p90": round(float(df[sales_col].quantile(0.90)), 2),
                "formula": "Total Revenue / Number of Orders",
                "benchmark": "Industry varies; aim to increase over time",
            })
            break

    # Profit Margin %
    profit_col = cols.get("profit")
    sales_col_name = cols.get("sales") or cols.get("revenue")
    if profit_col and sales_col_name:
        total_profit = float(df[profit_col].sum())
        total_sales = float(df[sales_col_name].sum())
        margin_pct = round((total_profit / total_sales) * 100.0, 2) if total_sales != 0 else 0
        kpis.append({
            "metric_name": "Overall Profit Margin %",
            "metric_key": "profit_margin_pct", "value": margin_pct,
            "unit": "%", "period": "reporting_period",
            "column": profit_col,
            "total": margin_pct,
            "formatted_total": f"{margin_pct}%",
            "mean": margin_pct,
            "formatted_mean": f"{margin_pct}%",
            "median": None,
            "growth_pct": None,
            "p25": None, "p75": None, "p90": None,
            "formula": "Total Profit / Total Revenue × 100",
            "benchmark": "Good: > 15% | Warning: < 5%",
        })

    return kpis


def compute_ops_kpis(df: pd.DataFrame, measures: List[str]) -> List[Dict[str, Any]]:
    """Computes Operations/Supply Chain KPIs: OTIF Rate, Average Lead Time."""
    kpis = []
    cols = {c.lower(): c for c in df.columns}

    # On-Time In-Full (OTIF) Rate
    for otif_term in ["on_time", "otif", "delivery_status", "sla_met", "on_time_delivery"]:
        if otif_term in cols:
            col = cols[otif_term]
            if df[col].dtype == object:
                on_time = int(df[col].str.lower().isin(["yes", "true", "on time", "met"]).sum())
            else:
                on_time = int((df[col] == 1).sum())
            otif_rate = round((on_time / len(df)) * 100.0, 2)
            kpis.append({
                "metric_name": "On-Time Delivery Rate (OTIF)",
                "column": col,
                "total": otif_rate,
                "formatted_total": f"{otif_rate}%",
                "mean": otif_rate,
                "formatted_mean": f"{otif_rate}%",
                "median": None, "growth_pct": None,
                "p25": None, "p75": None, "p90": None,
                "formula": "On-Time Deliveries / Total Deliveries × 100",
                "benchmark": "Target: > 95%",
            })
            break

    # Average Lead Time
    for lead_term in ["lead_time", "transit_time", "days_to_deliver", "shipping_days"]:
        if lead_term in cols and np.issubdtype(df[cols[lead_term]].dtype, np.number):
            col = cols[lead_term]
            kpis.append({
                "metric_name": "Average Lead Time (Days)",
                "column": col,
                "total": round(float(df[col].sum()), 2),
                "formatted_total": f"{round(float(df[col].sum()), 0):.0f} total days",
                "mean": round(float(df[col].mean()), 2),
                "formatted_mean": f"{round(float(df[col].mean()), 1)} days",
                "median": round(float(df[col].median()), 2),
                "growth_pct": None,
                "p25": round(float(df[col].quantile(0.25)), 2),
                "p75": round(float(df[col].quantile(0.75)), 2),
                "p90": round(float(df[col].quantile(0.90)), 2),
                "formula": "Average days from order to delivery",
                "benchmark": "Target: as low as possible",
            })
            break

    return kpis


# ─────────────────────────────────────────────────────────────────────────────
# CORE KPI COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def _compute_core_kpi(df: pd.DataFrame, col: str, date_col: Optional[str]) -> Dict[str, Any]:
    """Computes a full KPI fact block for a single numeric measure."""
    vals = df[col].dropna().astype(float)
    # Column names provide aggregation hints, not a currency or reporting period.
    aggregation = metric_aggregation(col)
    additive = aggregation == "sum"
    total_val = float(vals.sum()) if additive else None
    avg_val = float(vals.mean())
    median_val = float(vals.median())
    p25 = float(vals.quantile(0.25))
    p75 = float(vals.quantile(0.75))
    p90 = float(vals.quantile(0.90))

    # Currency formatting heuristic
    is_currency = any(k in col.lower() for k in ["revenue", "sales", "price", "amount", "cost", "profit", "mrr", "arr"])
    fmt = lambda v: f"{v:,.2f}" if v is not None and np.isfinite(v) else "Not additive"

    # Month-over-Month growth (deterministic via Pandas)
    growth_pct = None
    mom_trend = None
    if additive and date_col and date_col in df.columns:
        try:
            df_sorted = df.dropna(subset=[date_col]).copy()
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
            monthly = df_sorted.groupby(pd.Grouper(key=date_col, freq="ME"))[col].sum()
            if len(monthly) >= 2 and monthly.iloc[-2] != 0:
                last_m = float(monthly.iloc[-1])
                prev_m = float(monthly.iloc[-2])
                growth_pct = round(((last_m - prev_m) / abs(prev_m)) * 100.0, 2)
                mom_trend = "↑ Growing" if growth_pct > 0 else "↓ Declining" if growth_pct < 0 else "→ Flat"
        except Exception:
            pass

    # Quarterly growth (QoQ)
    qoq_pct = None
    if additive and date_col and date_col in df.columns:
        try:
            df_sorted = df.dropna(subset=[date_col]).copy()
            df_sorted[date_col] = pd.to_datetime(df_sorted[date_col], errors="coerce")
            quarterly = df_sorted.groupby(pd.Grouper(key=date_col, freq="QE"))[col].sum()
            if len(quarterly) >= 2 and quarterly.iloc[-2] != 0:
                qoq_pct = round(((float(quarterly.iloc[-1]) - float(quarterly.iloc[-2])) / abs(float(quarterly.iloc[-2]))) * 100.0, 2)
        except Exception:
            pass

    return {
        "metric_name": col.replace("_", " ").title(),
        "column": col,
        "total": round(total_val, 4) if total_val is not None else None,
        "value": round(total_val if additive else avg_val, 4),
        "formatted_value": fmt(total_val if additive else avg_val),
        "aggregation": aggregation,
        "unit": "unspecified",
        "period": "dataset snapshot",
        "aggregation_note": "Sum of observed values" if additive else "Mean of observed values; totals are not meaningful for this measure",
        "formatted_total": fmt(total_val),
        "mean": round(avg_val, 4),
        "formatted_mean": fmt(avg_val),
        "median": round(median_val, 4),
        "p25": round(p25, 4),
        "p75": round(p75, 4),
        "p90": round(p90, 4),
        "growth_pct": growth_pct,
        "mom_trend": mom_trend,
        "qoq_pct": qoq_pct,
        "is_currency": is_currency,
    }


def kpi_agent_node(state: AgentState) -> AgentState:
    """
    KPI Agent — Domain KPI Modeling (Tool-First Pattern)

    Step 1: Deterministic domain detection from column names (NO LLM)
    Step 2: Pandas computes exact KPI values, growth, percentiles
    Step 3: Apply domain-specific formulas (Churn Rate, AOV, OTIF, etc.)
    Step 4: LLM receives exact numbers and writes business interpretation
    """
    logger.info("--> [KPI Agent] Modeling domain KPIs (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("KPI Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    measures = schema_meta.get("recommended_measures", [])
    date_col = schema_meta.get("primary_date_column")

    # Fallback: pick numeric columns if schema didn't identify measures
    if not measures:
        measures = [c for c in df.columns if np.issubdtype(df[c].dtype, np.number)][:6]

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Detect domain — Rule-based (deterministic, NO LLM)
    # ──────────────────────────────────────────────────────────────────────────
    domain = detect_domain(list(df.columns))

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Compute core KPIs for each measure (Pandas — exact numbers)
    # ──────────────────────────────────────────────────────────────────────────
    kpis: List[Dict[str, Any]] = []

    # Volume metric (always first)
    kpis.append({
        "metric_name": "Total Records / Volume",
        "column": "rows",
        "total": len(df),
        "formatted_total": f"{len(df):,}",
        "mean": len(df),
        "formatted_mean": f"{len(df):,}",
        "median": None,
        "p25": None, "p75": None, "p90": None,
        "growth_pct": None,
        "mom_trend": None,
        "qoq_pct": None,
        "is_currency": False,
    })

    for col in measures[:5]:
        if col in df.columns and np.issubdtype(df[col].dtype, np.number):
            kpi_block = _compute_core_kpi(df, col, date_col)
            kpis.append(kpi_block)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Domain-Specific KPI formulas
    # ──────────────────────────────────────────────────────────────────────────
    domain_specific_kpis: List[Dict] = []
    if "SaaS" in domain:
        domain_specific_kpis = compute_saas_kpis(df, measures)
    elif "E-Commerce" in domain or "Retail" in domain:
        domain_specific_kpis = compute_ecommerce_kpis(df, measures)
    elif "Operations" in domain or "Supply" in domain:
        domain_specific_kpis = compute_ops_kpis(df, measures)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Time-Series trend (MoM/YoY) for primary metric
    # ──────────────────────────────────────────────────────────────────────────
    time_series_data = {}
    primary_metric = measures[0] if measures else None
    if primary_metric and date_col and primary_metric in df.columns and date_col in df.columns and kpis[1].get("aggregation") == "sum":
        from backend.tools.stats_tools import compute_mom_yoy
        time_series_data = compute_mom_yoy(df, date_col=date_col, metric_col=primary_metric)

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: LLM interprets computed numbers — does NOT compute them
    # ──────────────────────────────────────────────────────────────────────────
    kpi_summary_for_llm = []
    for k in kpis[1:4]:  # Skip volume row, take first 3 real metrics
        summary = f"• {k['metric_name']}: {k['aggregation']}={k['formatted_value']}, Median={k['median']}. Unit unspecified; dataset snapshot. {k['aggregation_note']}"
        if k.get("growth_pct") is not None:
            summary += f", MoM Growth={k['growth_pct']:+.2f}%"
        if k.get("qoq_pct") is not None:
            summary += f", QoQ={k['qoq_pct']:+.2f}%"
        kpi_summary_for_llm.append(summary)

    domain_kpi_summary = "\n".join([
        f"• {k['metric_name']}: {k['formatted_total']} ({k.get('formula', '')})"
        for k in domain_specific_kpis
    ]) if domain_specific_kpis else "No domain-specific KPIs computed."

    trend_summary = (
        f"Overall trend: {time_series_data.get('overall_trend', 'N/A')}, "
        f"Latest MoM: {time_series_data.get('latest_mom_pct', 'N/A')}%, "
        f"Best month: {time_series_data.get('best_month', 'N/A')}, "
        f"Worst month: {time_series_data.get('worst_month', 'N/A')}"
        if time_series_data and "error" not in time_series_data else "No time-series data available."
    )

    # Without a metric dictionary, business meaning is not established by a name.
    # Present computed facts rather than asking an LLM to infer pay goals or causes.
    kpi_interpretation = "\n".join(
        f"- **{k['metric_name']}**: {k['aggregation']} {k['formatted_value']}; median {k['median']:,.2f}."
        for k in kpis[1:] if k.get('median') is not None)
    kpi_interpretation += "\n\nUnits and reporting periods are unspecified. These descriptive values do not establish benchmark performance, organizational goals or causality."
    if not time_series_data:
        kpi_interpretation += " No time trend is established here."

    kpi_results = {
        "domain": domain,
        "kpi_metrics": kpis,
        "domain_specific_kpis": domain_specific_kpis,
        "primary_metric": kpis[1]["metric_name"] if len(kpis) > 1 else kpis[0]["metric_name"],
        "time_series": time_series_data,
        "kpi_interpretation": kpi_interpretation,
    }

    execution_steps.append(
        f"KPI Agent: Detected domain='{domain}', computed {len(kpis)} core + {len(domain_specific_kpis)} domain KPIs."
    )

    return {
        **state,
        "kpi_results": kpi_results,
        "execution_steps": execution_steps,
        "errors": errors,
    }
