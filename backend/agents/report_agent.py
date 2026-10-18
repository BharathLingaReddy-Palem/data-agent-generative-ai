import os
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from backend.graph.state import AgentState
from backend.config import REPORTS_DIR
from backend.services.report_artifacts import report_path
from backend.services.r2_service import r2_service
from backend.services.supabase_service import db_service
from backend.services.llm_service import invoke_llm
# Phase 3: Benchmarks + PPTX
from backend.tools.benchmarks import run_full_benchmark_audit
from backend.tools.pptx_exporter import generate_pptx_report

from backend.services.narrative_checks import unsupported_claims
from backend.services.evidence_briefing import build_evidence_briefing

logger = logging.getLogger(__name__)


import re
import html

def clean_reportlab_xml(text: str) -> str:
    """Safely sanitizes text for ReportLab Paragraph XML parsing."""
    if not text:
        return ""
    # Strip markdown headers like ### or ##
    text = re.sub(r'#+\s*', '', text)
    # Escape raw XML
    text = html.escape(text)
    # Convert markdown **bold** to <b>bold</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Convert newlines to breaks
    text = text.replace('\n\n', '<br/><br/>').replace('\n', ' ')
    # Strip stray unclosed <b> or </b>
    if text.count('<b>') != text.count('</b>'):
        text = text.replace('<b>', '').replace('</b>', '')
    return text.strip()


