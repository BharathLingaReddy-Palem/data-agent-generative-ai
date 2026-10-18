import Markdown from '../components/Markdown';
// ReportPage.jsx — Executive PDF Report viewer and downloader
import { motion } from 'framer-motion';
import { FileText, Download, Play, CheckCircle2 } from 'lucide-react';
import { useStore } from '../useStore';
import { useState } from 'react';
import { downloadReport } from '../api';

export default function ReportPage() {
  const { state, actions } = useStore();
  const { analysis, analyzing, projectId } = state;
  const [downloading, setDownloading] = useState(null);
  const [downloadError, setDownloadError] = useState('');
  async function download(format) {
    setDownloading(format); setDownloadError('');
    try {await downloadReport(projectId, format);}
    catch (error) {setDownloadError(error.message);}
    finally {setDownloading(null);}
  }

  if (!analysis) {
    return (
      <div>
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: 24 }}
        >
          Executive Report
        </motion.h2>
        <div className="card" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <FileText size={48} style={{ color: 'var(--text-tertiary)', margin: '0 auto 16px' }} />
          <h3 className="text-primary font-semibold mb-2">No Report Generated Yet</h3>
          <p className="text-secondary text-sm mb-6" style={{ maxWidth: 400, margin: '0 auto 24px' }}>
            Run the AI analysis pipeline from the Data Overview page to generate an executive PDF report.
          </p>
          <button
            className="btn btn-primary"
            onClick={() => actions.setTab('overview')}
          >
            <Play size={14} />
            Go to Overview
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-6 report-heading"
      >
        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Executive Report
        </h2>
        <div className="flex gap-2">
          {['pdf','pptx'].map(format => analysis.report_artifacts?.[format]?.available && (
            <button key={format} className="btn btn-primary" disabled={!!downloading} onClick={() => download(format)}>
              <Download size={14} />
              {downloading===format ? 'Downloading…' : format==='pdf' ? 'Download PDF' : 'Download PowerPoint'}
            </button>
          ))}
        </div>
      </motion.div>
      {downloadError && <p role="alert" className="text-sm mb-4">{downloadError}</p>}

      {/* Summary */}
      {analysis.report_summary && (
        <motion.div
          className="card mb-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          style={{ borderColor: 'var(--accent-green-border)' }}
        >
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 size={16} style={{ color: 'var(--accent-green)' }} />
            <span className="font-semibold text-primary">Executive Summary</span>
          </div>
          <Markdown>{analysis.report_summary}</Markdown>
        </motion.div>
      )}

      {/* Full markdown report */}
      {analysis.report_markdown && (
        <motion.div
          className="card"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <div className="section-title">Full Report</div>
          <Markdown>{analysis.report_markdown}</Markdown>
        </motion.div>
      )}

      {/* Errors */}
      {analysis.errors?.length > 0 && (
        <motion.div
          className="card mt-4"
          style={{ borderColor: 'rgba(239,68,68,0.3)' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
        >
          <div className="section-title">Pipeline Warnings</div>
          {analysis.errors.map((e, i) => (
            <div key={i} className="text-xs text-secondary mb-1" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
              ⚠ {e}
            </div>
          ))}
        </motion.div>
      )}
    </div>
  );
}
