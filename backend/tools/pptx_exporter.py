"""
pptx_exporter.py — Executive PowerPoint Report Generator (Phase 3)
====================================================================
Generates a polished, branded PowerPoint presentation from analysis results.
Uses python-pptx (already installed: v1.0.2).

Slide structure:
  Slide 1: Title slide (dataset name, date, health score)
  Slide 2: Data Health Dashboard (quality metrics)
  Slide 3: Core Business KPIs table
  Slide 4: Industry Benchmarks comparison
  Slide 5: Time-Series Trend Summary (if available)
  Slide 6: Root Cause & Pareto Findings
  Slide 7: Statistical Significance Tests
  Slide 8: Top 3 Strategic Actions
  Slide 9: Appendix (Execution Steps)

Design: Dark navy + blue accent professional theme.
"""
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

# ── Color palette ─────────────────────────────────────────────────────────────
_NAVY    = RGBColor(0x0F, 0x17, 0x2A) if HAS_PPTX else None
_BLUE    = RGBColor(0x37, 0x6B, 0xF7) if HAS_PPTX else None
_ACCENT  = RGBColor(0x06, 0xB6, 0xD4) if HAS_PPTX else None
_WHITE   = RGBColor(0xFF, 0xFF, 0xFF) if HAS_PPTX else None
_SILVER  = RGBColor(0xCB, 0xD5, 0xE1) if HAS_PPTX else None
_GREEN   = RGBColor(0x10, 0xB9, 0x81) if HAS_PPTX else None
_RED     = RGBColor(0xEF, 0x44, 0x44) if HAS_PPTX else None
_YELLOW  = RGBColor(0xF5, 0x9E, 0x0B) if HAS_PPTX else None


def _add_slide(prs: "Presentation", layout_index: int = 6) -> Any:
    """Adds a blank slide and returns it."""
    layout = prs.slide_layouts[layout_index]  # 6 = blank
    return prs.slides.add_slide(layout)


def _set_bg(slide: Any, color: "RGBColor") -> None:
    """Sets the slide background to a solid fill color."""
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(
    slide: Any,
    text: str,
    left: float, top: float, width: float, height: float,
    font_size: int = 14,
    bold: bool = False,
    color: "RGBColor" = None,
    align: str = "left",
    wrap: bool = True,
) -> Any:
    """Adds a styled textbox to a slide. All dimensions in inches."""
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN

    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = PP_ALIGN.LEFT if align == "left" else \
                  PP_ALIGN.CENTER if align == "center" else PP_ALIGN.RIGHT

    run = p.runs[0] if p.runs else p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color or _WHITE
    return txBox


def _add_divider(slide: Any, top: float, color: "RGBColor" = None) -> None:
    """Adds a thin horizontal line as a visual divider."""
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor

    line = slide.shapes.add_connector(
        1,  # MSO_CONNECTOR_TYPE.STRAIGHT
        Inches(0.4), Inches(top), Inches(9.6), Inches(top)
    )
    line.line.color.rgb = color or _BLUE
    line.line.width = Pt(1.5)


def _add_bullet_list(
    slide: Any,
    items: List[str],
    left: float, top: float, width: float, height: float,
    font_size: int = 11,
    color: "RGBColor" = None,
    bullet_color: "RGBColor" = None,
) -> None:
    """Adds a multi-line bullet list to a textbox."""
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN

    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, item in enumerate(items):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = f"• {item}"
        p.space_before = Pt(3)
        if p.runs:
            run = p.runs[0]
        else:
            run = p.add_run()
        run.text = f"• {item}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = color or _SILVER


def _add_table_slide(
    slide: Any,
    headers: List[str],
    rows: List[List[str]],
    left: float = 0.4, top: float = 1.6,
    width: float = 9.2, height: float = 4.5,
) -> None:
    """Adds a styled data table to the slide."""
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor

    if not rows:
        return

    n_cols = len(headers)
    n_rows = len(rows) + 1  # +1 for header

    table = slide.shapes.add_table(
        n_rows, n_cols,
        Inches(left), Inches(top),
        Inches(width), Inches(height),
    ).table

    col_width = Inches(width / n_cols)
    for i in range(n_cols):
        table.columns[i].width = col_width

    # Header row
    for j, hdr in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = hdr
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(0x1E, 0x3A, 0x5F)
        p = cell.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.runs[0] if p.runs else p.add_run()
        run.text = hdr
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = _WHITE

    # Data rows
    for i, row in enumerate(rows):
        bg = RGBColor(0x1A, 0x2A, 0x40) if i % 2 == 0 else RGBColor(0x14, 0x22, 0x38)
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = str(val)
            cell.fill.solid()
            cell.fill.fore_color.rgb = bg
            p = cell.text_frame.paragraphs[0]
            run = p.runs[0] if p.runs else p.add_run()
            run.text = str(val)
            run.font.size = Pt(9)
            run.font.color.rgb = _SILVER


