"""
Specialized Data Analyst Agent Nodes.
"""
from backend.agents.csv_loader import csv_loader_node
from backend.agents.supervisor import supervisor_node
from backend.agents.schema_agent import schema_agent_node
from backend.agents.quality_agent import quality_agent_node
from backend.agents.kpi_agent import kpi_agent_node
from backend.agents.eda_agent import eda_agent_node
from backend.agents.diagnostic_agent import diagnostic_agent_node
from backend.agents.hypothesis_agent import hypothesis_agent_node
from backend.agents.visualization_agent import visualization_agent_node
from backend.agents.report_agent import report_agent_node

__all__ = [
    "csv_loader_node",
    "supervisor_node",
    "schema_agent_node",
    "quality_agent_node",
    "kpi_agent_node",
    "eda_agent_node",
    "diagnostic_agent_node",
    "hypothesis_agent_node",
    "visualization_agent_node",
    "report_agent_node",
]
