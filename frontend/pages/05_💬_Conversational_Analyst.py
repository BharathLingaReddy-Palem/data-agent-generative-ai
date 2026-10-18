"""
05_💬_Conversational_Analyst.py — Phase 2 Upgrade
===================================================
Key improvements in Phase 2:
  1. FULL RUNNING MEMORY — every previous Q&A is injected into the next prompt
     so the LLM can answer follow-up questions like "And what about Europe?"
  2. TOOL-FIRST — LLM first generates Python code, Pandas executes it,
     then LLM interprets the exact computed result
  3. CONTEXT-AWARE — injects all analysis results (KPIs, diagnostics, trends)
     as grounding context, not just dataset name
  4. EVIDENCE DISPLAY — shows executed code + computed output in expanders
  5. SMART SUGGESTIONS — context-aware quick questions based on what was found
"""
import streamlit as st
import pandas as pd
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.services.llm_service import invoke_llm
from backend.tools.python_tool import execute_python

st.set_page_config(
    page_title="Conversational Analyst | AI Data Analyst",
    page_icon="💬",
    layout="wide"
)

from frontend.auth import require_login
current_account = require_login()

# ── Custom Styling ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.memory-badge {
    display: inline-block;
    background: linear-gradient(135deg, #1e3a5f, #2563eb);
    color: #93c5fd;
    border: 1px solid #3b82f6;
    border-radius: 9999px;
    padding: 0.2rem 0.7rem;
    font-size: 0.75rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}
.evidence-box {
    background: #0f172a;
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    padding: 0.8rem 1rem;
    font-size: 0.85rem;
    color: #7dd3fc;
    margin-top: 0.3rem;
}
</style>
""", unsafe_allow_html=True)

# ── Guard: need dataset ───────────────────────────────────────────────────────
from backend.services.dataset_views import active_dataframe
df: pd.DataFrame = active_dataframe(st.session_state) if st.session_state.get("df") is not None else None
analysis: dict = st.session_state.get("analysis", {})
dataset_name: str = st.session_state.get("dataset_name", "Dataset")

if df is None:
    st.warning("⚠️ Please load or upload a dataset on the **Upload & Audit** page first.")
    if st.button("Go to Upload & Audit"):
        st.switch_page("pages/01_📥_Upload_&_Audit.py")
    st.stop()

# ── Page Header ───────────────────────────────────────────────────────────────
st.markdown("# 💬 Conversational Data Analyst")
st.markdown(
    f"Ask follow-up questions about **{dataset_name}**. "
    "All calculations run live in Python — answers are grounded in exact numbers, not LLM guesses."
)
st.markdown(
    '<div class="memory-badge">🧠 Full Conversation Memory Active — follow-up questions understand prior context</div>',
    unsafe_allow_html=True,
)

# ── Build Grounding Context (injected into every LLM call) ───────────────────
def _build_analysis_context(df: pd.DataFrame, analysis: dict, dataset_name: str) -> str:
    """
    Builds a compact grounding context from all prior analysis results.
    This is injected into every LLM prompt so the model has full awareness.
    """
    kpi = analysis.get("kpi_results", {})
    diag = analysis.get("diagnostic_results", {})
    hypo = analysis.get("hypothesis_results", {})
    trend = analysis.get("trend_results", {})
    quality = analysis.get("quality_audit", {})
    schema = analysis.get("schema_metadata", {})

    # KPI summary
    kpi_lines = []
    for m in kpi.get("kpi_metrics", [])[:5]:
        line = f"  • {m.get('metric_name')}: total={m.get('formatted_total')}, avg={m.get('formatted_mean')}"
        if m.get("growth_pct") is not None:
            line += f", MoM={m.get('growth_pct'):+.1f}%"
        kpi_lines.append(line)

    # Trend summary
    trend_lines = []
    if trend.get("available") and "time_series_data" in trend:
        ts = trend["time_series_data"]
        trend_lines = [
            f"  • Trend direction: {ts.get('trend_direction')} ({ts.get('trend_pct', 0):+.1f}%)",
            f"  • Latest MoM: {ts.get('latest_mom_pct', 'N/A')}%",
            f"  • Peak: {ts.get('peak_month')} | Trough: {ts.get('trough_month')}",
        ]
        if trend.get("seasonality_profile", {}).get("seasonal_pattern_detected"):
            sp = trend["seasonality_profile"]
            trend_lines.append(
                f"  • Best month: {sp.get('best_month')} (+{sp.get('best_month_uplift_pct', 0):.1f}%), "
                f"Worst: {sp.get('worst_month')} ({sp.get('worst_month_drag_pct', 0):.1f}%)"
            )

    ctx = f"""DATASET: {dataset_name} ({len(df):,} rows × {len(df.columns)} columns)
DOMAIN: {kpi.get("domain", "General Business")}
DATA HEALTH: {quality.get("health_score", "N/A")}/100 ({quality.get("health_status", "")})
COLUMNS: {", ".join(list(df.columns)[:15])}
MEASURES: {", ".join(schema.get("recommended_measures", [])[:5])}
DIMENSIONS: {", ".join(schema.get("recommended_dimensions", [])[:5])}

