import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io

from backend.tools.comparator import compare_datasets
from backend.services.upload_limits import parse_upload

st.set_page_config(page_title="Multi-Dataset Comparison | AI Data Analyst", page_icon="⚖️", layout="wide")

from frontend.auth import require_login
current_account = require_login()

st.markdown("# ⚖️ Multi-Dataset Comparison & Variance Intelligence")
st.markdown("Compare periods (e.g. Q1 vs Q2), cohorts, regions, or A/B scenarios with automated Welch's t-test statistical validation, category mix shifts, and C-level executive briefing.")

# ───────────────────────────────────────────────────────────
# Dataset Selection / Upload Section
# ───────────────────────────────────────────────────────────
input_mode = st.radio(
    "Select Comparison Mode:",
    ["Upload Two Datasets (Period A vs Period B)", "Compare Active Analysis Dataset vs New File", "⚡ Load Interactive Demo Data (Q1 vs Q2 E-Commerce)"],
    horizontal=True,
)

df_a = None
df_b = None
default_name_a = "Period A (Baseline)"
default_name_b = "Period B (Comparison)"

if input_mode == "Upload Two Datasets (Period A vs Period B)":
    c_up1, c_up2 = st.columns(2)
    with c_up1:
        st.markdown("#### 📁 Dataset A (Baseline / Prior Period)")
        file_a = st.file_uploader("Upload CSV for Dataset A", type=["csv"], key="file_a")
        custom_name_a = st.text_input("Dataset A Label:", "Q1 2024 (Baseline)", key="name_a")
        if file_a:
            try:
                df_a = parse_upload(file_a.getvalue(), file_a.name)
                st.success(f"Loaded Dataset A: {len(df_a):,} rows, {len(df_a.columns)} cols")
            except Exception as e:
                st.error(f"Error reading File A: {e}")

    with c_up2:
        st.markdown("#### 📁 Dataset B (Current / Comparison Period)")
        file_b = st.file_uploader("Upload CSV for Dataset B", type=["csv"], key="file_b")
        custom_name_b = st.text_input("Dataset B Label:", "Q2 2024 (Current)", key="name_b")
        if file_b:
            try:
                df_b = parse_upload(file_b.getvalue(), file_b.name)
                st.success(f"Loaded Dataset B: {len(df_b):,} rows, {len(df_b.columns)} cols")
            except Exception as e:
                st.error(f"Error reading File B: {e}")

    default_name_a = custom_name_a
    default_name_b = custom_name_b

elif input_mode == "Compare Active Analysis Dataset vs New File":
    active_analysis = st.session_state.get("analysis")
    from backend.services.dataset_views import active_dataframe
    active_data = active_dataframe(st.session_state) if st.session_state.get("df") is not None else None
    active_name = st.session_state.get("dataset_name", "Active Dataset")

    c_up1, c_up2 = st.columns(2)
    with c_up1:
        st.markdown("#### 📁 Dataset A (Current Active Session)")
        if active_data is not None:
            df_a = active_data
            st.success(f"Using Active Dataset: {active_name} ({len(df_a):,} rows, {len(df_a.columns)} cols)")
        else:
            st.warning("⚠️ No active dataset found in memory. Please run analysis on Upload page first or choose another mode.")
        default_name_a = st.text_input("Dataset A Label:", f"{active_name} (Baseline)", key="name_act_a")

    with c_up2:
        st.markdown("#### 📁 Dataset B (Comparison Period File)")
        file_b = st.file_uploader("Upload Comparison CSV", type=["csv"], key="file_b_active")
        default_name_b = st.text_input("Dataset B Label:", "Comparison Cohort", key="name_act_b")
        if file_b:
            try:
                df_b = parse_upload(file_b.getvalue(), file_b.name)
                st.success(f"Loaded Dataset B: {len(df_b):,} rows, {len(df_b.columns)} cols")
            except Exception as e:
                st.error(f"Error reading File B: {e}")

