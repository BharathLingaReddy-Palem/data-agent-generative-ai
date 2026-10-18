import json
import logging
from typing import Dict, Any, List
import pandas as pd

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm

logger = logging.getLogger(__name__)


def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor Agent:
    Acts as the Lead Data Analyst. Interprets the dataset structure and user query,
    then formulates an intelligent, dynamic analysis DAG instead of blindly running everything.
    """
    logger.info("--> [Supervisor Agent] Formulating analytical plan...")

    df = state.get("df_raw")
    user_question = (state.get("user_question") or "").strip()
    dataset_name = state.get("dataset_name", "Dataset")
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Supervisor: No dataset available to analyze.")
        return {**state, "errors": errors}

    columns_info = [f"{col} ({df[col].dtype})" for col in df.columns[:30]]
    sample_preview = df.head(3).to_dict(orient="records")

    prompt = f"""You are the Lead Data Analyst formulating an analysis plan.
Dataset: {dataset_name}
Rows: {len(df)}, Columns ({len(df.columns)}): {', '.join(columns_info)}
Sample Data: {json.dumps(sample_preview, default=str)}

User Request: {user_question if user_question else "Perform a comprehensive autonomous business and data health audit."}

Your Task:
1. Determine the user's core analytical intent.
2. Identify target metrics (e.g. revenue, sales, churn, profit) and categorical dimensions (e.g. region, product, customer_tier).
3. Select which specialized agents are REQUIRED for this task from:
   - "schema": Semantic data dictionary (always required)
   - "quality": Data health audit & anomaly check (always recommended)
   - "kpi": Business KPI modeling (if numeric measures exist)
   - "eda": Distribution & correlation profiling
   - "diagnostic": Root cause, Pareto 80/20, segment drill-downs (critical if investigating drops/drivers/why)
   - "hypothesis": Statistical significance tests (if comparing groups/segments)
   - "visualization": Plotly charts
   - "report": Executive briefing & strategic actions

Respond ONLY with valid JSON in this exact structure:
{{
  "intent": "Brief description of analytical goal",
  "target_metric": "Primary numeric column to focus on (or null)",
  "dimensions": ["list", "of", "relevant", "dimension", "columns"],
  "agents_to_run": ["schema", "quality", "kpi", "eda", "diagnostic", "hypothesis", "visualization", "report"],
  "reasoning": "1-2 sentences explaining why this plan was chosen"
}}
"""

    system_prompt = (
        "You are an expert Chief Analytics Officer who plans rigorous, evidence-driven data analysis."
    )

    try:
        response_text = invoke_llm(
            prompt=prompt,
            system_prompt=system_prompt,
            tier="reasoning",
            task="supervisor",
            temperature=0.1,
        )

        # Parse JSON
        clean_text = response_text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        plan = json.loads(clean_text)
        agents_to_run = plan.get("agents_to_run", [
            "schema", "quality", "kpi", "eda", "diagnostic", "hypothesis", "visualization", "report"
        ])

    except Exception as e:
        logger.warning(f"Supervisor LLM planning fallback triggered: {e}")
        plan = {
            "intent": "Autonomous Comprehensive Business & Data Health Audit",
            "target_metric": None,
            "dimensions": [c for c in df.columns if df[c].dtype == "object"][:5],
            "agents_to_run": [
                "schema", "quality", "kpi", "eda", "diagnostic", "hypothesis", "visualization", "report"
            ],
            "reasoning": "Standard full-spectrum analytical audit initialized.",
        }
        agents_to_run = plan["agents_to_run"]

    execution_steps.append(f"Supervisor: Formulated plan -> {plan.get('intent', 'General Audit')}")

    return {
        **state,
        "analysis_plan": plan,
        "active_agents": agents_to_run,
        "execution_steps": execution_steps,
        "errors": errors,
    }
