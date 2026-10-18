import Markdown from '../components/Markdown';
// QualityPage.jsx — Health & Quality deep-dive page
import { motion } from 'framer-motion';
import Plot from '../components/ThemedPlot';
import { AlertTriangle, CheckCircle2, XCircle, AlertCircle, Minus } from 'lucide-react';
import { useStore } from '../useStore';
import GaugeChart from '../components/GaugeChart';

const plotLayout = {
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: { family: 'Inter, sans-serif', color: '#a0a0a0', size: 11 },
  margin: { l: 40, r: 10, t: 10, b: 40 },
  showlegend: false,
};

const SEV_ICON = {
  Critical: XCircle,
  High: AlertTriangle,
  Medium: AlertCircle,
  Low: Minus,
};

const SEV_COLOR = {
  Critical: 'var(--accent-red)',
  High: 'var(--accent-amber)',
  Medium: 'var(--accent-blue)',
  Low: 'var(--accent-green)',
};

export default function QualityPage() {
  const { state } = useStore();
  const { profile, analysis } = state;

  const health = profile?.health || analysis?.quality_audit || {};
  const score = health.score ?? health.health_score ?? 0;
  const anomalies = profile?.anomalies || analysis?.quality_audit?.anomalies || [];
  const cols = profile?.columns || {};
  const ov = profile?.overview || {};

  // Missing value bar data
  const missingCols = Object.entries(cols)
    .filter(([, v]) => v.missing?.pct > 0)
    .sort(([, a], [, b]) => b.missing.pct - a.missing.pct);

  return (
    <div>
      <motion.h2
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 24 }}
      >
        Data Health & Quality Audit
      </motion.h2>

      {/* Top row */}
      <div className="quality-summary-grid">
        {/* Gauge */}
        <motion.div className="card" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
          <div className="section-title">Quality Score</div>
          <div className="flex items-center justify-center">
            <GaugeChart score={score} size={180} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
            {[
              ['Rows', ov.total_rows?.toLocaleString()],
              ['Columns', ov.total_columns],
              ['Missing cells', `${ov.overall_missing_pct}%`],
              ['Duplicates', ov.duplicate_rows],
            ].map(([l, v]) => (
              <div key={l} className="stat-card" style={{ padding: '8px 10px' }}>
                <div className="stat-label" style={{ fontSize: '0.65rem' }}>{l}</div>
                <div className="font-bold text-sm text-primary">{v ?? '—'}</div>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Missing values bar */}
        <motion.div className="card" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.15 }}>
          <div className="section-title">Missing Values by Column</div>
          {missingCols.length > 0 ? (
            <Plot
              data={[{
                type: 'bar',
                orientation: 'h',
                x: missingCols.map(([, v]) => v.missing.pct),
                y: missingCols.map(([k]) => k),
                marker: {
                  color: missingCols.map(([, v]) =>
                    v.missing.severity === 'Critical' ? '#ef4444' :
                    v.missing.severity === 'High' ? '#f59e0b' : '#00b4d8'
                  ),
                  opacity: 0.85,
                },
                hovertemplate: '<b>%{y}</b>: %{x:.1f}% missing<extra></extra>',
              }]}
              layout={{
                ...plotLayout,
                xaxis: { title: 'Missing %', color: '#606060', range: [0, Math.min(100, Math.max(5, ...missingCols.map(([,v])=>v.missing.pct * 1.2)))], gridcolor: 'rgba(255,255,255,0.04)' },
                yaxis: { color: '#606060', automargin: true, tickfont: { size: 10 } },
                margin: { l: 120, r: 20, t: 8, b: 45 },
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: '100%', height: Math.max(260, missingCols.length * 22 + 60) }}
              useResizeHandler
            />
          ) : (
            <div className="flex items-center justify-center gap-2" style={{ height: 200, color: 'var(--accent-green)' }}>
              <CheckCircle2 size={20} />
              <span className="text-sm font-medium">No missing values detected!</span>
            </div>
          )}
        </motion.div>
      </div>

      {/* Anomalies list */}
      <motion.div
        className="card"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="section-title" style={{ marginBottom: 0 }}>
            Detected Issues ({anomalies.length})
          </div>
          <div className="flex gap-2">
            {Object.entries(health.anomaly_counts || {}).filter(([k]) => k !== 'total').map(([sev, cnt]) => (
              cnt > 0 && (
                <span key={sev} className="badge" style={{
                  background: `${SEV_COLOR[sev] || '#666'}18`,
                  color: SEV_COLOR[sev] || '#666',
                  border: `1px solid ${SEV_COLOR[sev] || '#666'}44`,
                  fontSize: '0.65rem',
                }}>
                  {cnt} {sev}
                </span>
              )
            ))}
          </div>
        </div>

        {anomalies.length === 0 ? (
          <div className="flex items-center justify-center gap-3 py-8" style={{ color: 'var(--accent-green)' }}>
            <CheckCircle2 size={24} />
            <span className="font-medium">No issues detected by the current checks.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {anomalies.map((a, i) => {
              const Icon = SEV_ICON[a.severity] || Minus;
              const color = SEV_COLOR[a.severity] || '#666';
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.3 + i * 0.03 }}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 12,
                    padding: '10px 14px', borderRadius: 'var(--radius-md)',
                    background: `color-mix(in srgb, ${color} 3%, transparent)`, border: `1px solid ${color}20`,
                  }}
                >
                  <Icon size={15} style={{ color, flexShrink: 0, marginTop: 1 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{
                      fontFamily: 'JetBrains Mono, monospace', fontSize: '0.78rem',
                      color: 'var(--text-primary)', fontWeight: 600,
                    }}>{a.column}</span>
                    <span className="text-xs text-secondary" style={{ marginLeft: 10 }}>{a.issue}</span>
                  </div>
                  <span style={{
                    fontSize: '0.65rem', fontWeight: 600, color, flexShrink: 0,
                    padding: '2px 8px', borderRadius: 999,
                    background: `color-mix(in srgb, ${color} 9%, transparent)`, border: `1px solid color-mix(in srgb, ${color} 20%, transparent)`,
                  }}>
                    {a.severity}
                  </span>
                </motion.div>
              );
            })}
          </div>
        )}
      </motion.div>

      {/* LLM Quality briefing from AI analysis */}
      {analysis?.quality_audit?.quality_briefing && (
        <motion.div
          className="card mt-4"
          style={{ borderColor: 'var(--accent-green-border)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <div className="section-title">AI Quality Briefing</div>
          <div style={{
            background: 'rgba(0,255,136,0.04)', borderRadius: 8,
            padding: 16, borderLeft: '3px solid var(--accent-green)',
          }}>
            <Markdown>{analysis.quality_audit.quality_briefing}</Markdown>
          </div>
        </motion.div>
      )}
    </div>
  );
}
