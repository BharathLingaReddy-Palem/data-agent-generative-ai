import logging
import concurrent.futures
from collections import Counter
from typing import Dict, Any, List

try:
    from langgraph.graph import StateGraph, END
except ImportError:
    StateGraph, END = None, None

from backend.graph.state import AgentState
from backend.agents.csv_loader import csv_loader_node
from backend.agents.supervisor import supervisor_node
from backend.agents.schema_agent import schema_agent_node
from backend.agents.quality_agent import quality_agent_node
from backend.agents.kpi_agent import kpi_agent_node
from backend.agents.eda_agent import eda_agent_node
from backend.agents.diagnostic_agent import diagnostic_agent_node
from backend.agents.hypothesis_agent import hypothesis_agent_node
from backend.agents.trend_agent import trend_agent_node          # Phase 2
from backend.agents.visualization_agent import visualization_agent_node
from backend.agents.report_agent import report_agent_node

logger = logging.getLogger(__name__)


def create_analyst_graph():
    """Builds and compiles the Autonomous AI Data Analyst LangGraph workflow."""
    if StateGraph is None:
        logger.info("LangGraph not installed. Using concurrent agent pipeline executor.")
        return None

    workflow = StateGraph(AgentState)

    # Register all 11 specialized agent nodes
    workflow.add_node("load_dataset", csv_loader_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("schema", schema_agent_node)
    workflow.add_node("quality", quality_agent_node)
    workflow.add_node("kpi", kpi_agent_node)
    workflow.add_node("eda", eda_agent_node)
    workflow.add_node("diagnostic", diagnostic_agent_node)
    workflow.add_node("hypothesis", hypothesis_agent_node)
    workflow.add_node("trend", trend_agent_node)                 # Phase 2
    workflow.add_node("visualization", visualization_agent_node)
    workflow.add_node("report", report_agent_node)

    # Wire Edges
    workflow.set_entry_point("load_dataset")
    workflow.add_edge("load_dataset", "supervisor")
    workflow.add_edge("supervisor", "schema")
    workflow.add_edge("schema", "quality")
    workflow.add_edge("quality", "kpi")
    workflow.add_edge("kpi", "eda")
    workflow.add_edge("eda", "diagnostic")
    workflow.add_edge("diagnostic", "hypothesis")
    workflow.add_edge("hypothesis", "trend")
    workflow.add_edge("trend", "visualization")
    workflow.add_edge("visualization", "report")
    workflow.add_edge("report", END)

    return workflow.compile()


analyst_graph_app = create_analyst_graph()


def run_analyst_pipeline(initial_state: AgentState) -> AgentState:
    """Respect dependencies; merge only outputs owned by independent branches."""
    initial_state = dict(initial_state)
    progress = initial_state.pop('_progress_callback', None)
    def report(pct, step):
        if progress:
            progress(pct, step)
    report(2, 'Loading dataset')
    loaded = csv_loader_node(initial_state)
    report(5, 'Planning analysis')
    state = supervisor_node(loaded)
    state.setdefault("execution_steps", [])
    state.setdefault("errors", [])
    active = set(state.get("active_agents", ["schema", "quality", "kpi", "eda",
        "diagnostic", "hypothesis", "trend", "visualization", "report"]))
    active.add("trend")
    if active & {"quality", "kpi", "eda", "diagnostic", "hypothesis", "trend", "visualization"}:
        active.add("schema")
    planned = active & {'schema', 'quality', 'kpi', 'eda', 'diagnostic', 'hypothesis', 'trend', 'visualization', 'report'}
    completed = 0

    def call(fn):
        branch = dict(state, execution_steps=list(state["execution_steps"]), errors=list(state["errors"]))
        try:
            result = fn(branch)
            if not isinstance(result, dict):
                raise TypeError('Agent must return a state dictionary.')
            return result
        except Exception as exc:
            return {"errors": branch['errors'] + [f"{fn.__name__}: {exc}"],
                    "execution_steps": branch['execution_steps']}

    def merge(result, keys, inherited):
        for key in keys:
            if key in result:
                state[key] = result[key]
        for key in ("execution_steps", "errors"):
            remaining = Counter(inherited[key])
            for item in result.get(key, []):
                if remaining[item]:
                    remaining[item] -= 1
                else:
                    state[key].append(item)

    def stage(nodes):
        nonlocal completed
        names = [name for name, _, _ in nodes if name in active]
        nodes = [(fn, keys) for name, fn, keys in nodes if name in active]
        if not nodes:
            return
        report(8 + int(88 * completed / max(len(planned), 1)), 'Running ' + ' + '.join(names))
        inherited = {key: list(state[key]) for key in ('errors', 'execution_steps')}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(nodes)) as pool:
            futures = [(pool.submit(call, fn), keys) for fn, keys in nodes]
            results = [(future.result(), keys) for future, keys in futures]
        for result, keys in results:
            merge(result, keys, inherited)
        completed += len(nodes)
        report(8 + int(88 * completed / max(len(planned), 1)), 'Finished ' + ' + '.join(names))

    stage([("schema", schema_agent_node, ["schema_metadata", "df_clean"])])
    stage([("quality", quality_agent_node, ["quality_audit", "health_score", "df_clean", "cleaning_log"])])
    stage([("kpi", kpi_agent_node, ["kpi_results"]),
           ("eda", eda_agent_node, ["eda_results", "eda_insights"])])
    stage([("diagnostic", diagnostic_agent_node, ["diagnostic_results"])])
    stage([("hypothesis", hypothesis_agent_node, ["hypothesis_results"]),
           ("trend", trend_agent_node, ["trend_results"])])
    stage([("visualization", visualization_agent_node, ["charts"])])
    stage([("report", report_agent_node, ["executive_report", "report_summary", "report_markdown",
        "report_pdf_path", "report_pdf_url", "report_pptx_path", "report_pptx_url", "benchmark_results"])])
    return state


run_full_pipeline = run_analyst_pipeline