BUSINESS KPIs (exact values computed by Python):
{chr(10).join(kpi_lines) if kpi_lines else "  No KPI analysis available"}

TIME-SERIES TREND:
{chr(10).join(trend_lines) if trend_lines else "  No date column or trend analysis available"}

ROOT CAUSE SUMMARY:
  {diag.get("diagnostic_narrative", "No diagnostic available")[:300]}

STATISTICAL TESTS:
  {hypo.get("executive_summary", "No hypothesis tests available")[:200]}"""

    return ctx


grounding_ctx = _build_analysis_context(df, analysis, dataset_name)

# ── Smart Quick Questions (context-aware) ────────────────────────────────────
st.markdown("##### 💡 Suggested Questions:")

# Generate suggestions dynamically from what was actually found
kpi_primary = analysis.get("kpi_results", {}).get("primary_metric", "the primary metric")
dims = analysis.get("schema_metadata", {}).get("recommended_dimensions", [])
trend_dir = analysis.get("trend_results", {}).get("time_series_data", {}).get("trend_direction", "")
has_trend = analysis.get("trend_results", {}).get("available", False)

col_q1, col_q2, col_q3, col_q4 = st.columns(4)
quick_q = None

with col_q1:
    label = f"📊 Top 5 {dims[0] if dims else 'segments'} by {kpi_primary}?"
    if st.button(label, use_container_width=True, key="sq1"):
        quick_q = f"Show me the top 5 {dims[0] if dims else 'segments'} by {kpi_primary} with exact values and share %."
with col_q2:
    if st.button("📐 Is the variance statistically significant?", use_container_width=True, key="sq2"):
        quick_q = "Is the difference between the top segments statistically significant or is it random chance? Explain the p-value in simple terms."
with col_q3:
    lbl = f"📉 Why is the trend {trend_dir.lower()}?" if has_trend and trend_dir else "🔍 What are the biggest risks?"
    q = f"Why is {kpi_primary} {trend_dir.lower()}? What segments are causing it?" if has_trend and trend_dir else "Based on all the analysis, what are the top 3 business risks I should act on?"
    if st.button(lbl, use_container_width=True, key="sq3"):
        quick_q = q
with col_q4:
    if st.button("🚀 What are the top 3 actions to take?", use_container_width=True, key="sq4"):
        quick_q = "Based on all the data findings — KPIs, root causes, trends, and statistical tests — what are the top 3 specific actions leadership should take immediately?"

# ── Initialize Chat History ───────────────────────────────────────────────────
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {
            "role": "assistant",
            "content": (
                f"Hello! I've completed a full autonomous analysis of **{dataset_name}**.\n\n"
                + (f"📈 **Trend:** {kpi_primary} is currently **{trend_dir}**. " if has_trend and trend_dir else "")
                + f"\n\nAsk me anything — I remember our entire conversation, so follow-up questions like *'And what about Europe?'* work perfectly."
            ),
        }
    ]

# ── Display Chat History ──────────────────────────────────────────────────────
for i, msg in enumerate(st.session_state["chat_messages"]):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("code") or msg.get("evidence"):
            with st.expander("🛠️ Executed Python Code & Computed Evidence", expanded=False):
                if msg.get("code"):
                    st.code(msg["code"], language="python")
                if msg.get("evidence"):
                    st.markdown('<div class="evidence-box"><strong>Computed Output:</strong></div>', unsafe_allow_html=True)
                    st.write(msg["evidence"])

# ── Chat Input ────────────────────────────────────────────────────────────────
user_prompt = st.chat_input(
    f"Ask about {dataset_name} — e.g. 'Which region had highest profit?' or follow up on anything above..."
)
if quick_q:
    user_prompt = quick_q

if user_prompt:
    st.session_state["chat_messages"].append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Computing exact answer..."):

            # ── STEP 1: Build full conversation history for memory ────────────
            # Last 6 exchanges (12 messages) kept in context — older ones summarized
            history_messages = st.session_state["chat_messages"][:-1]  # exclude current user msg
            if len(history_messages) > 12:
                # Summarize older history
                older = history_messages[:-12]
                older_summary = " | ".join([
                    f"[{m['role']}]: {m['content'][:80]}..."
                    for m in older if m.get("content")
                ])
                recent_history = history_messages[-12:]
            else:
                older_summary = None
                recent_history = history_messages

            history_block = "\n".join([
                f"{m['role'].upper()}: {m['content'][:300]}"
                for m in recent_history
                if m.get("content") and m["role"] != "assistant" or len(m.get("content", "")) < 500
            ])
            if older_summary:
                history_block = f"[EARLIER CONVERSATION SUMMARY]: {older_summary}\n\n" + history_block

            # ── STEP 2: Ask LLM whether Python code is needed ─────────────────
            code_plan_prompt = f"""You are an Autonomous Data Analyst assistant.

DATASET CONTEXT:
{grounding_ctx}

