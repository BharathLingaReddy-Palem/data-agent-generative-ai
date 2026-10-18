from typing import TypedDict, Optional, List, Dict, Any, Union
import pandas as pd


class AgentState(TypedDict, total=False):
    """
    Core state representation passed across all specialized data analyst agents.
    """
    # Project & Session Metadata
    project_id: str
    owner_id: str
    dataset_name: str
    file_path: Optional[str]
    csv_bytes: Optional[bytes]
    csv_url: Optional[str]

    # User Query & Planning
    user_question: Optional[str]
    analysis_plan: Dict[str, Any]
    active_agents: List[str]

    # Raw and Validated DataFrames
    df_raw: Optional[pd.DataFrame]
    df_clean: Optional[pd.DataFrame]
    cleaning_log: List[str]

    # Agent 1: Semantic Data Dictionary & Governance
    schema_metadata: Dict[str, Any]

    # Agent 2: Data Quality & Health Audit
    quality_audit: Dict[str, Any]
    health_score: float  # 0 to 100

    # Agent 3: Business KPIs & Domain Metrics
    kpi_results: Dict[str, Any]

    # Agent 4: Exploratory Distributions & Correlations
    eda_results: Dict[str, Any]
    eda_insights: str

    # Agent 5: Diagnostic & Root Cause Analysis
    diagnostic_results: Dict[str, Any]

    # Agent 6: Statistical Significance & Hypothesis Testing
    hypothesis_results: Dict[str, Any]

    # Agent 6b: Time-Series Intelligence (Phase 2)
    trend_results: Dict[str, Any]

    # Agent 7: Evidence-Driven Visualizations (Plotly)
    charts: List[Dict[str, Any]]

    # Agent 8: Report Generator — PDF + Markdown + PowerPoint
    executive_report: Dict[str, Any]
    report_summary: str
    report_markdown: str
    report_pdf_path: str
    report_pdf_url: str
    report_pptx_path: str       # Phase 3: PowerPoint path
    report_pptx_url: str
    benchmark_results: Dict[str, Any]  # Phase 3: Industry benchmarks

    # Conversational Memory & Q&A
    chat_history: List[Dict[str, str]]
    latest_answer: Optional[str]

    # Error handling & Execution traces
    execution_steps: List[str]
    errors: List[str]


# Alias for backward compatibility
AnalystState = AgentState
