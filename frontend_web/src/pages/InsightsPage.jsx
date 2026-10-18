import Markdown from '../components/Markdown';
// InsightsPage.jsx — AI Insights from analysis pipeline
import { motion } from 'framer-motion';
import { Brain, Lightbulb, Target, TrendingUp, AlertTriangle, Play } from 'lucide-react';
import { useStore } from '../useStore';
import { insightSections, planExplanation, hypothesisCells } from '../analysisView';

export default function InsightsPage() {
  const { state, actions } = useStore();
  const { analysis, analyzing, jobProgress, jobStep } = state;

  if (!analysis) {
    return (
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: 24 }}
        >
          AI Insights
        </motion.h2>
        <div className="card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <Brain size={48} style={{ color: 'var(--text-tertiary)', margin: '0 auto 16px' }} />
          <h3 className="text-primary font-semibold mb-2">AI Analysis Not Run Yet</h3>
          <p className="text-secondary text-sm mb-6" style={{ maxWidth: 400, margin: '0 auto 24px' }}>
            Run the AI analysis pipeline to get deep root-cause insights, KPI analysis,
            hypothesis testing results, and trend detection.
          </p>
          {analyzing && (
            <div>
              <div className="progress-bar" style={{ maxWidth: 300, margin: '0 auto 12px' }}>
                <div className="progress-fill" style={{ width: `${jobProgress}%` }} />
              </div>
              <p className="text-xs text-tertiary">{jobStep}</p>
            </div>
          )}
          {!analyzing && (
            <button
              className="btn btn-primary"
              onClick={() => actions.setTab('overview')}
            >
              <Play size={14} />
              Go to Overview to Start AI Analysis
            </button>
          )}
        </div>
      </div>
    );
  }

  const decoration = {
    kpi:{icon:Target,color:'var(--accent-green)'},
    diagnostic:{icon:AlertTriangle,color:'var(--accent-red)'},
    trend:{icon:TrendingUp,color:'var(--accent-blue)'},
    hypothesis:{icon:Lightbulb,color:'var(--accent-amber)'},
  };
  const sections = insightSections(analysis).map(section => ({...section,...decoration[section.id]}));


  return (
    <div>
      <motion.h2
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 24 }}
      >
        AI Insights
      </motion.h2>

      {analysis.kpi_results?.kpi_metrics?.some(row => row.column !== 'rows' && !row.aggregation) && <div className="card mb-4" role="status"><strong>Saved analysis needs refreshing</strong><p className="text-sm text-secondary mt-2">This result predates the aggregation checks. Re-run AI Analysis from Data Overview before relying on its KPI narrative or report.</p></div>}
      {/* Analysis plan */}
      {analysis.analysis_plan && (
        <motion.div
          className="card mb-4"
          style={{ borderColor: 'var(--accent-green-border)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className="section-title">Analysis Plan (Supervisor Agent)</div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            {(analysis.analysis_plan?.agents_to_run || []).map((agent) => (
              <span key={agent} className="badge badge-green" style={{ fontSize: '0.72rem' }}>✓ {agent}</span>
            ))}
          </div>
          {planExplanation(analysis) && (
            <p className="text-xs text-secondary mt-3" style={{ lineHeight: 1.7 }}>
              {planExplanation(analysis)}
            </p>
          )}
        </motion.div>
      )}

      {/* Insight sections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {sections.map(({ id, icon: Icon, color, title, content, data }, i) => (
          <motion.div
            key={title}
            className="card"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.08 }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div style={{
                width: 36, height: 36, borderRadius: 8, flexShrink: 0,
                background: `color-mix(in srgb, ${color} 8%, transparent)`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Icon size={18} style={{ color }} />
              </div>
              <h3 className="font-semibold text-primary" style={{ fontSize: '1rem' }}>{title}</h3>
            </div>

            <div style={{
              background: 'var(--bg-elevated)', borderRadius: 8,
              padding: '14px 16px', borderLeft: `3px solid ${color}`,
              marginBottom: data ? 16 : 0,
            }}>
              <Markdown>{content}</Markdown>
            </div>

            {data?.length > 0 && <div className="table-scroll">
              <table className="data-table mt-2">
                <thead><tr>{(id === 'kpi' ? ['Metric', 'Aggregation', 'Value', 'Context'] : ['Test', 'Comparison', 'Raw p-value', 'Holm-adjusted p-value', 'Result', 'Assumptions']).map(k => <th key={k}>{k.replace(/_/g, ' ')}</th>)}</tr></thead>
                <tbody>{data.map((row,j) => <tr key={j}>{(id === 'kpi' ? [row.metric_name,
                  row.aggregation || (row.column === 'rows' ? 'count' : 'Legacy result'),
                  row.formatted_value || (row.column === 'rows' ? row.formatted_total : 'Re-run analysis'),
                  row.aggregation_note || (row.column === 'rows' ? 'Dataset rows' : 'Saved before aggregation checks')]
                  : hypothesisCells(row)).map((v,k) => <td key={k}>{typeof v === 'number' ? v.toLocaleString(undefined,{maximumSignificantDigits:5}) : v != null && typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}</td>)}</tr>)}</tbody>
              </table>
            </div>}
          </motion.div>
        ))}
      </div>

      {analysis.errors?.length > 0 && <div className="card mt-4" role="alert">
        <div className="section-title">Pipeline Warnings</div>
        {analysis.errors.map((error,index) => <p className="text-sm text-secondary" key={index}>{error}</p>)}
      </div>}

      {/* Execution log */}
      {analysis.execution_steps?.length > 0 && (
        <motion.div
          className="card mt-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
        >
          <div className="section-title">Execution Log</div>
          <div style={{ maxHeight: 200, overflowY: 'auto' }}>
            {analysis.execution_steps.map((step, i) => (
              <div key={i} className="flex items-start gap-3 py-2" style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                <span className="text-xs text-tertiary" style={{ fontFamily: 'JetBrains Mono, monospace', flexShrink: 0 }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <p className="text-xs text-secondary" style={{ lineHeight: 1.6 }}>{step}</p>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  );
}