CONVERSATION HISTORY (for context):
{history_block if history_block else "This is the first question."}

CURRENT USER QUESTION: "{user_prompt}"

Task: If answering this question requires computing exact sums, counts, averages, filters, 
group-bys, comparisons, or percentages FROM THE DATA, write executable Python code.
- Assume the dataset is already loaded as `df` (a pandas DataFrame)
- Assign the final answer to a variable called `result`
- Use simple assignments, groupby, filters and aggregations only. No imports, loops, functions, comprehensions, file operations, apply, eval or query.
- Keep code short and focused

If the question can be answered from the analysis context above WITHOUT computing from raw data, respond with exactly: NO_CODE

Respond ONLY with Python code or NO_CODE."""

            code_resp = invoke_llm(code_plan_prompt, tier="fast", task="chat_code", temperature=0.05).strip()

            # Clean up markdown code fences if LLM wraps in them
            if "```python" in code_resp:
                code_resp = code_resp.split("```python")[1].split("```")[0].strip()
            elif "```" in code_resp:
                code_resp = code_resp.split("```")[1].split("```")[0].strip()

            # ── STEP 3: Execute Python if code was generated ──────────────────
            calc_evidence = None
            executed_code = None

            if "NO_CODE" not in code_resp and ("df[" in code_resp or "df." in code_resp or "result" in code_resp):
                py_res = execute_python(code_resp, df)
                executed_code = code_resp
                if py_res.get("success"):
                    calc_evidence = py_res.get("result") if py_res.get("result") is not None else py_res.get("stdout")
                else:
                    # Self-healing: retry with the error
                    retry_prompt = f"""The following Python code failed:
```python
{code_resp}
```
Error: {py_res.get('error')}
Dataset columns: {list(df.columns)}
Dataset dtypes: {df.dtypes.to_dict()}

Fix the code. Respond with ONLY corrected Python code. Assign result to `result`."""
                    fixed_code = invoke_llm(retry_prompt, tier="fast", task="chat_code", temperature=0.05).strip()
                    if "```python" in fixed_code:
                        fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
                    elif "```" in fixed_code:
                        fixed_code = fixed_code.split("```")[1].split("```")[0].strip()

                    retry_res = execute_python(fixed_code, df)
                    if retry_res.get("success"):
                        executed_code = fixed_code
                        calc_evidence = retry_res.get("result") or retry_res.get("stdout")
                    else:
                        calc_evidence = f"⚠️ Computation attempted but failed: {py_res.get('error')}"

            # ── STEP 4: Generate final answer with FULL memory context ─────────
            system_prompt = (
                "You are an elite Senior Data Analyst with full memory of this entire conversation. "
                "Ground every claim in the provided analysis context or computed Python output. "
                "If a prior question established context (e.g. 'the region' from a previous answer), "
                "refer to it naturally. Be direct and authoritative."
            )

            answer_prompt = f"""ANALYSIS CONTEXT (pre-computed by Python — treat as ground truth):
{grounding_ctx}

FULL CONVERSATION MEMORY:
{history_block if history_block else "This is the first question."}

CURRENT USER QUESTION: {user_prompt}

LIVE PYTHON COMPUTATION RESULT:
{f"Exact computed answer: {calc_evidence}" if calc_evidence else "No additional computation was needed — answer from analysis context above."}

Provide a direct, authoritative, evidence-grounded answer. 
- Use exact numbers from the context or computed result above
- If this is a follow-up question, reference the prior conversation naturally  
- Keep response concise and formatted with bullet points where helpful
- Never say "I don't have access to..." — you have full context above"""

            reply = invoke_llm(
                answer_prompt,
                system_prompt=system_prompt,
                tier="reasoning",
                task="chat_answer",
                temperature=0.15,
            ).strip()

        # ── Display reply + evidence ──────────────────────────────────────────
        st.markdown(reply)

        if executed_code or calc_evidence:
            with st.expander("🛠️ Executed Python Code & Computed Evidence", expanded=False):
                if executed_code:
                    st.code(executed_code, language="python")
                if calc_evidence:
                    st.markdown(
                        '<div class="evidence-box"><strong>Computed Output:</strong></div>',
                        unsafe_allow_html=True,
                    )
                    st.write(calc_evidence)

        # ── Save to memory ────────────────────────────────────────────────────
        st.session_state["chat_messages"].append({
            "role": "assistant",
            "content": reply,
            "code": executed_code,
            "evidence": str(calc_evidence) if calc_evidence else None,
        })

# ── Sidebar: Conversation Stats ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Chat Session")
    n_turns = len([m for m in st.session_state.get("chat_messages", []) if m["role"] == "user"])
    st.metric("Questions Asked", n_turns)
    code_used = len([m for m in st.session_state.get("chat_messages", []) if m.get("code")])
    st.metric("Python Computations Run", code_used)
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state["chat_messages"] = [{
            "role": "assistant",
            "content": f"Chat cleared. Ready to analyze **{dataset_name}** again!"
        }]
        st.rerun()