def generate_analyst_pdf_report(
    output_path: str,
    dataset_name: str,
    project_id: str,
    health_score: float,
    kpi_results: dict,
    diagnostic_results: dict,
    hypothesis_results: dict,
    executive_summary: str,
    action_plan: str,
) -> str:
    """Builds a formatted executive PDF report using ReportLab if installed, else fallback."""
    if not HAS_REPORTLAB:
        txt_path = output_path.replace(".pdf", ".txt")
        content = f"""
================================================================================
📊 AUTONOMOUS AI DATA ANALYST — EXECUTIVE INTELLIGENCE REPORT
================================================================================
Dataset: {dataset_name} | Project ID: {project_id[:8]} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Data Health Score: {health_score}/100

1. EXECUTIVE BRIEFING
--------------------------------------------------------------------------------
{executive_summary}

2. CORE BUSINESS KPIS
--------------------------------------------------------------------------------
Domain: {kpi_results.get('domain', 'General')}
{chr(10).join([f"• {m.get('metric_name')}: {m.get('formatted_total')} (Avg: {m.get('formatted_mean')})" for m in kpi_results.get('kpi_metrics', [])[:5]])}

3. ROOT CAUSE & DIAGNOSTIC FINDINGS
--------------------------------------------------------------------------------
{diagnostic_results.get('diagnostic_narrative', 'N/A')}

4. STATISTICAL HYPOTHESIS TESTING
--------------------------------------------------------------------------------
{hypothesis_results.get('executive_summary', 'N/A')}

5. RECOMMENDED STRATEGIC ACTIONS
--------------------------------------------------------------------------------
{action_plan}
================================================================================
"""
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(content)
        return txt_path

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    h2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("📊 Autonomous AI Data Analyst", title_style))
    story.append(Paragraph(f"Executive Intelligence & Diagnostic Briefing (Health Score: <b>{health_score}/100</b>)", h2_style))
    story.append(Paragraph(
        f"<b>Dataset:</b> {dataset_name} | <b>Domain:</b> {kpi_results.get('domain', 'Business')} | <b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        body_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceBefore=4, spaceAfter=8))

    # Executive Briefing
    story.append(Paragraph("1. Executive Briefing", h2_style))
    cleaned_exec = clean_reportlab_xml(executive_summary)
    story.append(Paragraph(cleaned_exec, body_style))
    story.append(Spacer(1, 6))

    # KPI Table
    story.append(Paragraph("2. Core Performance Metrics", h2_style))
    metrics = kpi_results.get("kpi_metrics", [])
    if metrics:
        table_data = [["Metric", "Aggregation / Value", "Mean / Average", "Growth / Change"]]
        for m in metrics[:6]:
            table_data.append([
                m.get("metric_name", ""),
                f"{m.get('aggregation', 'value')}: {m.get('formatted_value', m.get('formatted_total', ''))}",
                m.get("formatted_mean", ""),
                f"{m.get('growth_pct', 'N/A')}%" if m.get("growth_pct") is not None else "—",
            ])
        t = Table(table_data, colWidths=[160, 120, 120, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.HexColor("#FFFFFF")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
    story.append(Spacer(1, 8))

    # Diagnostic & Root Cause
    story.append(Paragraph("3. Root Cause & Pareto Diagnostics", h2_style))
    diag_narrative = diagnostic_results.get("diagnostic_narrative", "")
    cleaned_diag = clean_reportlab_xml(diag_narrative[:1400])
    story.append(Paragraph(cleaned_diag, body_style))
    story.append(Spacer(1, 6))

    # Statistical Tests
    story.append(Paragraph("4. Statistical Significance Validation", h2_style))
    hypo_summary = hypothesis_results.get("executive_summary", "")
    cleaned_hypo = clean_reportlab_xml(hypo_summary)
    story.append(Paragraph(cleaned_hypo, body_style))
    story.append(Spacer(1, 6))

    # Action Plan
    story.append(Paragraph("5. Prioritized Strategic Next Steps", h2_style))
    cleaned_actions = clean_reportlab_xml(action_plan)
    story.append(Paragraph(cleaned_actions, body_style))

    doc.build(story)
    return output_path


def report_agent_node(state: AgentState) -> AgentState:
    """
    Report Agent (Phase 3 Upgrade):
    1. Runs Industry Benchmark Audit against detected domain
    2. Synthesizes all agent findings into Executive Briefing
    3. Generates PDF report (ReportLab)
    4. Generates PowerPoint presentation (python-pptx)
    5. Generates Markdown report
    6. Uploads to cloud storage in background (non-blocking)
    """
    logger.info("--> [Report Agent] Generating Executive Briefing, PDF & PowerPoint...")

    dataset_name = state.get("dataset_name", "Dataset")
    project_id = state.get("project_id", "default")
    health_score = state.get("health_score", 100.0)
    quality_audit = state.get("quality_audit", {})
    kpi_results = state.get("kpi_results", {})
    diagnostic_results = state.get("diagnostic_results", {})
    hypothesis_results = state.get("hypothesis_results", {})
    trend_results = state.get("trend_results", {})
    user_question = state.get("user_question") or ""
    execution_steps = state.get("execution_steps", []).copy()
    errors = state.get("errors", []).copy()

    # ── Phase 3: Industry Benchmark Audit ────────────────────────────────────
    domain = kpi_results.get("domain", "General Business Analytics")
    benchmark_results = {}
    try:
        benchmark_results = run_full_benchmark_audit(
            kpi_metrics=kpi_results.get("kpi_metrics", []) + kpi_results.get("domain_specific_kpis", []),
            domain=domain,
        )
        logger.info(f"Benchmark audit: {benchmark_results.get('metrics_benchmarked', 0)} metrics evaluated")
    except Exception as bm_err:
        logger.warning(f"Benchmark audit skipped: {bm_err}")
        errors.append(f'Report Agent Benchmark Error: {bm_err}')

    pdf_destination = report_path(project_id, 'pdf', REPORTS_DIR)
    pptx_destination = report_path(project_id, 'pptx', REPORTS_DIR)
    pdf_destination.parent.mkdir(parents=True, exist_ok=True)
    filename = pdf_destination.name
    local_path = ""
    pptx_path = ""
    report_url = ""
    pptx_url = ""

    try:
        # Headlines are reproducible facts; detailed agents supply exploratory interpretation.
        executive_summary, action_plan = build_evidence_briefing(state)

        # Generate Complete Markdown Report
        markdown_report = f"""# 📊 Executive Intelligence Report: {dataset_name}
**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} | **Data Health Score:** {health_score}/100 ({quality_audit.get('health_status', 'Good')})

---

## 1. Executive Briefing
{executive_summary}

---

## 2. Core Business Metrics ({kpi_results.get('domain', 'Business')})
| Metric | Aggregation / Value | Average | Growth |
| :--- | :--- | :--- | :--- |
"""
        for m in kpi_results.get("kpi_metrics", [])[:6]:
            growth_str = f"{m.get('growth_pct')}%" if m.get('growth_pct') is not None else "—"
            markdown_report += f"| {m.get('metric_name')} | {m.get('aggregation', 'value')}: {m.get('formatted_value', m.get('formatted_total'))} | {m.get('formatted_mean')} | {growth_str} |\n"

        markdown_report += f"""
Units and periods are unspecified unless explicitly stated in the dataset metadata. Values summarize this dataset snapshot.

---

## 3. Root Cause & Diagnostic Breakdown
{diagnostic_results.get('diagnostic_narrative', 'N/A')}

---

## 4. Statistical Validation & Hypothesis Testing
{hypothesis_results.get('executive_summary', 'N/A')}

---

## 5. Strategic Recommendations & Action Plan
{action_plan}
"""

        # ── Generate PDF (ReportLab) ──────────────────────────────────────
        try:
            with tempfile.TemporaryDirectory(prefix='.pdf-', dir=pdf_destination.parent) as staging:
                actual_path = generate_analyst_pdf_report(
                    output_path=str(Path(staging) / filename),
                    dataset_name=dataset_name,
                    project_id=project_id,
                    health_score=health_score,
                    kpi_results=kpi_results,
                    diagnostic_results=diagnostic_results,
                    hypothesis_results=hypothesis_results,
                    executive_summary=executive_summary,
                    action_plan=action_plan,
                )
                if Path(actual_path).suffix == '.pdf' and Path(actual_path).is_file():
                    os.replace(actual_path, pdf_destination)
                    local_path = str(pdf_destination)
                    report_url = f'/api/reports/{project_id}/pdf/download'
                else:
                    errors.append('Report Agent: PDF generation returned a fallback instead of a PDF.')
        except Exception as pdf_err:
            errors.append(f'Report Agent PDF Error: {pdf_err}')

        # ── Generate PowerPoint (python-pptx) — Phase 3 ──────────────────────
        try:
            with tempfile.TemporaryDirectory(prefix='.pptx-', dir=pptx_destination.parent) as staging:
                pptx_actual_path = generate_pptx_report(
                    output_path=str(Path(staging) / pptx_destination.name),
                    dataset_name=dataset_name,
                    health_score=health_score,
                    kpi_results=kpi_results,
                    quality_audit=quality_audit,
                    diagnostic_results=diagnostic_results,
                    hypothesis_results=hypothesis_results,
                    trend_results=trend_results,
                    benchmark_results=benchmark_results,
                    executive_summary=executive_summary,
                    action_plan=action_plan,
                )
                if Path(pptx_actual_path).suffix == '.pptx' and Path(pptx_actual_path).is_file():
                    os.replace(pptx_actual_path, pptx_destination)
                    pptx_path = str(pptx_destination)
                    pptx_url = f'/api/reports/{project_id}/pptx/download'
                else:
                    errors.append('Report Agent: PowerPoint generation returned a fallback instead of a presentation.')
        except Exception as pptx_err:
            logger.warning(f"PPTX generation warning: {pptx_err}")
            errors.append(f'Report Agent PowerPoint Error: {pptx_err}')

        # ── Background Cloud Storage (R2 & Supabase) — Non-blocking ──────────
        import threading
        def _bg_report_sync(pid, fpath, fname, summ):
            try:
                r2_key = f"reports/{pid}/{fname}"
                url = r2_service.upload_file(
                    fpath, r2_key, content_type="application/pdf" if HAS_REPORTLAB else "text/plain"
                )
                db_service.save_report(pid, url, summary=summ[:500])
            except Exception as bg_err:
                logger.debug(f"Background report cloud sync notice: {bg_err}")

        if local_path:
            threading.Thread(
                target=_bg_report_sync,
                args=(project_id, local_path, filename, executive_summary),
                daemon=True
            ).start()

        execution_steps.append(
            f"Report Agent: Executive Briefing compiled. PDF={'ready' if local_path else 'unavailable'}, "
            f"PowerPoint={'ready' if pptx_path else 'unavailable'}. "
            f"Benchmarks: {benchmark_results.get('overall_competitive_position', 'N/A')}."
        )

    except Exception as e:
        logger.error(f"Report Agent failed: {e}")
        errors.append(f"Report Agent Error: {str(e)}")
        markdown_report = f"# Executive Report for {dataset_name}\nAnalysis completed."
        executive_summary = f"Analysis completed for {dataset_name}."
        pptx_path = ""
        local_path = ""
        report_url = ""
        pptx_url = ""

    return {
        **state,
        "executive_report": {
            "summary": executive_summary,
            "markdown": markdown_report,
            "local_pdf_path": local_path,
            "pdf_url": report_url,
            "pptx_url": pptx_url,
        },
        "report_summary": executive_summary,
        "report_markdown": markdown_report,
        "report_pdf_path": local_path,
        "report_pdf_url": report_url,
        "report_pptx_path": pptx_path,         # Phase 3
        "report_pptx_url": pptx_url,
        "benchmark_results": benchmark_results, # Phase 3
        "execution_steps": execution_steps,
        "errors": errors,
    }
