import json
import logging
from typing import Dict, Any, List
import pandas as pd

from backend.graph.state import AgentState
from backend.services.llm_service import invoke_llm
from backend.services.date_inference import infer_dates
from backend.services.profiler import _classify_column

logger = logging.getLogger(__name__)


def schema_agent_node(state: AgentState) -> AgentState:
    """
    Schema Agent:
    Builds a semantic data dictionary classifying columns into:
    Identifier, Measure (Metric), Dimension (Category), Temporal (Date), Geography, or Status.
    """
    logger.info("--> [Schema Agent] Building semantic data dictionary...")

    df = state.get("df_raw")
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    if df is None or df.empty:
        errors.append("Schema Agent: DataFrame is empty.")
        return {**state, "errors": errors}

    # Deterministic pre-classification
    column_profiles = {}
    converted_df = df.copy()

    for col in converted_df.columns:
        series = converted_df[col]
        dtype_str = str(series.dtype)
        nunique = int(series.nunique())
        sample_vals = [str(x) for x in series.dropna().unique()[:4]]

        # Detect temporal columns
        is_date = False
        if "datetime" in dtype_str:
            is_date = True
        elif dtype_str == "object" and any(k in col.lower() for k in ["date", "time", "day", "month", "year", "created", "updated"]):
            try:
                parsed = infer_dates(converted_df[col])
                if parsed is not None:
                    converted_df[col] = parsed
                    is_date = True
            except Exception:
                pass

        column_profiles[col] = {
            "dtype": str(converted_df[col].dtype),
            "nunique": nunique,
            "sample_values": sample_vals,
            "is_date": is_date,
        }

    # Prompt LLM (Fast tier) to semantically categorize each column
    prompt = f"""You are a Data Governance Specialist.
Given these column profiles from a dataset, assign a precise semantic role to each column.
Choose from: "Identifier", "Measure", "Dimension", "Temporal", "Geography", "Binary_Flag".

Column Profiles:
{json.dumps(column_profiles, indent=2)}

Respond ONLY with valid JSON in this structure:
{{
  "columns": {{
    "column_name": {{
      "semantic_type": "Measure",
      "business_description": "Total sales dollar amount",
      "is_key_metric": true
    }}
  }},
  "primary_date_column": "order_date_or_null",
  "primary_id_column": "id_or_null",
  "recommended_measures": ["sales", "profit"],
  "recommended_dimensions": ["region", "category"]
}}
"""

    try:
        raw_response = invoke_llm(
            prompt=prompt,
            system_prompt="You are an expert Data Architect. Return only valid JSON.",
            tier="fast",
            task="schema",
            temperature=0.1,
        )

        clean_text = raw_response.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0].strip()

        schema_meta = json.loads(clean_text)
    except Exception as e:
        logger.warning(f"Schema Agent LLM fallback: {e}")
        # Deterministic fallback
        cols_meta = {}
        for col, profile in column_profiles.items():
            if profile["is_date"]:
                sem = "Temporal"
            elif profile["nunique"] == len(converted_df) and "id" in col.lower():
                sem = "Identifier"
            elif "float" in profile["dtype"] or "int" in profile["dtype"]:
                sem = "Measure" if profile["nunique"] > 10 else "Dimension"
            else:
                sem = "Dimension"
            cols_meta[col] = {"semantic_type": sem, "business_description": col, "is_key_metric": sem == "Measure"}

        schema_meta = {
            "columns": cols_meta,
            "primary_date_column": next((c for c, p in column_profiles.items() if p["is_date"]), None),
            "primary_id_column": next((c for c in converted_df.columns if "id" in c.lower()), None),
            "recommended_measures": [c for c, m in cols_meta.items() if m["semantic_type"] == "Measure"],
            "recommended_dimensions": [c for c, m in cols_meta.items() if m["semantic_type"] == "Dimension"],
        }

    # Ensure recommended measures and dimensions strictly exist in dataframe
    rec_measures = [c for c in schema_meta.get("recommended_measures", []) if c in converted_df.columns]
    rec_dimensions = [c for c in schema_meta.get("recommended_dimensions", []) if c in converted_df.columns]
    if not rec_measures:
        rec_measures = [c for c, p in column_profiles.items() if ("float" in p["dtype"] or "int" in p["dtype"]) and p["nunique"] > 10]
    if not rec_dimensions:
        rec_dimensions = [c for c, p in column_profiles.items() if not p["is_date"] and p["nunique"] <= 50]
    identifiers = {c for c in converted_df if _classify_column(converted_df[c], str(c)) == 'id'}
    schema_meta["recommended_measures"] = [c for c in rec_measures if c not in identifiers]
    schema_meta["recommended_dimensions"] = [c for c in rec_dimensions if c not in identifiers]
    for column in identifiers:
        schema_meta.setdefault('columns', {}).setdefault(column, {}).update(semantic_type='Identifier', is_key_metric=False)
    if not column_profiles.get(schema_meta.get("primary_date_column"), {}).get("is_date"):
        schema_meta["primary_date_column"] = next((c for c, p in column_profiles.items() if p["is_date"]), None)
    if schema_meta.get("primary_id_column") not in converted_df.columns:
        schema_meta["primary_id_column"] = next((c for c in converted_df.columns if "id" in c.lower()), None)

    execution_steps.append(f"Schema Agent: Classified {len(df.columns)} columns into semantic roles.")

    return {
        **state,
        "df_clean": converted_df,
        "schema_metadata": schema_meta,
        "execution_steps": execution_steps,
        "errors": errors,
    }
