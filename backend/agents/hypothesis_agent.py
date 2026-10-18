"""
hypothesis_agent.py — Statistical Hypothesis Testing Agent
===========================================================
TOOL-FIRST PATTERN:
  Step 1: SciPy computes EXACT test statistics, p-values, effect sizes
  Step 2: LLM receives the computed test results and translates p-values
          into plain business English. LLM does NOT compute statistics.

Tests run (in order of data characteristics):
  - Welch's T-Test: Two-group comparison of a continuous metric
  - Mann-Whitney U: Non-parametric alternative (used when data is skewed)
  - One-Way ANOVA: 3+ group comparison
  - Chi-Square: Independence between two categorical columns
  All tests include effect sizes (Cohen's d, Cramér's V).
"""
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.services.narrative_checks import unsupported_claims
from backend.tools.stats_tools import (
    two_sample_ttest,
    holm_adjust,
    mannwhitney_test,
    one_way_anova,
    chi_square_test,
    compute_descriptive_stats,
)

logger = logging.getLogger(__name__)


def _select_test_type(df: pd.DataFrame, metric_col: str, group_col: str) -> str:
    """
    Automatically select the correct statistical test based on data properties.
    - ANOVA if 3+ groups
    - Mann-Whitney if 2 groups but metric is skewed (|skew| > 1)
    - T-Test if 2 groups and roughly symmetric
    """
    n_groups = df[group_col].nunique()
    if n_groups >= 3:
        return "anova"

    skewness = float(df[metric_col].dropna().skew())
    if abs(skewness) > 1.0:
        return "mannwhitney"

    return "ttest"


