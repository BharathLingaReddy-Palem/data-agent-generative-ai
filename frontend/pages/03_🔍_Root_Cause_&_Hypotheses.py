import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Root Cause & Hypotheses | AI Data Analyst", page_icon="🔍", layout="wide")

from frontend.auth import require_login
current_account = require_login()

st.markdown("# 🔍 Root Cause Diagnostics & Hypothesis Testing")
st.markdown("Discover **WHY** metrics moved, which 20% of segments drove 80% of volume, and whether observed patterns are statistically significant.")

analysis = st.session_state.get("analysis")

if not analysis:
    st.warning("⚠️ No completed analysis found. Please run the analysis on the **Upload & Audit** page first.")
    if st.button("Go to Upload & Audit"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
    st.stop()

diagnostic = analysis.get("diagnostic_results", {})
hypothesis = analysis.get("hypothesis_results", {})

# ───────────────────────────────────────────────────────────
# 1. EXECUTIVE ROOT CAUSE BRIEFING
# ───────────────────────────────────────────────────────────
st.markdown("## 1. 🎯 Diagnostic Narrative (The 'Why')")
narrative = diagnostic.get("diagnostic_narrative", "Diagnostic analysis completed.")
st.info(narrative)

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 2. PARETO 80/20 ANALYSIS
# ───────────────────────────────────────────────────────────
st.markdown("## 2. ⚖️ Pareto 80/20 Concentration Analysis")
pareto_dict = diagnostic.get("pareto_analysis", {})

if pareto_dict:
    for dim, p_data in pareto_dict.items():
        st.markdown(f"### Dimension: `{dim.title()}`")
        col_p1, col_p2, col_p3 = st.columns(3)
        col_p1.metric("Categories Driving 80%", f"{p_data.get('categories_driving_80pct')} of {p_data.get('total_categories')}")
        col_p2.metric("Concentration Ratio", f"{p_data.get('concentration_ratio_pct')}%")
        col_p3.metric("Pareto Rule Holds?", "✅ Yes" if p_data.get("pareto_rule_holds") else "ℹ️ Spread Out")

        st.caption(f"📢 **Summary:** {p_data.get('summary')}")

        # Top categories table
        top_cats = p_data.get("top_categories", [])
        if top_cats:
            with st.expander(f"View Cumulative Share Table ({dim.title()})", expanded=False):
                p_df = pd.DataFrame(top_cats)
                st.dataframe(p_df, use_container_width=True, hide_index=True)
else:
    st.info("Pareto analysis was not applicable for the selected dimensions.")

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 3. PERIOD-OVER-PERIOD VARIANCE DECOMPOSITION
# ───────────────────────────────────────────────────────────
variance_decomp = diagnostic.get("variance_decomposition")
if variance_decomp:
    st.markdown(f"## 3. 🌊 Period-over-Period Variance Drivers ({variance_decomp.get('period_1')} vs {variance_decomp.get('period_2')})")
    col_v1, col_v2, col_v3 = st.columns(3)
    col_v1.metric("Initial Period Total", f"${variance_decomp.get('total_p1', 0):,.2f}")
    col_v2.metric("Final Period Total", f"${variance_decomp.get('total_p2', 0):,.2f}")
    col_v3.metric("Net Change (Delta)", f"${variance_decomp.get('total_delta', 0):,.2f}", f"{variance_decomp.get('growth_pct', 0):+.2f}%")

    col_pos, col_neg = st.columns(2)
    with col_pos:
        st.markdown("#### 🟢 Top Positive Drivers (Gains)")
        pos_df = pd.DataFrame(variance_decomp.get("top_positive_drivers", []))
        if not pos_df.empty:
            st.dataframe(pos_df, use_container_width=True, hide_index=True)
        else:
            st.write("No positive drivers found.")

    with col_neg:
        st.markdown("#### 🔴 Top Negative Contributors (Drops)")
        neg_df = pd.DataFrame(variance_decomp.get("top_negative_drivers", []))
        if not neg_df.empty:
            st.dataframe(neg_df, use_container_width=True, hide_index=True)
        else:
            st.write("No negative drivers found.")

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 4. STATISTICAL HYPOTHESIS TESTING
# ───────────────────────────────────────────────────────────
st.markdown("## 4. 📐 Statistical Significance Validation")
tests = hypothesis.get("tests_conducted", [])
summary = hypothesis.get("executive_summary", "")

st.markdown("### Executive Significance Summary")
st.markdown(summary)

if tests:
    st.markdown("### Formal Statistical Tests")
    for t in tests:
        is_sig = t.get("statistically_significant", False)
        sig_badge = "🟢 Significant after Holm correction" if is_sig else "🟠 Insufficient evidence after Holm correction"
        with st.container():
            st.markdown(f"""
            <div style="background: #1E293B; border-radius: 8px; padding: 1.2rem; margin-bottom: 0.8rem; border-left: 4px solid {'#10B981' if is_sig else '#F59E0B'};">
                <h4 style="margin: 0; color: #F8FAFC;">🧪 {t.get('test', 'Statistical Test')}</h4>
                <p style="margin: 0.25rem 0; color: #94A3B8;"><b>Hypothesis:</b> {t.get('hypothesis', 'Group comparison')}</p>
                <p style="margin: 0.25rem 0;"><b>Verdict:</b> {sig_badge} | <b>Adjusted p-value:</b> <code>{t.get('p_value_adjusted', t.get('p_value', 1.0)):.4e}</code></p>
                <p style="margin: 0.25rem 0; color: #E2E8F0;"><i>{t.get('conclusion', '')}</i></p>
            </div>
            """, unsafe_allow_html=True)
