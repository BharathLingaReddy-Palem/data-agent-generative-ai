import streamlit as st
import pandas as pd
import requests
import json
import hashlib
import uuid
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import BACKEND_URL
from backend.graph.workflow import run_analyst_pipeline
from backend.graph.state import AgentState
from backend.services.cleaner import strip_column_names
from backend.services.dataset_views import active_dataframe
from backend.services.upload_limits import parse_upload
from frontend.datasets import fetch_sample_dataframe, save_active_dataset

st.set_page_config(page_title="Upload & Audit | AI Data Analyst", page_icon="📥", layout="wide")

from frontend.auth import require_login
current_account = require_login()

def reset_derived_data():
    for key in ('analysis', 'df_cleaned', 'cleaning_audit', 'cleaning_options',
                'cleaning_target_source', 'automl', 'model_invalidated', 'chat_messages', 'chat_history', 'comp_result'):
        st.session_state.pop(key, None)


st.markdown("# 📥 Ingest Dataset & Launch Autonomous Audit")
st.markdown("Upload your tabular business data (CSV or Excel) or test with an enterprise benchmark.")

tab1, tab2 = st.tabs(["📁 Upload Your File", "🏢 Load Enterprise Benchmark"])

with tab1:
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx", "xls"])
    user_question_upload = st.text_input(
        "Ask a specific analytical question (optional):",
        placeholder="e.g. Why did revenue drop in Q3? Which customer tier drives 80% of churn?",
    )
    
    if uploaded_file is not None:
        try:
            df = parse_upload(uploaded_file.getvalue(), uploaded_file.name)
            fingerprint = hashlib.sha256(uploaded_file.getvalue()).hexdigest() + uploaded_file.name
            if st.session_state.get('uploaded_fingerprint') != fingerprint:
                project_id = str(uuid.uuid4())
                dataset_name = uploaded_file.name.rsplit('.', 1)[0]
                candidate = dict(df=df, dataset_name=dataset_name, project_id=project_id)
                save_active_dataset(candidate, current_account["id"])
                reset_derived_data()
                st.session_state.update(candidate)
                st.session_state['uploaded_fingerprint'] = fingerprint
            st.success(f"Loaded **{uploaded_file.name}** ({df.shape[0]:,} rows x {df.shape[1]} columns)")
        except Exception as e:
            st.error(f"Failed to read file: {e}")

with tab2:
    st.markdown("Choose a preloaded business benchmark:")
    c1, c2, c3 = st.columns(3)
    sample_to_load = None
    with c1:
        st.markdown("#### 🛍️ E-Commerce Retail")
        st.caption("Sales, categories, discounts, profits across 4 global regions.")
        if st.button("Load E-Commerce Dataset", key="btn_ecom"):
            sample_to_load = "ecommerce_sales"
    with c2:
        st.markdown("#### 💳 SaaS Subscriptions")
        st.caption("MRR, tiers, tenure, support tickets, and customer churn.")
        if st.button("Load SaaS Churn Dataset", key="btn_saas"):
            sample_to_load = "saas_churn"
    with c3:
        st.markdown("#### 🚚 Supply Chain & Ops")
        st.caption("Warehouses, shipping modes, transit times, and SLA breaches.")
        if st.button("Load Supply Chain Dataset", key="btn_ops"):
            sample_to_load = "ops_fulfillment"

    if sample_to_load:
        with st.spinner(f"Loading {sample_to_load}..."):
            try:
                res = requests.post(f"{BACKEND_URL}/api/load-sample", data={"sample_id": sample_to_load}, headers={"Authorization": "Bearer " + st.session_state["auth_token"]}, timeout=15)
                if res.status_code == 200:
                    data = res.json()
                    sample_df = fetch_sample_dataframe(BACKEND_URL, st.session_state["auth_token"], data)
                    reset_derived_data()
                    st.session_state["project_id"] = data["project_id"]
                    st.session_state["dataset_name"] = data["dataset_name"]
                    st.session_state["df"] = sample_df
                    st.success(f"Loaded benchmark dataset: **{data['dataset_name']}**")
                else:
                    detail = res.json().get("detail", "Sample request failed.")
                    raise ValueError(detail)
            except Exception as e:
                st.error(f"Error loading benchmark: {e}")



# Data Preview
if st.session_state.get("df") is not None:
    df = active_dataframe(st.session_state)
    st.markdown("---")
    st.markdown("### 📋 Dataset Preview")
    st.dataframe(df.head(8), use_container_width=True)

    # Launch Analysis Button
    st.markdown("---")
    col_btn, col_q = st.columns([1, 2])
    with col_q:
        specific_q = st.text_input(
            "Specific analytical question for the Supervisor:",
            value=user_question_upload if 'user_question_upload' in locals() else "",
            placeholder="e.g. Why did revenue decline in Europe? Or leave blank for full audit.",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_audit = st.button("🚀 Run Autonomous Analysis", type="primary", use_container_width=True)

    if run_audit:
        with st.status("🤖 Autonomous Data Analyst team executing...", expanded=True) as status:
            st.write("1. 🎯 **Supervisor Agent:** Formulating dynamic analytical DAG...")
            initial_state: AgentState = {
                "project_id": st.session_state.get("project_id"),
                "owner_id": current_account["id"],
                "dataset_name": st.session_state.get("dataset_name", "Dataset"),
                "df_raw": df,
                "user_question": specific_q.strip() if specific_q else "",
                "execution_steps": [],
                "errors": [],
            }
            
            final_state = run_analyst_pipeline(initial_state)
            st.session_state["analysis"] = final_state
            save_active_dataset(st.session_state, current_account["id"])

            for step in final_state.get("execution_steps", []):
                st.write(f"• {step}")

            status.update(label="✅ Autonomous Analysis Completed!", state="complete", expanded=False)

        st.success("Analysis complete! Explore the findings across the pages in the sidebar.")
        c_nav1, c_nav2 = st.columns(2)
        with c_nav1:
            if st.button("🩺 View Health & Business KPIs", use_container_width=True):
                st.switch_page("pages/02_🩺_Health_&_KPIs.py")
        with c_nav2:
            if st.button("🔍 View Root-Cause Diagnostics", use_container_width=True):
                st.switch_page("pages/03_🔍_Root_Cause_&_Hypotheses.py")