# ─────────────────────────────────────────────────────────────────────────────
# SLIDE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_title_slide(prs, dataset_name, health_score, domain, report_date):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)

    # Accent bar at top
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = _BLUE
    bar.line.fill.background()

    _add_textbox(slide, "📊 Autonomous AI Data Analyst",
                 0.5, 0.4, 9, 0.5, font_size=13, color=_ACCENT, align="center")
    _add_textbox(slide, "Executive Intelligence Report",
                 0.5, 1.0, 9, 0.7, font_size=30, bold=True, color=_WHITE, align="center")
    _add_textbox(slide, dataset_name,
                 0.5, 1.8, 9, 0.5, font_size=20, color=_ACCENT, align="center")

    # Health score badge
    score_color = _GREEN if health_score >= 75 else _YELLOW if health_score >= 50 else _RED
    _add_textbox(slide, f"Data Health Score: {health_score}/100",
                 3.0, 2.8, 4.0, 0.5, font_size=16, bold=True, color=score_color, align="center")

    _add_divider(slide, 3.5)
    _add_textbox(slide, f"Domain: {domain}  |  Generated: {report_date}",
                 0.5, 3.7, 9, 0.4, font_size=11, color=_SILVER, align="center")
    _add_textbox(slide, "Powered by Multi-Agent AI • Tool-First Analytics • Zero Math Hallucinations",
                 0.5, 4.3, 9, 0.4, font_size=10, color=RGBColor(0x47, 0x55, 0x69), align="center")


