import { Evaluation } from './WorkspacePages';
import { startAutoML, predict, downloadModel } from '../api';
// AutoMLPage.jsx — Autonomous Multi-Model Benchmark & Leaderboard
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Trophy, Cpu, Zap, Download, Play, CheckCircle2,
  TrendingUp, BarChart2, HelpCircle, ArrowRight, RefreshCw, Sliders
} from 'lucide-react';
import Plot from '../components/ThemedPlot';
import { useStore, useProjectState } from '../useStore';

export default function AutoMLPage() {
  const { state, actions } = useStore();
  const { projectId, datasetName, profile } = state;

  const [targetCol, setTargetCol] = useProjectState('automlTarget');
  const [taskType, setTaskType] = useProjectState('automlTask');
  const [isTraining, setIsTraining] = useProjectState('automlTraining');
  const [jobStatus, setJobStatus] = useProjectState('automlJobStatus');
  const [results, setResults] = useProjectState('automlResults');
  const [activeSubTab, setActiveSubTab] = useProjectState('automlTab'); // leaderboard | xai | whatif

  const [splitStrategy,setSplitStrategy]=useProjectState('automlSplit');
  const [splitColumn,setSplitColumn]=useProjectState('automlSplitColumn');
  const [holdoutFraction,setHoldoutFraction]=useProjectState('automlHoldout');
  const [featureSettings]=useProjectState('featureSettings');
  // What-If input state
  const [whatIfInputs, setWhatIfInputs] = useProjectState('whatIfInputs');
  const [predictionResult, setPredictionResult] = useProjectState('predictionResult');
  const [isPredicting, setIsPredicting] = useProjectState('isPredicting');

  // Extract safe array of column names regardless of profile format
  const columns = Array.isArray(profile?.column_names)
    ? profile.column_names
    : Array.isArray(profile?.columns)
    ? profile.columns
    : (profile?.column_profiles && typeof profile.column_profiles === 'object')
    ? Object.keys(profile.column_profiles)
    : (profile?.columns && typeof profile.columns === 'object')
    ? Object.keys(profile.columns)
    : (profile?.col_types && typeof profile.col_types === 'object')
    ? Object.keys(profile.col_types)
    : [];

  // Initialize candidate target column from profile
  useEffect(() => {
    if (columns.length > 0 && !targetCol) {
      const candidates = [
        'profit', 'sales', 'churn', 'churned', 'status', 'target',
        'label', 'class', 'price', 'revenue', 'survived', 'target_salary', 'category'
      ];
      const matched = columns.find(c => candidates.includes(String(c).toLowerCase()));
      setTargetCol(matched || columns[columns.length - 1]);
    }
  }, [columns, targetCol]);

  // Start AutoML
  const handleStartAutoML = async () => {
    if (!projectId || state.analyzing || isTraining) return;
    setIsTraining(true);
    setJobStatus({ status: 'queued', current_step: 'Starting AutoML training pipeline...', progress: 0 });
    setResults(null);
    setPredictionResult(null);

    try {
      const job = await startAutoML(projectId, targetCol, taskType === 'auto' ? null : taskType,{split_strategy:splitStrategy,group_column:splitStrategy==='grouped'?splitColumn:null,date_column:splitStrategy==='chronological'?splitColumn:null,holdout_fraction:holdoutFraction,...featureSettings});
      actions.setAutomlJob(job.job_id, projectId);
    } catch (err) {
      setIsTraining(false);
      setJobStatus({status:'failed', error:err.message});
      actions.setError(err.message, projectId);
    }
  };

  const handlePredict = async () => {
    if (!projectId) return;
    const runId = results?.run_id;
    setIsPredicting(true);
    setPredictionResult(null);
    actions.setError(null, projectId);
    try {
      const data = await predict(projectId, whatIfInputs);
      actions.setField('predictionResult', data, projectId, runId);
    } catch (err) {
      actions.setError(err.message, projectId);
    } finally {
      setIsPredicting(false);
    }
  };

  return (
    <div className="page-container automl-page" style={{ padding: '24px 32px' }}>
      <section className="card ws-panel"><h2>Feature settings</h2><p>{featureSettings.include_columns?featureSettings.include_columns.join(', '):'All eligible features'} · retain {featureSettings.selection_percentile}% of encoded features</p><button className="btn btn-secondary" onClick={()=>actions.setTab('features')}>Configure feature selection</button></section>{/* Header */}
      <div className="automl-header">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Cpu className="text-accent" size={24} />
            AutoML Engine & Algorithm Leaderboard
          </h1>
          <p className="text-sm text-secondary">
            Benchmark multiple ML models (XGBoost, LightGBM, CatBoost, Scikit-Learn) with Optuna hyperparameter optimization.
          </p>
        </div>

        {/* Configuration Bar */}
        <div className="automl-config">
          <label className="flex items-center gap-2">
            <span className="text-xs text-secondary font-medium">Target Column:</span>
            <select aria-label="Target column"
              value={targetCol}
              onChange={(e) => setTargetCol(e.target.value)}
              className="bg-card text-xs text-primary px-3 py-1.5 rounded border border-border"
              style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
            >
              {columns.length > 0 ? (
                columns.map((col) => (
                  <option key={col} value={col}>{col}</option>
                ))
              ) : (
                <option value="">No columns found</option>
              )}
            </select>
          </label>

          <select aria-label="Prediction task" value={taskType} onChange={(e) => setTaskType(e.target.value)}
            className="bg-card text-xs text-primary px-3 py-1.5 rounded border border-border">
            <option value="auto">Detect task</option>
            <option value="classification">Classification</option>
            <option value="regression">Regression</option>
          </select>
          <button
            onClick={handleStartAutoML}
            disabled={isTraining || state.analyzing || !projectId || !targetCol}
            className="flex items-center gap-2 px-4 py-2 rounded font-medium text-xs text-black"
            style={{
              background: isTraining ? 'var(--text-tertiary)' : 'var(--accent-green)',
              cursor: isTraining ? 'not-allowed' : 'pointer',
              boxShadow: '0 0 15px rgba(0, 255, 136, 0.3)',
              fontWeight: 600,
            }}
          >
            {isTraining ? <RefreshCw className="animate-spin" size={14} /> : <Play size={14} />}
            {isTraining ? 'Training Models...' : state.analyzing ? 'Waiting for analysis…' : 'Run AutoML Competition'}
          </button>
        </div>
      </div>

      <section className="card ws-panel" style={{marginBottom:20}}><h2>Evaluation setup</h2><div className="ws-form-grid"><label className="ws-field"><span>Split strategy</span><select aria-label="Split strategy" value={splitStrategy} onChange={e=>{setSplitStrategy(e.target.value);setSplitColumn('');}}><option value="random">Random</option><option value="grouped">Grouped · keep entities separate</option><option value="chronological">Chronological · future holdout</option></select></label>{splitStrategy!=='random'&&<label className="ws-field"><span>{splitStrategy==='grouped'?'Group column':'Date column'}</span><select aria-label="Split column" value={splitColumn} onChange={e=>setSplitColumn(e.target.value)}><option value="">Choose a column</option>{columns.filter(c=>c!==targetCol).map(c=><option key={c}>{c}</option>)}</select></label>}<label className="ws-field"><span>Holdout size</span><select aria-label="Holdout size" value={holdoutFraction} onChange={e=>setHoldoutFraction(Number(e.target.value))}><option value={.2}>20%</option><option value={.3}>30%</option><option value={.4}>40%</option></select></label></div><p className="ws-muted">The winner is selected with cross-validation. Group and date split columns are excluded from features. The final holdout is used once for evaluation.</p></section>
      {results&&<Evaluation result={results}/>}
      {state.analyzing && <p role="status" className="text-sm text-secondary mb-4">Dataset analysis is running. Model training will be available when it finishes.</p>}

      {/* Training In Progress Card */}
      {isTraining && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="card mb-6 p-4"
          style={{ background: 'rgba(0, 255, 136, 0.05)', border: '1px solid var(--accent-green-border)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-accent flex items-center gap-2">
              <Zap size={14} className="animate-pulse" />
              AutoML Optimization in Progress
            </span>
            <span className="text-xs text-secondary">{jobStatus?.progress ?? 0}%</span>
          </div>
          <div style={{ height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 4, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${jobStatus?.progress ?? 0}%`,
                background: 'var(--accent-green)',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <p className="text-xs text-secondary mt-2">
            {jobStatus?.current_step || 'Fitting baseline models and running cross-validation...'}
          </p>
        </motion.div>
      )}

      {/* Results Dashboard */}
      {results ? (
        <div>
          {/* Best Model Banner */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="card p-4 col-span-2" style={{ border: '1px solid var(--accent-green-border)' }}>
              <div className="flex items-center gap-2 mb-1">
                <Trophy size={18} style={{ color: '#ffd700' }} />
                <span className="text-xs font-semibold text-accent">Champion Model Selected</span>
              </div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                {results.best_model?.model_name}
              </h2>
              <p className="text-xs text-secondary mt-1">
                Task Type: <b className="text-primary">{results.task_type.toUpperCase()}</b> on target{' '}
                <code className="text-accent">{results.target_column}</code>
              </p>
              {results.optuna_tuning && (
                <div className="mt-2 text-xs text-secondary">
                  {results.optuna_tuning.applied
                    ? `Optuna tuning applied: ${results.optuna_tuning.optimization_trials} trials evaluated`
                    : `Baseline retained. ${results.optuna_tuning.reason || ''}`}
                </div>
              )}
            </div>

            <div className="card p-4 flex flex-col justify-between">
              <span className="text-xs text-secondary">Primary Score</span>
              <div className="text-2xl font-bold text-accent">
                {results.best_model?.primary_metric?.toFixed(4) || '—'}
              </div>
              <span className="text-xs text-secondary">
                {results.task_type === 'classification' ? 'Holdout F1 (Macro)' : 'Holdout R²'}
              </span>
            </div>

            <div className="card p-4 flex flex-col justify-between">
              <span className="text-xs text-secondary">Artifact Ready</span>
              <button
                onClick={async () => { try {await downloadModel(projectId);} catch (err) {actions.setError(err.message, projectId);}}}
                type="button"
                className="flex items-center justify-center gap-2 px-3 py-2 rounded text-xs font-medium text-black"
                style={{ background: 'var(--accent-green)', textDecoration: 'none' }}
              >
                <Download size={14} /> Download .joblib
              </button>
              <span className="text-xs text-secondary">Pretrained Scikit Pipeline</span>
            </div>
          </div>

          {/* Sub Navigation */}
          <div className="model-tabs flex items-center gap-4 mb-4 border-b border-border pb-2">
            {[
              { id: 'leaderboard', label: 'Model Leaderboard', icon: Trophy },
              { id: 'xai', label: 'Feature importance', icon: BarChart2 },
              { id: 'whatif', label: 'What-If Simulation', icon: Sliders },
            ].map(tab => (
              <button
                key={tab.id}
                aria-pressed={activeSubTab === tab.id}
                onClick={() => setActiveSubTab(tab.id)}
                className="flex items-center gap-2 text-xs font-medium pb-2 border-b-2"
                style={{
                  color: activeSubTab === tab.id ? 'var(--accent-green)' : 'var(--text-secondary)',
                  borderColor: activeSubTab === tab.id ? 'var(--accent-green)' : 'transparent',
                  background: 'none',
                  borderTop: 'none', borderLeft: 'none', borderRight: 'none',
                  cursor: 'pointer',
                }}
              >
                <tab.icon size={14} />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 1: Leaderboard Table */}
          {activeSubTab === 'leaderboard' && (
            <div className="card overflow-hidden">
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.8rem' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid var(--border-color)' }}>
                    <th style={{ padding: '10px 14px' }}>Rank</th>
                    <th style={{ padding: '10px 14px' }}>Model</th>
                    <th style={{ padding: '10px 14px' }}>Holdout Score</th>
                    <th style={{ padding: '10px 14px' }}>{results.cv_folds || '—'}-Fold CV {results.cv_metric === 'f1_macro' ? 'F1 (Macro)' : 'R²'} (Mean ± Std)</th>
                    {results.task_type === 'classification' ? (
                      <>
                        <th style={{ padding: '10px 14px' }}>Accuracy</th>
                        <th style={{ padding: '10px 14px' }}>Precision (Macro)</th>
                        <th style={{ padding: '10px 14px' }}>Recall (Macro)</th>
                      </>
                    ) : (
                      <>
                        <th style={{ padding: '10px 14px' }}>RMSE</th>
                        <th style={{ padding: '10px 14px' }}>MAE</th>
                        <th style={{ padding: '10px 14px' }}>MAPE</th>
                      </>
                    )}
                    <th style={{ padding: '10px 14px' }}>Train Time</th>
                  </tr>
                </thead>
                <tbody>
                  {results.leaderboard?.map((m, idx) => (
                    <tr
                      key={m.model_name}
                      style={{
                        borderBottom: '1px solid var(--border-color)',
                        background: idx === 0 ? 'rgba(0, 255, 136, 0.04)' : 'transparent',
                      }}
                    >
                      <td style={{ padding: '10px 14px' }}>
                        {idx === 0 ? <span className="text-accent font-bold">🥇 #1</span> : `#${idx + 1}`}
                      </td>
                      <td style={{ padding: '10px 14px', fontWeight: 600 }}>{m.model_name}</td>
                      <td style={{ padding: '10px 14px', color: 'var(--accent-green)', fontWeight: 'bold' }}>
                        {m.primary_metric?.toFixed(4) ?? '—'}
                      </td>
                      <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>
                        {m.cv_score_mean?.toFixed(4)} ± {m.cv_score_std?.toFixed(3)}
                      </td>
                      {results.task_type === 'classification' ? (
                        <>
                          <td style={{ padding: '10px 14px' }}>{m.accuracy != null ? `${(m.accuracy * 100).toFixed(1)}%` : '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{m.precision != null ? `${(m.precision * 100).toFixed(1)}%` : '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{m.recall != null ? `${(m.recall * 100).toFixed(1)}%` : '—'}</td>
                        </>
                      ) : (
                        <>
                          <td style={{ padding: '10px 14px' }}>{m.rmse?.toFixed(2) ?? '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{m.mae?.toFixed(2) ?? '—'}</td>
                          <td style={{ padding: '10px 14px' }}>{m.mape != null ? `${m.mape.toFixed(1)}%` : '—'}</td>
                        </>
                      )}
                      <td style={{ padding: '10px 14px', color: 'var(--text-secondary)' }}>
                        {m.training_time_sec}s
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeSubTab === 'leaderboard' && <p className="text-xs text-secondary mt-2">
            Ranked by training-fold validation. Only the selected winner is evaluated on the holdout set.
          </p>}
          {/* Tab 2: Explainable AI (SHAP) */}
          {activeSubTab === 'xai' && results.xai?.chart && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                Feature importance · {results.xai.method.replaceAll('_',' ')}
              </h3>
              <Plot
                data={results.xai.chart.data}
                layout={{
                  ...results.xai.chart.layout,
                  autosize: true,
                  height: 380,
                  paper_bgcolor: 'transparent',
                  plot_bgcolor: 'transparent',
                }}
                useResizeHandler
                style={{ width: '100%' }}
                config={{ displayModeBar: false }}
              />
              <div className="grid grid-cols-2 gap-3 mt-4">
                {results.xai.top_features?.slice(0, 4).map(item => (
                  <div
                    key={item.feature}
                    className="p-3 rounded"
                    style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)' }}
                  >
                    <div className="text-xs font-semibold text-accent">{item.feature}</div>
                    <div className="text-xs text-secondary mt-1">Importance score: {Number(item.importance_score).toFixed(4)}. {item.relative_percentage}% of the displayed importance total.</div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-secondary mt-4">Importance describes this model and evaluation sample. It does not measure causality or the percentage of predictions explained.</p>
            </div>
          )}

          {activeSubTab === 'xai' && !results.xai?.chart && <div className="card"><h3>Feature importance unavailable</h3><p className="text-sm text-secondary mt-2">{results.xai?.error || 'The selected model did not produce an explanation chart.'}</p></div>}

          {/* Tab 3: What-If Simulation Sandbox */}
          {activeSubTab === 'whatif' && (
            <div className="card p-5">
              <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
                Interactive What-If Simulation
              </h3>
              <p className="text-xs text-secondary mb-4">
                Adjust feature values below to query the champion model pipeline and see live predictions.
              </p>

              <div className="grid grid-cols-3 gap-4 mb-4">
                {(results.feature_columns || columns.filter(c => c !== results.target_column)).map(col => (
                  <div key={col}>
                    <label htmlFor={`feature-${col}`} className="text-xs text-secondary block mb-1">{col}</label>
                    <input
                      id={`feature-${col}`}
                      type="text"
                      placeholder="Enter value"
                      value={whatIfInputs[col] ?? ''}
                      onChange={(e) => setWhatIfInputs({ ...whatIfInputs, [col]: e.target.value })}
                      className="w-full text-xs px-3 py-1.5 rounded"
                      style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-4">
                <button
                  onClick={handlePredict}
                  disabled={isPredicting}
                  className="px-4 py-2 rounded text-xs font-semibold text-black"
                  style={{ background: 'var(--accent-green)' }}
                >
                  {isPredicting ? 'Evaluating...' : 'Run Simulation Prediction'}
                </button>

                {predictionResult && (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-secondary">Predicted Output:</span>
                    <span className="text-sm font-bold text-accent px-3 py-1 rounded" style={{ background: 'rgba(0,255,136,0.1)' }}>
                      {typeof predictionResult.predictions?.[0] === 'number' ? predictionResult.predictions[0].toLocaleString(undefined,{maximumFractionDigits:2}) : String(predictionResult.predictions?.[0])}
                    </span>
                  </div>
                )}
              </div>
              {predictionResult?.warnings?.length>0&&<p className="ws-notice" role="status">{predictionResult.warnings.join(' ')}</p>}
            </div>
          )}
        </div>
      ) : (
        /* Empty State */
        !isTraining && (
          <div className="card p-12 text-center" style={{ borderStyle: 'dashed' }}>
            <Cpu size={36} className="text-secondary mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-primary mb-1">No Model Benchmark Run Yet</h3>
            <p className="text-xs text-secondary mb-4 max-w-md mx-auto">
              Select your target column above and click "Run AutoML Competition" to automatically evaluate Logistic Regression, Random Forest, XGBoost, LightGBM, and CatBoost with Optuna tuning.
            </p>
          </div>
        )
      )}
    </div>
  );
}
