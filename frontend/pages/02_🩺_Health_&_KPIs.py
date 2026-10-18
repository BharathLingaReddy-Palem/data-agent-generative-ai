import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="Data Health & KPIs | AI Data Analyst", page_icon="🩺", layout="wide")

from frontend.auth import require_login
current_account = require_login()

st.markdown("# 🩺 Data Health Audit & Core Business KPIs")
st.markdown("Automated data hygiene score, anomaly detection, semantic dictionary, and business performance metrics.")

analysis = st.session_state.get("analysis")

if not analysis:
    st.warning("⚠️ No completed analysis found. Please upload a dataset and run the analysis on the **Upload & Audit** page first.")
    if st.button("Go to Upload & Audit"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
    st.stop()

# ───────────────────────────────────────────────────────────
# 1. DATA HEALTH AUDIT
# ───────────────────────────────────────────────────────────
st.markdown("## 1. 🏥 Data Health Audit")

health_score = analysis.get("health_score", 100)
quality = analysis.get("quality_audit", {})

col_g, col_s = st.columns([1, 2])
with col_g:
    # Health Score Metric Card
    color = "#10B981" if health_score >= 85 else ("#F59E0B" if health_score >= 65 else "#EF4444")
    st.markdown(f"""
    <div style="background: #1E293B; border-radius: 12px; padding: 1.5rem; text-align: center; border: 2px solid {color};">
        <h3 style="margin: 0; color: #94A3B8;">DATA HEALTH SCORE</h3>
        <h1 style="font-size: 3.5rem; margin: 0.5rem 0; color: {color};">{health_score:.1f}<span style="font-size: 1.5rem;">/100</span></h1>
        <p style="margin: 0; font-weight: 600; color: #F8FAFC;">Status: {quality.get('health_status', 'Good')}</p>
    </div>
    """, unsafe_allow_html=True)

with col_s:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Records", f"{quality.get('total_rows', 0):,}")
    c2.metric("Total Columns", f"{quality.get('total_columns', 0)}")
    c3.metric("Missing Cell Rate", f"{quality.get('overall_missing_pct', 0):.2f}%")

    c4, c5, c6 = st.columns(3)
    c4.metric("Duplicate Rows", f"{quality.get('duplicate_rows', 0)}")
    c5.metric("Primary Key Collisions", f"{quality.get('id_collisions', 0)}")
    c6.metric("Anomalies Detected", f"{len(quality.get('anomalies', []))}")

# Anomaly Alerts
anomalies = quality.get("anomalies", [])
if anomalies:
    st.markdown("### ⚠️ Detected Anomalies & Risk Items")
    for a in anomalies:
        st.error(f"**{a.get('column')}** [{a.get('severity', 'Medium')} Risk]: {a.get('issue')}")
else:
    st.success("✅ No structural anomalies or negative value violations detected.")

# Missing values table
missing_cols = quality.get("missing_columns", {})
if missing_cols:
    with st.expander("🔍 View Missing Data Details by Column", expanded=False):
        m_df = pd.DataFrame.from_dict(missing_cols, orient="index")
        st.dataframe(m_df, use_container_width=True)

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 2. CORE BUSINESS KPIS
# ───────────────────────────────────────────────────────────
st.markdown("## 2. 💼 Business KPIs & Domain Metrics")
kpi_data = analysis.get("kpi_results", {})
domain = kpi_data.get("domain", "General Business")
st.markdown(f"**Inferred Business Domain:** `{domain}`")

metrics = kpi_data.get("kpi_metrics", [])
if metrics:
    cols = st.columns(min(len(metrics), 4))
    for i, m in enumerate(metrics[:4]):
        with cols[i]:
            growth = m.get("growth_pct")
            delta_str = f"{growth:+.1f}% MoM" if growth is not None else None
            st.metric(
                label=m.get("metric_name", ""),
                value=m.get("formatted_total", ""),
                delta=delta_str,
            )
            st.caption(f"Average: {m.get('formatted_mean', '')}")

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 3. INDUSTRY BENCHMARKS AUDIT (Phase 3)
# ───────────────────────────────────────────────────────────
st.markdown("## 3. 🌐 Industry Benchmark Comparison")
st.markdown("How your performance measures against McKinsey, Gartner, and industry sector percentiles.")

benchmark_results = analysis.get("benchmark_results")
if not benchmark_results:
    try:
        from backend.tools.benchmarks import run_full_benchmark_audit
        benchmark_results = run_full_benchmark_audit(
            kpi_metrics=kpi_data.get("kpi_metrics", []) + kpi_data.get("domain_specific_kpis", []),
            domain=domain,
        )
    except Exception:
        benchmark_results = {}

if benchmark_results and benchmark_results.get("metrics_benchmarked", 0) > 0:
    pos = benchmark_results.get("overall_competitive_position", "Competitive")
    pos_color = "#10B981" if "Leader" in pos else ("#3B82F6" if "Competitive" in pos else "#F59E0B")
    
    st.markdown(f"""
    <div style="background: #1E293B; border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; border-left: 5px solid {pos_color}; display: flex; align-items: center; justify-content: space-between;">
        <div>
            <span style="color: #94A3B8; font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">Overall Competitive Standing</span>
            <h3 style="margin: 0.2rem 0; color: #F8FAFC;">{pos}</h3>
            <span style="color: #64748B; font-size: 0.85rem;">Domain: {benchmark_results.get('domain', domain)} | Evaluated {benchmark_results.get('metrics_benchmarked')} key metrics</span>
        </div>
        <div style="text-align: right;">
            <span style="background: {pos_color}22; color: {pos_color}; padding: 6px 14px; border-radius: 20px; font-weight: 700; font-size: 0.95rem; border: 1px solid {pos_color}44;">
                {pos}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    verdicts = benchmark_results.get("benchmark_verdicts", [])
    if verdicts:
        bm_rows = []
        for v in verdicts:
            bm_rows.append({
                "Metric": v.get("metric_label"),
                "Your Value": f"{v.get('actual_value')}{v.get('unit')}",
                "Rating": v.get("rating"),
                "Percentile": v.get("percentile_estimate"),
                "Industry Good": f"{v['benchmarks'].get('good')}{v.get('unit')}",
                "World Class (Top 10%)": f"{v['benchmarks'].get('world_class')}{v.get('unit')}",
                "Action Guidance": v.get("recommendation"),
                "Benchmark Source": v.get("source"),
            })
        bm_df = pd.DataFrame(bm_rows)
        st.dataframe(bm_df, use_container_width=True, hide_index=True)
else:
    st.info(f"ℹ️ General domain detected (`{domain}`). Upload specific sales, SaaS, operations, or finance datasets to activate automated industry benchmark percentiles.")

st.markdown("---")

# ───────────────────────────────────────────────────────────
# 4. SEMANTIC DATA DICTIONARY
# ───────────────────────────────────────────────────────────
st.markdown("## 4. 🗂️ Semantic Data Dictionary")
schema_meta = analysis.get("schema_metadata", {})
cols_meta = schema_meta.get("columns", {})

if cols_meta:
    dict_rows = []
    for c, meta in cols_meta.items():
        dict_rows.append({
            "Column Name": c,
            "Semantic Role": meta.get("semantic_type", "Dimension"),
            "Business Description": meta.get("business_description", c),
            "Key Metric?": "⭐ Yes" if meta.get("is_key_metric") else "No",
        })
    dict_df = pd.DataFrame(dict_rows)
    st.dataframe(dict_df, use_container_width=True, hide_index=True)