def _build_health_slide(prs, quality_audit):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    _add_textbox(slide, "🩺 Data Health Audit", 0.4, 0.15, 9, 0.5,
                 font_size=20, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    score = quality_audit.get("health_score", 0)
    status = quality_audit.get("health_status", "")
    score_color = _GREEN if score >= 75 else _YELLOW if score >= 50 else _RED
    _add_textbox(slide, f"Health Score: {score}/100  ({status})", 0.4, 0.9, 5, 0.5,
                 font_size=16, bold=True, color=score_color)

    dup_pct = quality_audit.get('duplicate_pct')
    dup_pct_str = f"({dup_pct:.1f}%)" if dup_pct is not None else "(0.0%)"
    metrics = [
        f"Total Records: {quality_audit.get('total_rows', 0):,}  |  Columns: {quality_audit.get('total_columns', 0)}",
        f"Missing Data: {quality_audit.get('overall_missing_pct', 0)}%",
        f"Duplicate Rows: {quality_audit.get('duplicate_rows', 0)} {dup_pct_str}",
        f"Anomalies: {quality_audit.get('anomaly_counts', {}).get('critical', 0)} Critical  |  "
        f"{quality_audit.get('anomaly_counts', {}).get('high', 0)} High  |  "
        f"{quality_audit.get('anomaly_counts', {}).get('medium', 0)} Medium",
    ]

    anomalies = quality_audit.get("anomalies", [])[:4]
    for a in anomalies:
        sev = a.get("severity", "")
        icon = "🔴" if sev == "Critical" else "🟠" if sev == "High" else "🟡"
        metrics.append(f"{icon} [{sev}] {a.get('issue', '')[:80]}")

    briefing = quality_audit.get("quality_briefing", "")
    if briefing:
        metrics.append("")
        for line in briefing.split("\n")[:3]:
            if line.strip():
                metrics.append(line.strip()[:100])

    _add_bullet_list(slide, metrics, 0.4, 1.5, 9.2, 5.0, font_size=11)


def _build_kpi_slide(prs, kpi_results):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    domain = kpi_results.get("domain", "Business Analytics")
    _add_textbox(slide, f"💼 Core KPIs  •  {domain}", 0.4, 0.15, 9, 0.5,
                 font_size=20, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    metrics = kpi_results.get("kpi_metrics", [])[:7]
    headers = ["Metric", "Aggregation / Value", "Average", "Median", "MoM Growth"]
    rows = []
    for m in metrics:
        growth = f"{m.get('growth_pct'):+.1f}%" if m.get('growth_pct') is not None else "—"
        rows.append([
            m.get("metric_name", "")[:25],
            f"{m.get('aggregation', 'value')}: {m.get('formatted_value', m.get('formatted_total', ''))}",
            m.get("formatted_mean", ""),
            str(m.get("median", "—")),
            growth,
        ])

    _add_table_slide(slide, headers, rows, top=1.0, height=3.8)

    # Domain-specific KPIs note
    domain_kpis = kpi_results.get("domain_specific_kpis", [])
    if domain_kpis:
        domain_lines = [f"• {k.get('metric_name')}: {k.get('formatted_total')}" for k in domain_kpis[:3]]
        _add_textbox(slide, "Domain-Specific Metrics:", 0.4, 5.1, 9, 0.3,
                     font_size=10, bold=True, color=_ACCENT)
        _add_bullet_list(slide, domain_lines, 0.4, 5.45, 9, 0.9, font_size=10)


def _build_benchmark_slide(prs, benchmark_results):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    position = benchmark_results.get("overall_competitive_position", "N/A")
    _add_textbox(slide, f"🏆 Industry Benchmarks  •  Position: {position}",
                 0.4, 0.15, 9, 0.5, font_size=18, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    verdicts = benchmark_results.get("benchmark_verdicts", [])
    if not verdicts:
        _add_textbox(slide, "No metrics matched the industry benchmark database for this domain.",
                     0.4, 1.5, 9, 0.5, font_size=12, color=_SILVER)
        return

    headers = ["Metric", "Your Value", "Good ≥", "World Class ≥", "Rating"]
    rows = []
    for v in verdicts[:6]:
        bm = v.get("benchmarks", {})
        higher = v.get("higher_is_better", True)
        act_val = v.get('actual_value')
        act_str = f"{act_val:.1f}" if act_val is not None else "—"
        rows.append([
            v.get("metric_label", "")[:22],
            f"{act_str}{v.get('unit', '')}",
            f"{bm.get('good', '—')}{v.get('unit', '')}",
            f"{bm.get('world_class', '—')}{v.get('unit', '')}",
            v.get("rating", ""),
        ])

    _add_table_slide(slide, headers, rows, top=1.0, height=3.8)

    summary = benchmark_results.get("score_summary", {})
    summary_line = (
        f"⭐ {summary.get('world_class', 0)} World Class  "
        f"✅ {summary.get('good', 0)} Good  "
        f"⚠️ {summary.get('warning', 0)} Warning  "
        f"🔴 {summary.get('critical', 0)} Critical"
    )
    _add_textbox(slide, summary_line, 0.4, 5.05, 9, 0.4, font_size=11, bold=True, color=_ACCENT)


def _build_trend_slide(prs, trend_results):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    metric = trend_results.get("primary_metric", "")
    _add_textbox(slide, f"📈 Time-Series Analysis  •  {metric.replace('_', ' ').title()}",
                 0.4, 0.15, 9, 0.5, font_size=18, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    if not trend_results.get("available"):
        reason = trend_results.get("reason", "No date column detected.")
        _add_textbox(slide, f"Time-series analysis not available: {reason}",
                     0.4, 1.5, 9, 0.5, font_size=12, color=_SILVER)
        return

    ts = trend_results.get("time_series_data", {})
    mk = trend_results.get("mann_kendall_test", {})
    seas = trend_results.get("seasonality_profile", {})
    stl = trend_results.get("stl_decomposition", {})

    trend_dir = ts.get("trend_direction", "N/A")
    trend_color = _GREEN if trend_dir == "Growing" else _RED if trend_dir == "Declining" else _YELLOW

    trend_pct = ts.get('trend_pct')
    trend_pct_str = f"({trend_pct:+.1f}%)" if trend_pct is not None else "(0.0%)"
    _add_textbox(slide, f"Overall Trend: {trend_dir}  {trend_pct_str}",
                 0.4, 0.9, 9, 0.45, font_size=16, bold=True, color=trend_color)

    pv = ts.get('peak_value')
    tv = ts.get('trough_value')
    pt_drop = ts.get('peak_to_trough_drop_pct')
    peak_val_str = f"{pv:,.2f}" if pv is not None else "N/A"
    trough_val_str = f"{tv:,.2f}" if tv is not None else "N/A"
    drop_str = f"{pt_drop:+.1f}%" if pt_drop is not None else "N/A"

    bullets = [
        f"Date Range: {ts.get('date_range', 'N/A')}  |  {ts.get('total_months', 0)} months of data",
        f"Latest MoM Growth: {ts.get('latest_mom_pct', 'N/A')}%",
        f"Peak Period: {ts.get('peak_month', 'N/A')}  (value={peak_val_str})",
        f"Trough Period: {ts.get('trough_month', 'N/A')}  (value={trough_val_str})",
        f"Peak-to-Trough Swing: {drop_str}",
    ]

    if "error" not in mk and mk:
        p_val = mk.get('p_value')
        p_str = f"{p_val:.4f}" if p_val is not None else "N/A"
        sig_txt = "SIGNIFICANT ✅" if mk.get("is_significant") else "Not significant"
        bullets.append(f"Mann-Kendall Trend Test: {mk.get('trend', 'N/A')} — {sig_txt} (p={p_str})")

    if stl.get("available"):
        s_str = stl.get('seasonal_strength')
        s_str_fmt = f"{s_str:.2f}" if s_str is not None else "N/A"
        bullets.append(f"Seasonality: {stl.get('seasonality_label', 'N/A')}  (strength={s_str_fmt})")

    if seas.get("seasonal_pattern_detected"):
        best_u = seas.get('best_month_uplift_pct')
        worst_d = seas.get('worst_month_drag_pct')
        best_u_str = f"+{best_u:.1f}%" if best_u is not None else "N/A"
        worst_d_str = f"{worst_d:.1f}%" if worst_d is not None else "N/A"
        bullets.append(f"Peak Month: {seas.get('best_month')} ({best_u_str})  |  Trough Month: {seas.get('worst_month')} ({worst_d_str})")

    narrative = trend_results.get("trend_narrative", "")
    if narrative:
        bullets.append("")
        for line in narrative.split("\n")[:4]:
            if line.strip() and not line.startswith("#"):
                bullets.append(line.strip()[:110])

    _add_bullet_list(slide, bullets, 0.4, 1.45, 9.2, 5.0, font_size=11)


def _build_diagnostic_slide(prs, diagnostic_results):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    metric = diagnostic_results.get("target_metric", "")
    _add_textbox(slide, f"🔍 Root Cause & Pareto Analysis  •  {metric.replace('_', ' ').title()}",
                 0.4, 0.15, 9, 0.5, font_size=18, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    # Pareto quick stats
    pareto = diagnostic_results.get("pareto_analysis", {})
    hhi = diagnostic_results.get("hhi_concentration", {})

    bullets = []
    for dim, p_res in list(pareto.items())[:2]:
        cats = p_res.get("top_categories", [])[:3]
        top_str = "  |  ".join([
            f"{r.get(list(r.keys())[0], '?')}: {(r.get('share_pct') if r.get('share_pct') is not None else 0):.1f}%"
            for r in cats
        ])
        bullets.append(f"Pareto [{dim}]: {top_str}")
        bullets.append(f"  → {p_res.get('summary', '')[:90]}")

    for dim, h in list(hhi.items())[:2]:
        hhi_val = h.get('hhi_score')
        hhi_str = f"{hhi_val:.4f}" if hhi_val is not None else "N/A"
        bullets.append(f"HHI [{dim}]: {hhi_str} — {h.get('interpretation', '')}")

    variance = diagnostic_results.get("variance_decomposition")
    if variance and "error" not in (variance or {}):
        bullets.append(f"Period Change: {variance.get('summary', '')[:100]}")

    narrative = diagnostic_results.get("diagnostic_narrative", "")
    if narrative:
        bullets.append("")
        for line in narrative.split("\n")[:5]:
            if line.strip() and not line.startswith("#"):
                bullets.append(line.strip()[:110])

    _add_bullet_list(slide, bullets, 0.4, 0.9, 9.2, 5.5, font_size=11)


def _build_hypothesis_slide(prs, hypothesis_results):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    n_tests = hypothesis_results.get("tests_count", 0)
    n_sig = hypothesis_results.get("significant_tests", 0)
    _add_textbox(slide, f"📐 Statistical Significance  •  {n_tests} Tests  ({n_sig} Significant)",
                 0.4, 0.15, 9, 0.5, font_size=18, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    tests = hypothesis_results.get("tests_conducted", [])
    rows = []
    for t in tests[:5]:
        sig_icon = "✅" if t.get("statistically_significant") else "❌"
        effect = t.get("cohens_d") or t.get("cramers_v") or t.get("common_language_effect_size")
        effect_lbl = t.get("effect_size_label") or t.get("association_strength") or "N/A"
        rows.append([
            t.get("test", "")[:30],
            f"{t.get('p_value_formatted', t.get('p_value', 'N/A'))}",
            sig_icon,
            f"{effect:.3f} ({effect_lbl})" if effect is not None else "N/A",
        ])

    if rows:
        _add_table_slide(slide, ["Test", "p-value", "Significant?", "Effect Size"],
                         rows, top=0.85, height=2.5)

    summary = hypothesis_results.get("executive_summary", "")
    if summary:
        bullets = [line.strip()[:110] for line in summary.split("\n")
                   if line.strip() and not line.startswith("#")][:5]
        _add_bullet_list(slide, bullets, 0.4, 3.6, 9.2, 2.8, font_size=11)


def _build_actions_slide(prs, action_plan, executive_summary):
    slide = _add_slide(prs)
    _set_bg(slide, _NAVY)
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(10), Inches(0.08))
    bar.fill.solid(); bar.fill.fore_color.rgb = _BLUE; bar.line.fill.background()

    _add_textbox(slide, "🚀 Strategic Action Plan — Top 3 Priorities",
                 0.4, 0.15, 9, 0.5, font_size=20, bold=True, color=_WHITE)
    _add_divider(slide, 0.75)

    actions = []
    for i, line in enumerate(action_plan.split("\n")):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            actions.append(stripped[:120])
        if len(actions) >= 10:
            break

    icons = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    formatted = []
    action_count = 0
    for a in actions:
        if a.startswith(("1.", "2.", "3.", "Action", "Priority", "•", "-", "*")):
            icon = icons[action_count] if action_count < len(icons) else "•"
            formatted.append(f"{icon} {a.lstrip('123. -•*')}")
            action_count += 1
        else:
            formatted.append(f"   {a}")

    _add_bullet_list(slide, formatted, 0.4, 0.9, 9.2, 5.5, font_size=12)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXPORT FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def generate_pptx_report(
    output_path: str,
    dataset_name: str,
    health_score: float,
    kpi_results: Dict[str, Any],
    quality_audit: Dict[str, Any],
    diagnostic_results: Dict[str, Any],
    hypothesis_results: Dict[str, Any],
    trend_results: Dict[str, Any],
    benchmark_results: Dict[str, Any],
    executive_summary: str,
    action_plan: str,
) -> str:
    """
    Generates a complete executive PowerPoint presentation.
    Returns the path to the saved .pptx file.
    Falls back to a text summary if python-pptx is unavailable.
    """
    if not HAS_PPTX:
        txt_path = output_path.replace(".pptx", "_slides_summary.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"PRESENTATION SUMMARY: {dataset_name}\n\n")
            f.write(f"Health Score: {health_score}/100\n")
            f.write(f"Domain: {kpi_results.get('domain', 'General')}\n\n")
            f.write(f"EXECUTIVE SUMMARY:\n{executive_summary}\n\n")
            f.write(f"ACTION PLAN:\n{action_plan}\n")
        return txt_path

    try:
        prs = Presentation()
        prs.slide_width = Inches(10)
        prs.slide_height = Inches(6.5)

        domain = kpi_results.get("domain", "General Business Analytics")
        report_date = datetime.utcnow().strftime("%B %d, %Y  %H:%M UTC")

        # Build all slides
        _build_title_slide(prs, dataset_name, health_score, domain, report_date)
        _build_health_slide(prs, quality_audit)
        _build_kpi_slide(prs, kpi_results)

        if benchmark_results.get("metrics_benchmarked", 0) > 0:
            _build_benchmark_slide(prs, benchmark_results)

        _build_trend_slide(prs, trend_results)
        _build_diagnostic_slide(prs, diagnostic_results)
        _build_hypothesis_slide(prs, hypothesis_results)
        _build_actions_slide(prs, action_plan, executive_summary)

        prs.save(output_path)
        logger.info(f"PowerPoint report saved: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"PowerPoint generation failed: {e}")
        # Fallback to text
        txt_path = output_path.replace(".pptx", "_summary.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"PPTX generation error: {e}\n\n")
            f.write(f"Dataset: {dataset_name}\n")
            f.write(f"Executive Summary:\n{executive_summary}\n\n")
            f.write(f"Action Plan:\n{action_plan}\n")
        return txt_path
