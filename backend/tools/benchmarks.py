"""
benchmarks.py — Industry Benchmark Library (Phase 3)
=====================================================
Pure Python dictionaries — NO external library needed.
Provides KPI benchmark ranges for major business domains so
the analyst can answer: "Is our 18% margin GOOD or BAD?"

Structure per metric:
  world_class:  upper reference performance tier
  good:         reference target threshold
  warning:      reference warning threshold
  critical:     reference critical threshold
  unit:         display unit (%, $, days, x)
  higher_is_better: whether higher values are desirable

These historical configured values include source labels from the original
project. They have not been independently verified and do not establish an
industry percentile. Compare only exact metrics with explicit units and periods.
"""
import math
from typing import Dict, Any, Optional

# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK DATABASE
# ─────────────────────────────────────────────────────────────────────────────

BENCHMARK_DB: Dict[str, Dict[str, Any]] = {

    # ── E-Commerce / Retail ───────────────────────────────────────────────────
    "E-Commerce / Retail": {
        "profit_margin_pct": {
            "label": "Profit Margin %",
            "world_class": 25.0,
            "good": 15.0,
            "warning": 8.0,
            "critical": 3.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "NRF Retail Industry Report 2024",
        },
        "gross_margin_pct": {
            "label": "Gross Margin %",
            "world_class": 55.0,
            "good": 40.0,
            "warning": 25.0,
            "critical": 15.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "Industry standard",
        },
        "return_rate_pct": {
            "label": "Return Rate %",
            "world_class": 5.0,
            "good": 12.0,
            "warning": 20.0,
            "critical": 30.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "Shopify Commerce Report 2024",
        },
        "conversion_rate_pct": {
            "label": "Conversion Rate %",
            "world_class": 5.0,
            "good": 2.5,
            "warning": 1.5,
            "critical": 0.5,
            "unit": "%",
            "higher_is_better": True,
            "source": "Baymard Institute 2024",
        },
        "customer_acquisition_cost": {
            "label": "Customer Acquisition Cost (CAC)",
            "world_class": 20.0,
            "good": 45.0,
            "warning": 80.0,
            "critical": 150.0,
            "unit": "$",
            "higher_is_better": False,
            "source": "Industry standard",
        },
        "inventory_turnover": {
            "label": "Inventory Turnover (times/year)",
            "world_class": 12.0,
            "good": 8.0,
            "warning": 5.0,
            "critical": 3.0,
            "unit": "x/yr",
            "higher_is_better": True,
            "source": "NRF 2024",
        },
    },

    # ── SaaS / Subscription ───────────────────────────────────────────────────
    "SaaS / Subscription": {
        "churn_rate_monthly_pct": {
            "label": "Monthly Churn Rate %",
            "world_class": 1.0,
            "good": 3.0,
            "warning": 7.0,
            "critical": 12.0,
            "unit": "%/mo",
            "higher_is_better": False,
            "source": "Bessemer Venture Partners SaaS Report 2024",
        },
        "net_revenue_retention_pct": {
            "label": "Net Revenue Retention (NRR) %",
            "world_class": 130.0,
            "good": 110.0,
            "warning": 100.0,
            "critical": 90.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "OpenView SaaS Benchmarks 2024",
        },
        "ltv_cac_ratio": {
            "label": "LTV:CAC Ratio",
            "world_class": 5.0,
            "good": 3.0,
            "warning": 2.0,
            "critical": 1.0,
            "unit": "x",
            "higher_is_better": True,
            "source": "SaaStr / David Skok",
        },
        "payback_period_months": {
            "label": "CAC Payback Period (months)",
            "world_class": 12.0,
            "good": 18.0,
            "warning": 24.0,
            "critical": 36.0,
            "unit": "months",
            "higher_is_better": False,
            "source": "Bessemer 2024",
        },
        "gross_margin_pct": {
            "label": "Gross Margin %",
            "world_class": 80.0,
            "good": 70.0,
            "warning": 60.0,
            "critical": 50.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "OpenView 2024",
        },
        "annual_growth_rate_pct": {
            "label": "Annual Revenue Growth %",
            "world_class": 100.0,
            "good": 50.0,
            "warning": 20.0,
            "critical": 5.0,
            "unit": "%/yr",
            "higher_is_better": True,
            "source": "Bessemer 2024",
        },
    },

    # ── Operations / Supply Chain ──────────────────────────────────────────────
    "Operations / Supply Chain": {
        "otif_rate_pct": {
            "label": "On-Time In-Full (OTIF) Rate %",
            "world_class": 98.0,
            "good": 95.0,
            "warning": 90.0,
            "critical": 85.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "Gartner Supply Chain Top 25 2024",
        },
        "avg_lead_time_days": {
            "label": "Average Lead Time (days)",
            "world_class": 3.0,
            "good": 7.0,
            "warning": 14.0,
            "critical": 21.0,
            "unit": "days",
            "higher_is_better": False,
            "source": "APICS SCOR Benchmarks",
        },
        "defect_rate_pct": {
            "label": "Defect / Error Rate %",
            "world_class": 0.1,
            "good": 0.5,
            "warning": 1.0,
            "critical": 3.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "Six Sigma industry standard",
        },
        "warehouse_utilization_pct": {
            "label": "Warehouse Utilization %",
            "world_class": 85.0,
            "good": 75.0,
            "warning": 65.0,
            "critical": 55.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "CSCMP 2024",
        },
        "perfect_order_rate_pct": {
            "label": "Perfect Order Rate %",
            "world_class": 98.0,
            "good": 95.0,
            "warning": 90.0,
            "critical": 85.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "APICS SCOR",
        },
    },

    # ── Finance / Banking ──────────────────────────────────────────────────────
    "Finance / Banking": {
        "net_interest_margin_pct": {
            "label": "Net Interest Margin %",
            "world_class": 4.5,
            "good": 3.0,
            "warning": 2.0,
            "critical": 1.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "FDIC Quarterly Report 2024",
        },
        "loan_loss_rate_pct": {
            "label": "Loan Loss Rate %",
            "world_class": 0.3,
            "good": 0.8,
            "warning": 1.5,
            "critical": 3.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "Federal Reserve 2024",
        },
        "cost_to_income_ratio_pct": {
            "label": "Cost-to-Income Ratio %",
            "world_class": 40.0,
            "good": 55.0,
            "warning": 65.0,
            "critical": 75.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "McKinsey Banking 2024",
        },
    },

    # ── Healthcare ─────────────────────────────────────────────────────────────
    "Healthcare": {
        "readmission_rate_pct": {
            "label": "30-Day Readmission Rate %",
            "world_class": 8.0,
            "good": 12.0,
            "warning": 16.0,
            "critical": 20.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "CMS Hospital Quality Initiative 2024",
        },
        "patient_satisfaction_score": {
            "label": "Patient Satisfaction Score (HCAHPS)",
            "world_class": 90.0,
            "good": 80.0,
            "warning": 70.0,
            "critical": 60.0,
            "unit": "score",
            "higher_is_better": True,
            "source": "CMS HCAHPS 2024",
        },
        "avg_length_of_stay_days": {
            "label": "Average Length of Stay (days)",
            "world_class": 3.5,
            "good": 4.5,
            "warning": 6.0,
            "critical": 8.0,
            "unit": "days",
            "higher_is_better": False,
            "source": "AHA Hospital Statistics 2024",
        },
        "bed_occupancy_pct": {
            "label": "Bed Occupancy Rate %",
            "world_class": 85.0,
            "good": 78.0,
            "warning": 65.0,
            "critical": 55.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "WHO Hospital Metrics",
        },
    },

    # ── HR / People Analytics ──────────────────────────────────────────────────
    "HR / People Analytics": {
        "annual_attrition_pct": {
            "label": "Annual Employee Attrition %",
            "world_class": 5.0,
            "good": 10.0,
            "warning": 18.0,
            "critical": 25.0,
            "unit": "%/yr",
            "higher_is_better": False,
            "source": "SHRM Benchmarking Report 2024",
        },
        "time_to_fill_days": {
            "label": "Time-to-Fill (days)",
            "world_class": 20.0,
            "good": 35.0,
            "warning": 50.0,
            "critical": 70.0,
            "unit": "days",
            "higher_is_better": False,
            "source": "SHRM 2024",
        },
        "offer_acceptance_rate_pct": {
            "label": "Offer Acceptance Rate %",
            "world_class": 90.0,
            "good": 80.0,
            "warning": 70.0,
            "critical": 60.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "LinkedIn Talent Insights 2024",
        },
        "absenteeism_rate_pct": {
            "label": "Absenteeism Rate %",
            "world_class": 1.5,
            "good": 2.5,
            "warning": 4.0,
            "critical": 6.0,
            "unit": "%",
            "higher_is_better": False,
            "source": "BLS & SHRM 2024",
        },
    },

    # ── General Business Analytics (fallback) ─────────────────────────────────
    "General Business Analytics": {
        "revenue_growth_pct": {
            "label": "Revenue Growth % (YoY)",
            "world_class": 30.0,
            "good": 15.0,
            "warning": 5.0,
            "critical": 0.0,
            "unit": "%/yr",
            "higher_is_better": True,
            "source": "S&P 500 Composite Average",
        },
        "operating_margin_pct": {
            "label": "Operating Margin %",
            "world_class": 25.0,
            "good": 15.0,
            "warning": 8.0,
            "critical": 3.0,
            "unit": "%",
            "higher_is_better": True,
            "source": "Damodaran NYU Databases 2024",
        },
    },
}


