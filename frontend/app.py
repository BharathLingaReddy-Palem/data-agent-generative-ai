import streamlit as st
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

st.set_page_config(
    page_title="Autonomous AI Data Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from frontend.auth import require_login
current_account = require_login()

# Custom Theme Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .hero-title {
        font-size: 2.6rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8 0%, #818CF8 50%, #C084FC 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.25rem;
    }
    
    .hero-sub {
        font-size: 1.15rem;
        color: #94A3B8;
        line-height: 1.6;
        margin-bottom: 1.5rem;
    }
    
    .feature-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.4rem;
        margin-bottom: 1rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .feature-card:hover {
        border-color: #6366F1;
        transform: translateY(-2px);
    }
    
    .feature-card h3 {
        color: #F8FAFC;
        font-size: 1.15rem;
        margin-bottom: 0.4rem;
    }
    
    .feature-card p {
        color: #94A3B8;
        font-size: 0.9rem;
        line-height: 1.5;
        margin: 0;
    }

    .badge {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.4rem;
    }
    .badge-nvidia { background-color: #14532D; color: #4ADE80; border: 1px solid #15803D; }
    .badge-groq { background-color: #7C2D12; color: #FB923C; border: 1px solid #C2410C; }
    .badge-stat { background-color: #1E3A8A; color: #93C5FD; border: 1px solid #2563EB; }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "project_id" not in st.session_state:
    st.session_state["project_id"] = None
if "dataset_name" not in st.session_state:
    st.session_state["dataset_name"] = None
if "df" not in st.session_state:
    st.session_state["df"] = None
if "analysis" not in st.session_state:
    st.session_state["analysis"] = None
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Sidebar
with st.sidebar:
    st.markdown("### 📊 **AI Data Analyst**")
    st.markdown(
        """
        <div>
            <span class='badge badge-nvidia'>7 NVIDIA NIM Keys</span>
            <span class='badge badge-groq'>11 Groq Keys</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    if st.session_state.get("project_id"):
        st.success(f"📂 Active Dataset:\n**{st.session_state['dataset_name']}**")
        st.caption(f"Session ID: `{st.session_state['project_id'][:8]}`")
        if st.session_state.get("analysis"):
            score = st.session_state["analysis"].get("health_score", 100)
            st.metric("Data Health Score", f"{score}/100")
    else:
        st.info("ℹ️ No active dataset. Go to **Upload & Audit** to start.")

    st.markdown("---")
    st.markdown("### 🧠 Autonomous Team")
    st.markdown("""
    - 🎯 **Supervisor Agent** (Dynamic Planning)
    - 🗂️ **Schema Agent** (Semantic Dictionary)
    - 🩺 **Quality Agent** (Health 0-100 Score & Z-scores)
    - 💼 **KPI Agent** (Domain Business Metrics)
    - 📊 **EDA Agent** (Distributions & Correlations)
    - 🔍 **Diagnostic Agent** (Root-Cause & Pareto)
    - 📐 **Hypothesis Agent** (p-value tests)
    - 📈 **Trend Agent** (MoM/YoY & Seasonality)
    - 📊 **Visualization Agent** (Smart Plotly figures)
    - 🌐 **Benchmark Library** (McKinsey/Gartner comparisons)
    - ⚖️ **Dataset Comparator** (Welch's t-test variance)
    - 📄 **Report Agent** (Executive PDF & PowerPoint)
    """)

# Hero Section
st.markdown("<h1 class='hero-title'>Autonomous AI Data Analyst</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='hero-sub'>An enterprise-grade autonomous analytical agent system that ingests raw business data, diagnoses root causes (<b>WHY did metrics change?</b>), validates statistical significance, and generates executive briefings with zero mathematical hallucinations.</p>",
    unsafe_allow_html=True,
)

# API Engine Status Cards
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("""
    <div class='feature-card'>
        <h3>🥇 Deep Reasoning Engine</h3>
        <p>Powered by <b>NVIDIA Nemotron 3 Super 120B</b> with fallback to <b>Groq GPT-OSS 120B</b> for multi-dimensional root-cause deduction.</p>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("""
    <div class='feature-card'>
        <h3>⚡ 18-Key Resilient Pool</h3>
        <p>11 Groq accounts + 7 NVIDIA NIM accounts running round-robin with transparent HTTP 429 rate-limit failover.</p>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("""
    <div class='feature-card'>
        <h3>🧮 Zero Math Hallucinations</h3>
        <p>The LLM reasons and orchestrates while sandboxed <b>Python, Pandas, DuckDB, and SciPy</b> compute exact numbers.</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# Quick Action Banner
col_l, col_r1, col_r2 = st.columns([2, 1, 1])
with col_l:
    st.markdown("### 🚀 Ready to Analyze Your Business Data?")
    st.write("Upload your CSV/Excel transactions, compare two cohorts/periods, or view industry benchmark audits.")
with col_r1:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("👉 Upload & Audit", use_container_width=True, type="primary"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
with col_r2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚖️ Dataset Comparison", use_container_width=True):
        st.switch_page("pages/07_⚖️_Dataset_Comparison.py")