def hypothesis_agent_node(state: AgentState) -> AgentState:
    """
    Hypothesis Agent — Statistical Significance Testing (Tool-First Pattern)

    Tests conducted (selected automatically based on data properties):
      1. T-Test or Mann-Whitney U (2-group continuous comparison)
      2. One-Way ANOVA (3+ group comparison)
      3. Chi-Square with Cramér's V (categorical independence)
    All effect sizes are computed deterministically.
    LLM translates exact p-values and effect sizes into executive language.
    """
    logger.info("--> [Hypothesis Agent] Running statistical significance tests (Tool-First)...")

    df = state.get("df_clean") if state.get("df_clean") is not None else state.get("df_raw")
    schema_meta = state.get("schema_metadata", {})
    diagnostic = state.get("diagnostic_results", {})
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Hypothesis Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    target_metric = diagnostic.get("target_metric")
    measures = schema_meta.get("recommended_measures", [])
    dimensions = schema_meta.get("recommended_dimensions", [])

    if not target_metric:
        target_metric = measures[0] if measures else None

    dimensions = [c for c in dimensions if c != target_metric]

    tests_run: List[Dict[str, Any]] = []

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 1: Continuous group comparison (2 groups → T-Test or Mann-Whitney)
    #         (3+ groups → ANOVA)
    # ──────────────────────────────────────────────────────────────────────────
    if target_metric and target_metric in df.columns and dimensions:
        for dim in dimensions[:2]:
            if dim not in df.columns:
                continue
            n_groups = df[dim].nunique()
            clean = df.dropna(subset=[dim, target_metric])
            if len(clean) < 10:
                continue

            if n_groups >= 3:
                # ANOVA
                anova_res = one_way_anova(df, group_col=dim, value_col=target_metric)
                if "error" not in anova_res:
                    anova_res["hypothesis"] = (
                        f"Do means of '{target_metric}' differ significantly across "
                        f"{n_groups} groups in '{dim}'?"
                    )
                    tests_run.append(anova_res)
                    break
            else:
                # Choose T-Test or Mann-Whitney based on skewness
                test_type = _select_test_type(df, target_metric, dim)
                if test_type == "mannwhitney":
                    result = mannwhitney_test(df, group_col=dim, value_col=target_metric)
                    method = "Mann-Whitney U (non-parametric, data is skewed)"
                else:
                    result = two_sample_ttest(df, group_col=dim, value_col=target_metric)
                    method = "Welch's T-Test"

                if "error" not in result:
                    result["auto_selected_test"] = method
                    result["hypothesis"] = (
                        f"Does '{target_metric}' differ significantly between the top 2 groups in '{dim}'?"
                    )
                    tests_run.append(result)
                    break

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 2: Chi-Square Independence (categorical vs. categorical)
    # ──────────────────────────────────────────────────────────────────────────
    cat_cols = [
        c for c in dimensions
        if c in df.columns and 2 <= df[c].nunique() <= 20
    ]
    if len(cat_cols) >= 2:
        for i in range(len(cat_cols) - 1):
            chi_res = chi_square_test(df, col1=cat_cols[i], col2=cat_cols[i + 1])
            if "error" not in chi_res:
                chi_res["hypothesis"] = (
                    f"Is there a statistically significant association between "
                    f"'{cat_cols[i]}' and '{cat_cols[i+1]}'?"
                )
                tests_run.append(chi_res)
                break

    # ──────────────────────────────────────────────────────────────────────────
    # TEST 3: If only 1 dimension was tested, add T-Test on next dimension
    # ──────────────────────────────────────────────────────────────────────────
    if len(tests_run) < 2 and target_metric and len(dimensions) >= 2:
        for dim in dimensions[1:3]:
            if dim not in df.columns or df[dim].nunique() < 2:
                continue
            if any(t.get("group_col") == dim for t in tests_run):
                continue
            test_type = _select_test_type(df, target_metric, dim)
            if test_type == "mannwhitney":
                result = mannwhitney_test(df, group_col=dim, value_col=target_metric)
            elif test_type == "anova":
                result = one_way_anova(df, group_col=dim, value_col=target_metric)
            else:
                result = two_sample_ttest(df, group_col=dim, value_col=target_metric)

            if "error" not in result:
                result["hypothesis"] = f"Does '{target_metric}' differ between groups in '{dim}'?"
                tests_run.append(result)
                break

    # ──────────────────────────────────────────────────────────────────────────
    # LLM STEP: Interpret exact p-values and effect sizes — NOT compute them
    # ──────────────────────────────────────────────────────────────────────────
    if tests_run:
        adjusted = holm_adjust([test['p_value'] for test in tests_run])
        for test, probability in zip(tests_run, adjusted):
            test['raw_statistically_significant'] = test['statistically_significant']
            test['p_value_adjusted'] = probability
            test['p_value_formatted'] = f"{probability:.4e} (Holm-adjusted)"
            test['multiple_testing_correction'] = 'Holm'
            test['statistically_significant'] = probability < test.get('significance_level', 0.05)
            test['conclusion'] = (f"{'Evidence against' if test['statistically_significant'] else 'Insufficient evidence against'} the null hypothesis "
                f"after Holm correction (adjusted p={probability:.4e}). This exploratory association does not establish causation or business importance.")

    executive_summary = ""
    if tests_run:
        # Build a structured, LLM-friendly evidence block
        evidence_blocks = []
        for t in tests_run:
            test_name = t.get("test", "Statistical Test")
            hypo = t.get("hypothesis", "")
            p_val = t.get("p_value_formatted", t.get("p_value", "N/A"))
            is_sig = t.get("statistically_significant", False)
            conclusion = t.get("conclusion", "")
            effect = next((t[key] for key in ("cohens_d", "cramers_v", "common_language_effect_size") if t.get(key) is not None), None)
            effect_label = t.get("effect_size_label") or t.get("association_strength") or ""

            block = (
                f"TEST: {test_name}\n"
                f"Hypothesis: {hypo}\n"
                f"Result: p={p_val}, Significant={is_sig}\n"
                f"Effect size: {effect} ({effect_label})\n"
                f"Conclusion: {conclusion}"
            )
            evidence_blocks.append(block)

        prompt = f"""You are a Chief Quantitative Analyst explaining statistical test results to executive leadership.

STATISTICAL EVIDENCE (computed by SciPy — DO NOT change any numbers or p-values):
{chr(10).join(['─'*60 + chr(10) + b for b in evidence_blocks])}

Guidelines for your response:
- Explain that p is the probability of results at least this extreme under the null hypothesis and test assumptions. It is not the probability that the null is true or the difference is due to chance.
- Report the effect size descriptively. No practical-importance threshold has been supplied: never claim the effect matters or is too small to affect business decisions.
- Use Holm-adjusted significance. A non-significant result does not prove equality, random noise or absence of a meaningful effect. These exploratory observational comparisons do not establish causation; assess effect sizes and assumptions before decisions.
- Keep to 3 concise bullet points total

Do NOT restate the technical test names. Write for a VP or CEO who understands business but not statistics."""

        try:
            executive_summary = invoke_llm(
                prompt=prompt,
                system_prompt="Explain exploratory statistical evidence. Do not infer business importance, equivalence, causality or absence of an effect.",
                tier="fast_reasoning",
                task="hypothesis",
                temperature=0.1,
            ).strip()
        except Exception as e:
            logger.warning(f"Hypothesis LLM interpretation skipped: {e}")
            # Deterministic fallback summary
            sig_tests = [t for t in tests_run if t.get("statistically_significant")]
            executive_summary = (
                f"{len(tests_run)} statistical tests conducted. "
                f"{len(sig_tests)} showed significant differences. "
                + " | ".join([t.get("conclusion", "") for t in tests_run[:2]])
            )
    else:
        executive_summary = "No multi-group dimensions met the minimum sample requirements for formal hypothesis testing."

    if tests_run and unsupported_claims(executive_summary):
        executive_summary = "\n".join(f"- **{t.get('hypothesis', 'Statistical comparison')}**: {t['conclusion']}" for t in tests_run)
        executive_summary += "\n\nA non-significant result does not establish equality or absence of a meaningful effect. Practical importance requires a domain threshold and assessment of uncertainty."

    hypothesis_results = {
        "tests_conducted": tests_run,
        "executive_summary": executive_summary,
        "tests_count": len(tests_run),
        "multiple_testing_correction": "Holm",
        "interpretation_notice": "Exploratory tests assume independent observations. P-values do not establish causation or practical importance.",
        "significant_tests": sum(1 for t in tests_run if t.get("statistically_significant")),
    }

    execution_steps.append(
        f"Hypothesis Agent: Ran {len(tests_run)} statistical tests "
        f"({hypothesis_results['significant_tests']} significant at α=0.05)."
    )

    return {
        **state,
        "hypothesis_results": hypothesis_results,
        "execution_steps": execution_steps,
        "errors": errors,
    }