else:  # Interactive Demo Data
    st.info("💡 Loading pre-configured multi-period Retail dataset (Q1 Baseline vs Q2 Growth Period) with customer segments, revenue, profit, and discount rates.")
    np.random.seed(42)
    
    # Q1 Baseline
    cats = ["Technology", "Office Supplies", "Furniture"]
    segs = ["Consumer", "Corporate", "Home Office"]
    n_a = 600
    df_a = pd.DataFrame({
        "order_id": [f"CA-2024-{1000+i}" for i in range(n_a)],
        "category": np.random.choice(cats, n_a, p=[0.35, 0.45, 0.20]),
        "segment": np.random.choice(segs, n_a, p=[0.50, 0.30, 0.20]),
        "sales": np.round(np.random.gamma(shape=3.0, scale=60.0, size=n_a), 2),
        "profit": np.round(np.random.normal(loc=28.0, scale=12.0, size=n_a), 2),
        "discount": np.round(np.random.uniform(0.0, 0.25, size=n_a), 2),
    })

    # Q2 Comparison (Higher tech volume, higher margins, tighter discount)
    n_b = 750
    df_b = pd.DataFrame({
        "order_id": [f"CA-2024-{2000+i}" for i in range(n_b)],
        "category": np.random.choice(cats, n_b, p=[0.45, 0.40, 0.15]), # Tech grew
        "segment": np.random.choice(segs, n_b, p=[0.45, 0.35, 0.20]), # Corporate grew
        "sales": np.round(np.random.gamma(shape=3.5, scale=65.0, size=n_b), 2),
        "profit": np.round(np.random.normal(loc=36.0, scale=14.0, size=n_b), 2),
        "discount": np.round(np.random.uniform(0.0, 0.18, size=n_b), 2), # Discounts reduced
    })
    default_name_a = "Q1 2024 (Baseline)"
    default_name_b = "Q2 2024 (Current)"

    c_prev1, c_prev2 = st.columns(2)
    with c_prev1:
        st.caption(f"**Dataset A preview:** {default_name_a} ({len(df_a):,} rows)")
        st.dataframe(df_a.head(3), use_container_width=True)
    with c_prev2:
        st.caption(f"**Dataset B preview:** {default_name_b} ({len(df_b):,} rows)")
        st.dataframe(df_b.head(3), use_container_width=True)

