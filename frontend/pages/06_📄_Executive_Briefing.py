import streamlit as st
import os
from pathlib import Path
from backend.config import REPORTS_DIR

st.set_page_config(page_title="Executive Briefing | AI Data Analyst", page_icon="📄", layout="wide")

from frontend.auth import require_login
current_account = require_login()

st.markdown("# 📄 Executive Intelligence Report & Action Plan")
st.markdown("C-level briefing, strategic recommendations, industry benchmarks, and exportable documentation.")

analysis = st.session_state.get("analysis")

if not analysis:
    st.warning("⚠️ No completed analysis found. Please run the analysis on the **Upload & Audit** page first.")
    if st.button("Go to Upload & Audit"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
    st.stop()

dataset_name = st.session_state.get("dataset_name", "Dataset")
report_md = analysis.get("report_markdown", "")
report_pdf_path = analysis.get("report_pdf_path", "")
report_pdf_url = analysis.get("report_pdf_url", "")
report_pptx_path = analysis.get("report_pptx_path", "")
report_summary = analysis.get("report_summary", "")
benchmark_results = analysis.get("benchmark_results", {})

# ───────────────────────────────────────────────────────────
# Competitive Position Callout (if benchmarks evaluated)
# ───────────────────────────────────────────────────────────
if benchmark_results and benchmark_results.get("metrics_benchmarked", 0) > 0:
    pos = benchmark_results.get("overall_competitive_position", "Competitive")
    pos_color = "#10B981" if "Leader" in pos else ("#3B82F6" if "Competitive" in pos else "#F59E0B")
    st.markdown(f"""
    <div style="background: #0F172A; border: 1px solid {pos_color}55; border-radius: 12px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; display: flex; align-items: center; justify-content: space-between;">
        <div>
            <span style="color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Industry Benchmark Position</span>
            <h3 style="margin: 0.2rem 0; color: #F8FAFC;">{pos}</h3>
            <span style="color: #64748B; font-size: 0.85rem;">Domain: {benchmark_results.get('domain')} • {benchmark_results.get('metrics_benchmarked')} KPIs verified against sector standards</span>
        </div>
        <div style="background: {pos_color}22; border: 1px solid {pos_color}; color: {pos_color}; padding: 8px 18px; border-radius: 20px; font-weight: 700; font-size: 1rem;">
            {pos}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────
# Export Documentation (PDF, PowerPoint, Markdown, Cloud)
# ───────────────────────────────────────────────────────────
st.markdown("### 📥 Export Executive Documentation")
c_d1, c_d2, c_d3, c_d4 = st.columns(4)

with c_d1:
    st.download_button(
        label="📄 Markdown Report (.md)",
        data=report_md,
        file_name=f"analyst_report_{dataset_name.lower().replace(' ', '_')}.md",
        mime="text/markdown",
        use_container_width=True,
    )

with c_d2:
    if report_pdf_path and Path(report_pdf_path).suffix == ".pdf" and os.path.exists(report_pdf_path):
        with open(report_pdf_path, "rb") as f:
            pdf_bytes = f.read()
        st.download_button(
            label="📑 Executive PDF Report",
            data=pdf_bytes,
            file_name=os.path.basename(report_pdf_path),
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.button("📑 PDF Pending", disabled=True, use_container_width=True)

with c_d3:
    if report_pptx_path and Path(report_pptx_path).suffix == ".pptx" and os.path.exists(report_pptx_path):
        with open(report_pptx_path, "rb") as f:
            pptx_bytes = f.read()
        st.download_button(
            label="📊 Executive PowerPoint (.pptx)",
            data=pptx_bytes,
            file_name=os.path.basename(report_pptx_path),
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )
    else:
        st.button("📊 PowerPoint Pending", disabled=True, use_container_width=True)

with c_d4:
    st.caption("Download your generated documents using the export buttons.")

# ───────────────────────────────────────────────────────────
# PowerPoint Deck Structure Preview
# ───────────────────────────────────────────────────────────
with st.expander("📊 Executive PowerPoint Deck Overview (8 Slides Included)", expanded=False):
    st.markdown("""
    Your auto-generated PowerPoint deck (`.pptx`) is formatted with a modern Dark Navy C-Level theme:
    - **Slide 1:** Title Slide (Dataset, Date, Health Score, Domain)
    - **Slide 2:** Data Health & Quality Hygiene Audit
    - **Slide 3:** Core Business Performance KPIs (Totals, Averages, Growth)
    - **Slide 4:** Industry Benchmark Percentile Comparison
    - **Slide 5:** Time-Series Growth & Seasonality Profile
    - **Slide 6:** Root Cause Diagnostic & Pareto Breakdown
    - **Slide 7:** Statistical Significance & Hypothesis Testing
    - **Slide 8:** Prioritized Strategic Leadership Action Plan
    """)

st.markdown("---")

# Render Markdown Report
st.markdown(report_md)
