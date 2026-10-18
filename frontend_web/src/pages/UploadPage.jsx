// Dataset entrance with accessible file selection and real sample loading.
import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, CheckCircle, XCircle, ArrowRight } from 'lucide-react';
import { profileDataset, loadSampleDataset, listProjects, restoreProject } from '../api';
import { useStore } from '../useStore';

// ── Sample dataset cards ─────────────────────────────────────────────────────
const SAMPLES = [
  {
    id: 'ecommerce_sales',
    name: 'E-Commerce Retail',
    domain: 'Retail & Sales',
    rows: '600 rows',
    icon: '🛒',
  },
  {
    id: 'saas_churn',
    name: 'SaaS Churn',
    domain: 'Subscriptions',
    rows: '600 rows',
    icon: '📊',
  },
  {
    id: 'ops_fulfillment',
    name: 'Supply Chain',
    domain: 'Operations',
    rows: '600 rows',
    icon: '🚚',
  },
];

// ── Main component ────────────────────────────────────────────────────────────
export default function UploadPage() {
  const { state, actions } = useStore();
  const [projects, setProjects] = useState([]);
  const [projectsError, setProjectsError] = useState('');
  const [opening, setOpening] = useState(null);
  useEffect(() => {let active=true; listProjects().then(rows=>{if(active)setProjects(rows.filter(row=>row.session_available));}).catch(error=>{if(active)setProjectsError(error.message);}); return()=>{active=false;};}, []);
  async function openSaved(project) {
    const loadId=actions.beginLoad(); setOpening(project.id);
    try {const data=await restoreProject(project.id); actions.selectSavedProject(data,loadId);}
    catch(error){actions.setError(error.message,undefined,loadId);}
    finally{setOpening(null);}
  }
  const [file, setFile] = useState(null);
  const [loadingSample, setLoadingSample] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | profiling | done | error
  const [errorMsg, setErrorMsg] = useState('');

  const handleProfile = useCallback(async (fileObj) => {
    const loadId = actions.beginLoad();
    setFile(fileObj);
    setStatus('profiling');
    setErrorMsg('');
    actions.setUploading(true, loadId);
    actions.setProfiling(true, loadId);
    try {
      const result = await profileDataset(fileObj);
      actions.setProject(result.project_id, result.dataset_name, loadId);
      actions.setProfile(result, result.project_id, loadId);
      setStatus('done');
      actions.setTab('overview', result.project_id, loadId);
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.message);
      actions.setError(err.message, undefined, loadId);
    } finally {
      actions.setUploading(false, loadId);
      actions.setProfiling(false, loadId);
    }
  }, [actions]);

  const onDrop = useCallback((accepted) => {
    if (accepted[0]) handleProfile(accepted[0]);
  }, [handleProfile]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.ms-excel': ['.xls', '.xlsx'],
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
    maxFiles: 1,
    multiple: false,
    disabled: status === 'profiling' || loadingSample !== null || opening !== null,
    onDropRejected: rejections => {
      const message = rejections.flatMap(item => item.errors.map(error => error.code === 'file-invalid-type' ? 'Choose a CSV, XLS or XLSX file.' : error.message)).join(' ');
      setErrorMsg(message); setStatus('error');
    },
  });

  const handleSample = async (sampleId) => {
    const loadId = actions.beginLoad();
    setLoadingSample(sampleId);
    try {
      const result = await loadSampleDataset(sampleId);
      actions.setProject(result.project_id, result.dataset_name, loadId);
      actions.setProfile(result.profile, result.project_id, loadId);
      actions.setTab('overview', result.project_id, loadId);
    } catch (err) {
      actions.setError(err.message, undefined, loadId);
    } finally {
      setLoadingSample(null);
    }
  };

  return (
    <div className="upload-page">
      {(projects.length > 0 || projectsError) && <section className="saved-projects card" aria-label="Saved datasets"><div className="section-title">Continue your work</div>{projectsError && <p role="alert" className="text-sm text-secondary">{projectsError}</p>}<div className="saved-project-list">{projects.map(project=><button key={project.id} className="saved-project-button" disabled={opening !== null || loadingSample !== null || status === 'profiling'} onClick={()=>openSaved(project)}><span><strong>{project.name}</strong><small>{opening===project.id?'Opening…':'Restore analysis, models and conversation'}</small></span><ArrowRight size={16}/></button>)}</div></section>}
      {/* Hero header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        className="upload-hero"
      >
        <span className="eyebrow"><span className="status-dot" /> YOUR NEXT DISCOVERY STARTS HERE</span>
        <h1>Big questions. <span>Meet your data.</span></h1>
        <p>Bring a dataset into your workspace. Get a clear view of its quality, explore what matters, and decide where to go next.</p>
      </motion.div>

      {/* File selection */}
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1, duration: 0.4 }}
        className="mb-6"
      >
        <div
          {...getRootProps({ 'aria-label': 'Choose a CSV or Excel dataset' })}
          className={`dropzone ${isDragActive ? 'active' : ''}`}
          style={{ position: 'relative', minHeight: 240, padding: 0 }}
        >
          <input {...getInputProps()} />

          {/* Upload content overlay */}
          <div style={{
            position: 'relative', zIndex: 2,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            height: '100%', minHeight: 240, padding: '40px 24px',
          }}>
            <AnimatePresence mode="wait">
              {status === 'profiling' ? (
                <motion.div key="profiling" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-4">
                  <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
                  <p style={{ color: 'var(--accent-green)', fontWeight: 600 }}>Profiling dataset…</p>
                  <p className="text-xs text-tertiary">Detecting column types, outliers, correlations…</p>
                </motion.div>
              ) : status === 'done' ? (
                <motion.div key="done" initial={{ scale: 0 }} animate={{ scale: 1 }} className="flex flex-col items-center gap-3">
                  <CheckCircle size={48} style={{ color: 'var(--accent-green)' }} />
                  <p style={{ color: 'var(--accent-green)', fontWeight: 700, fontSize: '1.1rem' }}>
                    Profile complete! Redirecting…
                  </p>
                </motion.div>
              ) : status === 'error' ? (
                <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-3">
                  <XCircle size={40} style={{ color: 'var(--accent-red)' }} />
                  <p role="alert" style={{ color: '#fbbdbd', fontWeight: 500 }}> {errorMsg}</p>
                  <button className="btn btn-ghost" onClick={event => { event.stopPropagation(); setStatus('idle'); }}>Try again</button>
                </motion.div>
              ) : (
                <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-center gap-3">
                  <div className="upload-emblem"><UploadCloud size={28} strokeWidth={1.4} /></div>
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ fontSize: '1.05rem', fontWeight: 600, color: isDragActive ? 'var(--accent-green)' : 'var(--text-primary)' }}>
                      {isDragActive ? 'Drop it here!' : 'Drag & drop your CSV or Excel file'}
                    </p>
                    <p className="text-secondary text-sm mt-2">or click to browse your files</p>
                  </div>
                  <div className="flex gap-2 mt-2">
                    {['CSV', 'XLS', 'XLSX'].map((f) => (
                      <span key={f} className="badge">{f}</span>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </motion.div>

      {/* Divider */}
      <div className="flex items-center gap-4 mb-6">
        <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
        <span className="text-xs text-tertiary font-medium">OR TRY A SAMPLE DATASET</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
      </div>

      {/* Sample datasets */}
      <div className="grid-3 mb-8">
        {SAMPLES.map((sample, i) => (
          <motion.div
            key={sample.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
          >
            <button
              className="card sample-card"
              onClick={() => handleSample(sample.id)}
              disabled={loadingSample !== null || status === 'profiling'}
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="sample-icon" aria-hidden="true">{sample.icon}</span>
                <div>
                  <div className="font-semibold text-sm text-primary">{sample.name}</div>
                  <div className="text-xs text-tertiary">{sample.domain}</div>
                </div>
                {loadingSample === sample.id && <div className="spinner" style={{ marginLeft: 'auto' }} />}
              </div>
              <div className="flex items-center justify-between">
                <span className="badge badge-blue">{sample.rows}</span>
                <ArrowRight size={14} style={{ color: 'var(--text-tertiary)' }} />
              </div>
            </button>
          </motion.div>
        ))}
      </div>

      {/* Workflow guidance */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="upload-flow"
      >
          {[
            ['01', 'Get to know your data', 'Review column types, missing values and quality checks.'],
            ['02', 'Follow your curiosity', 'Explore distributions or ask the AI analyst a question.'],
            ['03', 'Take the next step', 'Compare models or export a report to share your findings.'],
          ].map(([number, label, description]) => (
            <div key={number}><span>{number}</span><div><strong>{label}</strong><p>{description}</p></div></div>
          ))}
      </motion.div>
    </div>
  );
}
