import Markdown from '../components/Markdown';
// OverviewPage.jsx — Data Overview Dashboard (matches reference image layout exactly)
// Features: metric cards, data quality gauge, anomaly bar chart, correlation heatmap,
// top categories, insight bullets, executive report preview panel

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Plot from '../components/ThemedPlot';
import {
  Database, AlertTriangle, Copy, BarChart3, Activity,
  TrendingUp, Layers, FileText, Play, Clock, CheckCircle2
} from 'lucide-react';
import GaugeChart from '../components/GaugeChart';
import StatCard from '../components/StatCard';
import { useStore } from '../useStore';
import { startAnalysisJob, downloadReport } from '../api';

// Plotly dark layout defaults
const plotLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, sans-serif', color: '#a0a0a0', size: 11 },
  margin: { l: 8, r: 8, t: 8, b: 8 },
  showlegend: false,
};

// ── Anomaly Bar Chart ─────────────────────────────────────────────────────────
function AnomalyBarChart({ bars }) {
  if (!bars || bars.length === 0) {
    return (
      <div className="flex items-center justify-center" style={{ height: 200, color: 'var(--text-tertiary)' }}>
        No outliers detected ✓
      </div>
    );
  }

  const colors = bars.map((b) =>
    b.severity === 'High' ? '#ef4444' : b.severity === 'Medium' ? '#f59e0b' : '#00ff88'
  );

  return (
    <Plot
      data={[{
        type: 'bar',
        x: bars.map((b) => b.column.length > 12 ? b.column.slice(0, 12) + '…' : b.column),
        y: bars.map((b) => b.anomaly_count),
        marker: { color: colors, opacity: 0.85 },
        hovertemplate: '<b>%{x}</b><br>%{y} outliers<extra></extra>',
      }]}
      layout={{
        ...plotLayout,
        xaxis: { color: '#606060', tickangle:-30, tickfont: { size: 10 }, gridcolor: 'rgba(255,255,255,0.04)' },
        yaxis: { title:{text:'Outlier count'}, tickformat:',d', rangemode:'tozero', color: '#606060', gridcolor: 'rgba(255,255,255,0.04)' },
        margin: {l:55,r:15,t:10,b:75},
        bargap: 0.35,
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: 200 }}
      useResizeHandler
    />
  );
}