# ───────────────────────────────────────────────────────────
# Execution Parameters
# ───────────────────────────────────────────────────────────
if df_a is not None and df_b is not None:
    st.markdown("---")
    st.markdown("### ⚙️ Comparison Configuration")

    common_cols = sorted(list(set(df_a.columns).intersection(set(df_b.columns))))
    num_cols = sorted(list(set(df_a.select_dtypes(include=[np.number]).columns).intersection(set(df_b.select_dtypes(include=[np.number]).columns))))
    cat_cols = sorted(list(set(df_a.select_dtypes(include=['object', 'category']).columns).intersection(set(df_b.select_dtypes(include=['object', 'category']).columns))))

    col_cfg1, col_cfg2, col_btn = st.columns([2, 2, 2])
    with col_cfg1:
        selected_seg = st.selectbox(
            "Primary Segment Column (Mix Shift Analysis):",
            options=["Auto-detect"] + cat_cols,
            index=0,
        )
    with col_cfg2:
        selected_met = st.selectbox(
            "Primary Metric Column (Driver Decomposition):",
            options=["Auto-detect"] + num_cols,
            index=0,
        )
    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        run_comp = st.button("⚡ Run Comparative Analysis", type="primary", use_container_width=True)

    if run_comp or "comp_result" in st.session_state:
        if run_comp:
            with st.spinner("Analyzing variances, calculating Welch's t-test, and generating executive briefing..."):
                seg_arg = None if selected_seg == "Auto-detect" else selected_seg
                met_arg = None if selected_met == "Auto-detect" else selected_met
                res = compare_datasets(
                    df_a=df_a,
                    df_b=df_b,
                    name_a=default_name_a,
                    name_b=default_name_b,
                    segment_col=seg_arg,
                    key_metric_col=met_arg,
                )
                st.session_state["comp_result"] = res
        
        comp = st.session_state.get("comp_result")
        if comp and comp.get("status") == "success":
            vol = comp["volume_summary"]
            
            # ── 1. Top KPI Summary Cards ──
            st.markdown("---")
            st.markdown("### 1. 📊 Executive Variance Summary")
            
            kpi_c1, kpi_c2, kpi_c3, kpi_c4 = st.columns(4)
            with kpi_c1:
                st.metric(
                    label=f"Total Records ({vol['name_b']})",
                    value=f"{vol['rows_b']:,}",
                    delta=f"{vol['row_pct_change']:+.1f}% vs {vol['name_a']}",
                )
            with kpi_c2:
                sig_count = comp.get("significant_metrics_count", 0)
                st.metric(
                    label="Statistically Significant Shifts",
                    value=f"{sig_count} Metrics",
                    delta="p < 0.05 (Welch's / Mann-Whitney)",
                    delta_color="normal",
                )
            with kpi_c3:
                top_m = comp["metric_comparisons"][0] if comp.get("metric_comparisons") else None
                if top_m:
                    st.metric(
                        label=f"Primary Metric ({top_m['column']})",
                        value=f"{top_m['sum_b']:,.0f}",
                        delta=f"{top_m['sum_pct_change']:+.1f}% Total",
                    )
                else:
                    st.metric("Primary Metric", "—")
            with kpi_c4:
                shifts = comp.get("segment_shifts", [])
                lead_gain = shifts[0] if shifts else None
                if lead_gain:
                    st.metric(
                        label=f"Top Gaining Segment ({comp.get('chosen_segment_col', 'Segment')})",
                        value=lead_gain['segment'],
                        delta=f"{lead_gain['share_delta_pct']:+.1f}% Share",
                    )
                else:
                    st.metric("Top Segment Shift", "—")

            # ── 2. AI Executive Comparative Narrative ──
            st.markdown("### 2. 📝 C-Level Comparative Briefing")
            narrative = comp.get("executive_narrative", "")
            st.markdown(f"""
            <div style="background: #0F172A; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border-left: 5px solid #3B82F6;">
                {narrative}
            </div>
            """, unsafe_allow_html=True)

            # ── 3. Interactive Visual Comparison Charts ──
            st.markdown("### 3. 📈 Side-by-Side Visual Comparison")
            c_viz1, c_viz2 = st.columns(2)

            with c_viz1:
                # Grouped Bar Chart for Top 4 Metrics
                top_metrics = comp["metric_comparisons"][:4]
                if top_metrics:
                    chart_rows = []
                    for m in top_metrics:
                        chart_rows.append({"Metric": m["column"], "Dataset": vol["name_a"], "Average Value": m["mean_a"]})
                        chart_rows.append({"Metric": m["column"], "Dataset": vol["name_b"], "Average Value": m["mean_b"]})
                    cdf = pd.DataFrame(chart_rows)
                    fig_bar = px.bar(
                        cdf,
                        x="Metric",
                        y="Average Value",
                        color="Dataset",
                        barmode="group",
                        title=f"Mean Metric Comparison: {vol['name_a']} vs {vol['name_b']}",
                        color_discrete_sequence=["#64748B", "#3B82F6"],
                        template="plotly_dark",
                    )
                    fig_bar.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_bar, use_container_width=True)

            with c_viz2:
                # Segment Share Shift Chart
                if comp.get("segment_shifts"):
                    seg_df = pd.DataFrame(comp["segment_shifts"][:6])
                    fig_shift = px.bar(
                        seg_df,
                        x="share_delta_pct",
                        y="segment",
                        orientation="h",
                        title=f"Segment Share Shift (% Points) in {comp.get('chosen_segment_col', 'Category')}",
                        color="share_delta_pct",
                        color_continuous_scale=["#EF4444", "#94A3B8", "#10B981"],
                        labels={"share_delta_pct": "Share Shift (%)", "segment": "Segment"},
                        template="plotly_dark",
                    )
                    fig_shift.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_shift, use_container_width=True)

            # ── 4. Full Statistical Delta Scorecard Table ──
            st.markdown("### 4. 🔬 Statistical Metric Deltas & Hypothesis Testing")
            st.markdown("Calculates absolute delta, percentage shift, Welch's t-test p-value, and Cohen's d effect size for every common numeric column.")

            metric_rows = []
            for m in comp["metric_comparisons"]:
                sig_badge = "Unavailable" if not m.get("test_available", True) else "⭐ Significant after Holm correction" if m["is_statistically_significant"] else "Not Significant"
                metric_rows.append({
                    "Metric": m["column"],
                    f"{vol['name_a']} Mean": f"{m['mean_a']:,.2f}",
                    f"{vol['name_b']} Mean": f"{m['mean_b']:,.2f}",
                    "Mean Delta": f"{m['mean_delta']:+,.2f}",
                    "Mean Shift %": f"{m['mean_pct_change']:+.1f}%",
                    f"{vol['name_a']} Sum": f"{m['sum_a']:,.0f}",
                    f"{vol['name_b']} Sum": f"{m['sum_b']:,.0f}",
                    "Total Shift %": f"{m['sum_pct_change']:+.1f}%",
                    "Direction": m["direction"],
                    "p-Value (Welch, Holm-adjusted)": m.get("p_value_adjusted_formatted", "Unavailable"),
                    "Statistical Significance": sig_badge,
                    "Effect Size (Cohen's d)": f"{m['effect_size']} ({m['cohens_d']})",
                })
            m_scorecard_df = pd.DataFrame(metric_rows)
            st.dataframe(m_scorecard_df, use_container_width=True, hide_index=True)

            # ── 5. Segment Mix Shift & Drivers Breakdown ──
            c_seg1, c_seg2 = st.columns(2)

            with c_seg1:
                st.markdown(f"#### 🧬 Segment Evolution: `{comp.get('chosen_segment_col', 'Category')}`")
                if comp.get("segment_shifts"):
                    shifts_table = pd.DataFrame(comp["segment_shifts"])
                    st.dataframe(shifts_table, use_container_width=True, hide_index=True)

                if comp.get("new_segments"):
                    st.success(f"🌱 **New Segments in {vol['name_b']}:** {', '.join(comp['new_segments'])}")
                if comp.get("lost_segments"):
                    st.error(f"🥀 **Lost / Churned Segments from {vol['name_a']}:** {', '.join(comp['lost_segments'])}")

            with c_seg2:
                st.markdown(f"#### 🎯 Variance Driver Decomposition (`{comp.get('chosen_metric', 'Metric')}`)")
                if comp.get("growth_drivers"):
                    drivers_table = pd.DataFrame(comp["growth_drivers"])
                    st.dataframe(drivers_table, use_container_width=True, hide_index=True)
                else:
                    st.caption("No categorical driver breakdown available for the selected columns.")

            # ── 6. Export Comparative Report ──
            st.markdown("---")
            st.markdown("### 📥 Export Comparative Documentation")
            c_exp1, c_exp2 = st.columns(2)

            with c_exp1:
                # Markdown Export
                comp_md = f"""# ⚖️ Executive Comparative Report: {vol['name_a']} vs {vol['name_b']}
**Generated by Autonomous AI Data Analyst**

{narrative}

---

## Metric Variance Scorecard
| Metric | {vol['name_a']} Mean | {vol['name_b']} Mean | Shift % | Total Shift % | Significance |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""
                for m in comp["metric_comparisons"]:
                    sig_txt = "Significant after Holm correction" if m['is_statistically_significant'] else "Not Significant"
                    comp_md += f"| {m['column']} | {m['mean_a']} | {m['mean_b']} | {m['mean_pct_change']:+.1f}% | {m['sum_pct_change']:+.1f}% | {sig_txt} |\n"

                st.download_button(
                    label="📄 Download Comparative Report (.md)",
                    data=comp_md,
                    file_name=f"comparison_{vol['name_a'][:6]}_vs_{vol['name_b'][:6]}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with c_exp2:
                # CSV Export
                csv_bytes = m_scorecard_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Export Delta Metrics Scorecard (.csv)",
                    data=csv_bytes,
                    file_name=f"metrics_variance_{vol['name_a'][:6]}_vs_{vol['name_b'][:6]}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