# Period is part of the metric contract, never inferred from an uploaded amount.
for _metrics in BENCHMARK_DB.values():
    for _key, _definition in _metrics.items():
        _definition["period"] = ("monthly" if _definition["unit"] == "%/mo" else
            "annual" if _definition["unit"] in ("%/yr", "x/yr") else
            "30_days" if _key == "readmission_rate_pct" else "reporting_period")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_benchmarks_for_domain(domain: str) -> Dict[str, Any]:
    """Returns all benchmark definitions for a given business domain."""
    for key in BENCHMARK_DB:
        if key.lower() in domain.lower() or domain.lower() in key.lower():
            return BENCHMARK_DB[key]
    return BENCHMARK_DB.get("General Business Analytics", {})


def evaluate_metric_vs_benchmark(
    metric_key: str,
    actual_value: float,
    domain: str,
    *, unit: Optional[str] = None, period: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Compares an actual metric value against the industry benchmark for its domain.
    Returns a structured verdict with:
      - rating: "World Class" / "Good" / "Warning" / "Critical"
      - gap_to_good: how far from 'good' threshold
      - gap_to_world_class: how far from 'world class'
      - percentile_estimate: explicitly not inferred from threshold cutoffs
      - recommendation: what to do
    """
    benchmarks = get_benchmarks_for_domain(domain)

    # Exact identifiers and explicit units/periods prevent amount-vs-rate errors.
    if metric_key not in benchmarks or unit is None or period is None:
        return None
    bm = benchmarks[metric_key]
    if unit != bm["unit"] or period != bm["period"]:
        return None
    if isinstance(actual_value, bool):
        return None
    try:
        actual_value = float(actual_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(actual_value):
        return None
    higher = bm["higher_is_better"]
    wc = bm["world_class"]
    good = bm["good"]
    warn = bm["warning"]
    crit = bm["critical"]
    unit = bm["unit"]

    if higher:
        if actual_value >= wc:
            rating = "World Class ⭐"
            pct_est = "Top 10%"
        elif actual_value >= good:
            rating = "Good ✅"
            pct_est = "Top 30%"
        elif actual_value >= warn:
            rating = "Warning ⚠️"
            pct_est = "Bottom 40%"
        else:
            rating = "Critical 🔴"
            pct_est = "Bottom 20%"

        gap_to_good = round(good - actual_value, 2) if actual_value < good else 0
        gap_to_wc = round(wc - actual_value, 2) if actual_value < wc else 0
    else:
        if actual_value <= wc:
            rating = "World Class ⭐"
            pct_est = "Top 10%"
        elif actual_value <= good:
            rating = "Good ✅"
            pct_est = "Top 30%"
        elif actual_value <= warn:
            rating = "Warning ⚠️"
            pct_est = "Bottom 40%"
        else:
            rating = "Critical 🔴"
            pct_est = "Bottom 20%"

        gap_to_good = round(actual_value - good, 2) if actual_value > good else 0
        gap_to_wc = round(actual_value - wc, 2) if actual_value > wc else 0

    recommendation = (
        f"Excellent performance — maintain and expand what's working."
        if rating.startswith("World Class") else
        f"Solid — focus on closing the {gap_to_wc}{unit} gap to reach world-class ({wc}{unit})."
        if rating.startswith("Good") else
        f"Needs attention — you are {gap_to_good}{unit} behind the industry 'good' threshold ({good}{unit})."
        if rating.startswith("Warning") else
        f"Critical priority — immediate action required. Industry good threshold: {good}{unit}, yours: {actual_value}{unit}."
    )

    return {
        "metric_key": metric_key,
        "period": period,
        "metric_label": bm["label"],
        "actual_value": actual_value,
        "unit": unit,
        "rating": rating,
        "percentile_estimate": "Not estimated from reference thresholds",
        "benchmarks": {
            "world_class": wc,
            "good": good,
            "warning": warn,
            "critical": crit,
        },
        "gap_to_good": gap_to_good,
        "gap_to_world_class": gap_to_wc,
        "higher_is_better": higher,
        "recommendation": recommendation,
        "source": bm.get("source", "Configured reference"),
        "reference_notice": "Configured historical thresholds; source values have not been independently verified.",
    }


def run_full_benchmark_audit(
    kpi_metrics: list,
    domain: str,
) -> Dict[str, Any]:
    """
    Runs all KPI metrics through the benchmark database for the detected domain.
    Returns a structured audit with ratings and gaps for each matched metric.
    """
    results, skipped = [], []
    for kpi in kpi_metrics:
        key = kpi.get("metric_key")
        value = kpi.get("value")
        verdict = evaluate_metric_vs_benchmark(key, value, domain,
            unit=kpi.get("unit"), period=kpi.get("period"))
        if verdict is not None:
            verdict["kpi_name"] = kpi.get("metric_name", key)
            results.append(verdict)
        else:
            skipped.append(dict(metric=kpi.get("metric_name", kpi.get("column", key)),
                reason="Requires an exact benchmark metric_key, finite value, matching unit and explicit period."))

    world_class_count = sum(1 for r in results if "World Class" in r["rating"])
    good_count = sum(1 for r in results if r["rating"].startswith("Good"))
    warning_count = sum(1 for r in results if "Warning" in r["rating"])
    critical_count = sum(1 for r in results if "Critical" in r["rating"])

    return {
        "domain": domain,
        "metrics_benchmarked": len(results),
        "skipped_metrics": skipped,
        "benchmark_verdicts": results,
        "score_summary": {
            "world_class": world_class_count,
            "good": good_count,
            "warning": warning_count,
            "critical": critical_count,
        },
        "overall_competitive_position": (
            "Industry Leader" if world_class_count >= 2 else
            "Competitive" if (world_class_count + good_count) >= len(results) * 0.6 else
            "Below Average" if warning_count >= len(results) * 0.5 else
            "Needs Improvement"
        ) if results else "No benchmarks matched",
    }