// ── Correlation Heatmap ───────────────────────────────────────────────────────
function CorrelationHeatmap({ correlation }) {
  if (!correlation || !correlation.columns || correlation.columns.length < 2) {
    return (
      <div className="flex items-center justify-center" style={{ height: 220, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
        Need ≥2 numeric columns
      </div>
    );
  }

  const cols = correlation.columns.map((c) => c.length > 8 ? c.slice(0, 8) + '…' : c);

  return (
    <Plot
      data={[{
        type: 'heatmap',
        z: correlation.matrix,
        x: correlation.columns,
        y: correlation.columns,
        colorscale: [
          [0, '#1a0a00'], [0.2, '#7f1d1d'], [0.4, '#1e3a5f'],
          [0.5, '#1a1a1a'], [0.7, '#0f3d2e'], [0.85, '#00cc6a'], [1, '#00ff88']
        ],
        zmin: -1,
        zmax: 1,
        hovertemplate: '<b>%{x} × %{y}</b><br>r = %{z:.3f}<extra></extra>',
        showscale: true,
        colorbar: {
          thickness: 10, len: 0.8,
          tickfont: { size: 9, color: '#606060' },
          bgcolor: 'rgba(0,0,0,0)',
          bordercolor: 'rgba(255,255,255,0.05)',
        },
      }]}
      layout={{
        ...plotLayout,
        xaxis: { color: '#606060', tickfont: { size: 9 }, tickangle: -30, tickvals:correlation.columns, ticktext:cols },
        yaxis: { color: '#606060', tickfont: { size: 9 }, tickvals:correlation.columns, ticktext:cols },
        margin: { l: 60, r: 50, t: 8, b: 60 },
      }}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: '100%', height: 220 }}
      useResizeHandler
    />
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  const { state, actions } = useStore();
  const { profile, analysis, projectId, datasetName, jobStatus, jobProgress, jobStep, analyzing } = state;

  const ov = profile?.overview || {};
  const health = profile?.health || {};
  const anomalyBars = profile?.anomaly_bars || [];
  const correlation = profile?.correlation || {};
  const topCats = profile?.top_categories || [];
  const anomalies = profile?.anomalies || [];

  const startAI = async () => {
    if (!projectId || analyzing) return;
    try {
      actions.setAnalyzing(true, projectId);
      const job = await startAnalysisJob(projectId);
      actions.setJob(job.job_id, projectId);
    } catch (err) {
      actions.setError(err.message, projectId);
      actions.setAnalyzing(false, projectId);
    }
  };

  if (!profile) {
    return (
      <div className="flex items-center justify-center" style={{ height: '60vh', flexDirection: 'column', gap: 16 }}>
        <Database size={40} style={{ color: 'var(--text-tertiary)' }} />
        <p className="text-secondary">Upload a dataset to see the overview</p>
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-6 page-heading"
      >
        <div>
          <span className="eyebrow">YOUR DATASET, AT A GLANCE</span>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 550, letterSpacing: '-.8px', marginTop: 9 }}>Data overview</h2>
          <p className="text-secondary text-xs" style={{ marginTop: 7, overflowWrap: 'anywhere' }}>{datasetName || 'Dataset'}</p>
        </div>

        {/* AI Analysis button */}
        {(
          <button
            className="btn btn-primary"
            onClick={startAI}
            disabled={analyzing}
          >
            {analyzing ? (
              <>
                <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                {jobProgress}% · {jobStep || 'Running…'}
              </>
            ) : (
              <>
                <Play size={14} />
                {analysis ? 'Re-run AI Analysis' : 'Run AI Analysis'}
              </>
            )}
          </button>
        )}
        {analysis && (
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} style={{ color: 'var(--accent-green)' }} />
            <span className="text-sm" style={{ color: 'var(--accent-green)' }}>AI Analysis Complete</span>
          </div>
        )}
      </motion.div>

      {/* AI Job Progress Bar */}
      {analyzing && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="card mb-4"
          style={{ borderColor: 'var(--accent-green-border)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-primary">AI Analysis Running</span>
            <span className="text-sm" style={{ color: 'var(--accent-green)' }}>{jobProgress}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${jobProgress}%` }} />
          </div>
          <p className="text-xs text-tertiary mt-2">{jobStep}</p>
        </motion.div>
      )}

      {/* ── Row 1: Metric Cards ── */}
      <div className="grid-4 mb-4">
        <StatCard
          label="Records Analyzed"
          value={ov.total_rows || 0}
          icon={Database}
          delay={0}
        />
        <StatCard
          label="Issues Detected"
          value={health.anomaly_counts?.total || 0}
          color={health.anomaly_counts?.total > 10 ? 'danger' : health.anomaly_counts?.total > 3 ? 'warning' : 'accent'}
          icon={AlertTriangle}
          delay={0.05}
        />
        <StatCard
          label="Columns"
          value={ov.total_columns || 0}
          icon={Layers}
          delay={0.1}
        />
        <StatCard
          label="Duplicates"
          value={ov.duplicate_rows || 0}
          color={ov.duplicate_rows > 0 ? 'warning' : 'accent'}
          icon={Copy}
          subtitle={ov.duplicate_pct ? `${ov.duplicate_pct}% of rows` : null}
          delay={0.15}
        />
      </div>

      {/* ── Row 2: Gauge + Anomaly Bar + Top Categories ── */}
      <div className="overview-primary-grid">

        {/* Data Quality Score (gauge) */}
        <motion.div
          className="card"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="section-title">Data Quality Score</div>
          <div className="flex items-center justify-center" style={{ padding: '8px 0' }}>
            <GaugeChart score={health.score || 0} size={180} />
          </div>
          <div className="flex justify-center gap-3 mt-2" style={{ flexWrap: 'wrap' }}>
            {Object.entries(health.anomaly_counts || {}).filter(([k]) => k !== 'total').map(([sev, count]) => (
              <div key={sev} className="text-center">
                <div className={`font-bold text-sm severity-${sev}`} style={{ fontSize: '1.1rem' }}>{count}</div>
                <div className="text-xs text-tertiary" style={{ textTransform: 'capitalize' }}>{sev}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Anomaly Detection bar chart */}
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="section-title" style={{ marginBottom: 0 }}>Anomaly Detection</div>
            <div className="flex gap-2">
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.7rem', color: '#ef4444' }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#ef4444', display: 'inline-block' }} />
                High
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.7rem', color: '#f59e0b' }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#f59e0b', display: 'inline-block' }} />
                Med
              </span>
            </div>
          </div>
          <AnomalyBarChart bars={anomalyBars} />
        </motion.div>

        {/* Top Categories */}
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="section-title">Top Categories</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {topCats.length > 0 ? topCats.map((cat, i) => {
              const colors = ['var(--accent-purple)', 'var(--accent-blue)', 'var(--accent-amber)', 'var(--accent-green)'];
              const c = colors[i % colors.length];
              return (
                <div key={cat.column}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs text-secondary truncate" style={{ maxWidth: '70%' }}>{cat.column}</span>
                    <span className="text-xs font-semibold" style={{ color: c }}>{cat.pct}%</span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width: `${cat.pct}%`, background: c, boxShadow: 'none' }} />
                  </div>
                </div>
              );
            }) : (
              <p className="text-xs text-tertiary">No categorical columns found</p>
            )}
          </div>

          {/* Potential targets */}
          {profile?.potential_targets?.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div className="section-title">Suggested Targets</div>
              {profile.potential_targets.slice(0, 3).map((t) => (
                <div key={t.column} className="flex items-center justify-between mb-2">
                  <span className="text-xs text-secondary truncate">{t.column}</span>
                  <span className={`badge badge-${t.task_type?.includes('class') ? 'purple' : 'blue'}`} style={{ fontSize: '0.6rem' }}>
                    {t.task_type?.replace('_', ' ')}
                  </span>
                </div>
              ))}
            </div>
          )}
        </motion.div>
      </div>

      {/* ── Row 3: Correlation Heatmap + Insight Summary + Executive Report ── */}
      <div className="overview-secondary-grid">

        {/* Correlation heatmap */}
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35 }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="section-title" style={{ marginBottom: 0 }}>Correlation Analysis</div>
            {correlation.high_correlations?.length > 0 && (
              <span className="badge badge-amber">{correlation.high_correlations.length} strong</span>
            )}
          </div>
          <CorrelationHeatmap correlation={correlation} />
        </motion.div>

        {/* Insight summary */}
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <div className="section-title">Insight Summary</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {/* Auto-generated insights from profile data */}
            {[
              ov.duplicate_rows > 0 && {
                dot: 'var(--accent-amber)',
                text: `${ov.duplicate_rows} duplicate rows detected (${ov.duplicate_pct}%) — verify whether repeated records are valid before deduplicating.`,
              },
              ov.overall_missing_pct > 5 && {
                dot: 'var(--accent-red)',
                text: `${ov.overall_missing_pct}% of cells are null across ${ov.cols_with_missing} columns — review missing-data patterns before choosing a treatment.`,
              },
              correlation.high_correlations?.length > 0 && {
                dot: 'var(--accent-purple)',
                text: `${correlation.high_correlations.length} strong correlations found — potential multicollinearity risk.`,
              },
              profile?.potential_targets?.length > 0 && {
                dot: 'var(--accent-blue)',
                text: `Recommended ML target: "${profile.potential_targets[0]?.column}" (${profile.potential_targets[0]?.task_type?.replace('_', ' ')}).`,
              },
              health.score >= 90 && {
                dot: 'var(--accent-green)',
                text: `Data quality score ${health.score}/100 — review the detailed quality checks before use.`,
              },
            ].filter(Boolean).slice(0, 5).map((item, i) => (
              <div key={i} className="flex gap-2" style={{ padding: '4px 0' }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 5,
                  background: item.dot,
                }} />
                <p className="text-xs text-secondary" style={{ lineHeight: 1.6 }}>{item.text}</p>
              </div>
            ))}
            {!analysis && (
              <div className="flex gap-2 mt-2">
                <div style={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 5, background: 'var(--text-tertiary)' }} />
                <p className="text-xs text-tertiary" style={{ lineHeight: 1.6 }}>
                  Run AI Analysis for deeper root-cause insights, KPIs, and hypothesis tests.
                </p>
              </div>
            )}
          </div>
        </motion.div>

        {/* Executive Report panel */}
        <motion.div
          className="card"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="section-title" style={{ marginBottom: 0 }}>Executive Report</div>
            <button className="icon-button" title="Open executive report" aria-label="Open executive report" onClick={() => actions.setTab('report')}><FileText size={15} /></button>
          </div>

          {analysis?.report_pdf_url ? (
            <div>
              <div style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: 12, marginBottom: 12 }}>
                <div className="text-xs font-semibold text-primary mb-2">📄 AI Analysis Report</div>
                <div className="report-preview"><Markdown>{analysis.report_summary}</Markdown></div>
              </div>
              <div className="grid-2" style={{ gap: 8 }}>
                <div className="stat-card" style={{ padding: '10px 12px' }}>
                  <div className="stat-label">Health Score</div>
                  <div className="stat-value accent" style={{ fontSize: '1.4rem' }}>
                    {analysis.health_score}
                    <span style={{ fontSize: '0.6em' }}>/100</span>
                  </div>
                </div>
                <div className="stat-card" style={{ padding: '10px 12px' }}>
                  <div className="stat-label">Logged steps</div>
                  <div className="stat-value" style={{ fontSize: '1.4rem' }}>
                    {analysis.execution_steps?.length || 0}
                  </div>
                </div>
              </div>
              <button
                onClick={async () => { try { await downloadReport(projectId, 'pdf'); } catch (error) { actions.setError(error.message, projectId); } }}
                className="btn btn-primary w-full mt-3"
                style={{ justifyContent: 'center', textDecoration: 'none' }}
              >
                <FileText size={14} />
                Download PDF Report
              </button>
            </div>
          ) : (
            <div>
              <div style={{
                background: 'var(--bg-elevated)', borderRadius: 8, padding: 12,
                marginBottom: 12, border: '1px dashed var(--border-subtle)',
              }}>
                <div className="text-xs font-semibold text-primary mb-2">Your report will appear here</div>
                <div style={{ height: 60, background: 'linear-gradient(90deg, rgba(0,255,136,0.05), rgba(168,85,247,0.05))', borderRadius: 4 }} />
              </div>
              {analysis ? (
                <div className="grid-2" style={{ gap: 8, marginBottom: 12 }}>
                  <div className="stat-card" style={{ padding: '10px 12px' }}>
                    <div className="stat-label">Health</div>
                    <div className="stat-value accent" style={{ fontSize: '1.3rem' }}>
                      {analysis.health_score}<span style={{ fontSize: '0.6em' }}>/100</span>
                    </div>
                  </div>
                  <div className="stat-card" style={{ padding: '10px 12px' }}>
                    <div className="stat-label">Anomalies</div>
                    <div className="stat-value warning" style={{ fontSize: '1.3rem' }}>
                      {profile?.health?.anomaly_counts?.total || 0}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-xs text-tertiary mb-3" style={{ lineHeight: 1.6 }}>
                  Run AI Analysis to generate a full executive briefing with root-cause findings and action plan.
                </div>
              )}
              <button
                className="btn btn-ghost w-full"
                onClick={() => actions.setTab('report')}
                style={{ justifyContent: 'center' }}
              >
                <FileText size={14} />
                View Report Section
              </button>
            </div>
          )}
        </motion.div>
      </div>

      {/* ── Column Profile Table ── */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <div className="section-title">Column Profiles</div>
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Column</th>
                <th>Type</th>
                <th>Missing</th>
                <th>Unique</th>
                <th>Outliers</th>
                <th>Distribution</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(profile?.columns || {}).map(([col, info]) => (
                <tr key={col}>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 500, fontFamily: 'JetBrains Mono, monospace', fontSize: '0.8rem' }}>{col}</td>
                  <td>
                    <span className={`badge ${
                      info.col_type?.includes('numeric') ? 'badge-blue' :
                      info.col_type?.includes('categorical') ? 'badge-purple' :
                      info.col_type === 'datetime' ? 'badge-amber' :
                      info.col_type === 'id' ? 'badge-green' :
                      'badge-blue'
                    }`} style={{ fontSize: '0.65rem' }}>
                      {info.col_type?.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: info.missing?.severity === 'Critical' ? '#ef4444' : info.missing?.severity === 'High' ? '#f59e0b' : 'var(--text-secondary)' }}>
                      {info.missing?.pct?.toFixed(1)}%
                    </span>
                  </td>
                  <td className="text-secondary">{info.unique_count?.toLocaleString()}</td>
                  <td>
                    {info.outliers?.iqr_count > 0 ? (
                      <span className={`badge ${info.outliers.severity === 'High' ? 'badge-red' : 'badge-amber'}`} style={{ fontSize: '0.65rem' }}>
                        {info.outliers.iqr_count} ({info.outliers.iqr_pct}%)
                      </span>
                    ) : (
                      <span className="text-xs" style={{ color: 'var(--accent-green)' }}>None</span>
                    )}
                  </td>
                  <td className="text-secondary text-xs">
                    {info.distribution ? (
                      <span title={`skew: ${info.distribution.skewness}`}>
                        μ={info.distribution.mean?.toFixed(2)}, σ={info.distribution.std?.toFixed(2)}
                        <br />
                        <span style={{ color: 'var(--text-tertiary)' }}>{info.distribution.distribution_shape}</span>
                      </span>
                    ) : (
                      info.mode ? <span>mode: {String(info.mode).slice(0, 12)}</span> : '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
