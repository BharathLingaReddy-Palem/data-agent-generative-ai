import streamlit as st
import json
import plotly.io as pio

st.set_page_config(page_title="Visual Evidence | AI Data Analyst", page_icon="📈", layout="wide")

from frontend.auth import require_login
current_account = require_login()

st.markdown("# 📈 Visual Evidence & Interactive Dashboards")
st.markdown("Publication-grade, interactive Plotly charts illustrating root-cause drivers, trends, and segment breakdowns.")

analysis = st.session_state.get("analysis")

if not analysis:
    st.warning("⚠️ No completed analysis found. Please run the analysis on the **Upload & Audit** page first.")
    if st.button("Go to Upload & Audit"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
    st.stop()

charts = analysis.get("charts", [])

if not charts:
    st.info("No charts generated for this dataset.")
else:
    for i, c in enumerate(charts):
        st.markdown(f"### {c.get('title', f'Chart {i+1}')}")
        chart_json = c.get("json")
        if chart_json:
            try:
                fig = pio.from_json(chart_json)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Failed to render chart: {e}")
        st.markdown("---")
