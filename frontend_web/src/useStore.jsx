import { createContext, useContext, useReducer, useMemo, useEffect, useRef } from 'react';
import { initialState, reducer } from './storeState';
import { pollJobUntilDone, restoreProject } from './api';
const StoreContext = createContext(null);

function loadSelection() {
  try {
    const selected = JSON.parse(sessionStorage.getItem('ds_project') || 'null');
    return selected?.projectId ? {...initialState, ...selected, activeTab: 'overview'} : initialState;
  } catch { return initialState; }
}

export function StoreProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, undefined, loadSelection);
  const restoring = useRef(state.projectId);
  const actions = useMemo(() => ({
    beginLoad: () => {const loadId = crypto.randomUUID(); dispatch({type:'BEGIN_LOAD', loadId}); return loadId;},
    setProject: (projectId, datasetName, loadId) => dispatch({type:'SET_PROJECT', projectId, datasetName, loadId}),
    setProfile: (profile, projectId=profile.project_id, loadId) => dispatch({type:'SET_PROFILE', profile, projectId, loadId}),
    setJob: (jobId, projectId) => dispatch({type:'SET_JOB', jobId, projectId}),
    updateJob: (status, progress, step, projectId, jobId) => dispatch({type:'UPDATE_JOB', status, progress, step, projectId, jobId}),
    setAnalysis: (analysis, projectId=analysis.project_id, jobId) => dispatch({type:'SET_ANALYSIS', analysis, projectId, jobId}),
    setAutomlJob: (jobId, projectId) => dispatch({type:'SET_AUTOML_JOB', jobId, projectId}),
    setField: (key, value, projectId, modelRunId) => dispatch({type:'SET_FIELD', key, value, projectId, modelRunId}),
    setTab: (tab, projectId, loadId) => dispatch({type:'SET_TAB', tab, projectId, loadId}),
    setUploading: (uploading, loadId) => dispatch({type:'SET_UPLOADING', uploading, loadId}),
    setProfiling: (profiling, loadId) => dispatch({type:'SET_PROFILING', profiling, loadId}),
    setAnalyzing: (analyzing, projectId) => dispatch({type:'SET_ANALYZING', analyzing, projectId}),
    setError: (error, projectId, loadId) => dispatch({type:'SET_ERROR', error, projectId, loadId}),
    reset: () => dispatch({type:'RESET'}),
    selectSavedProject: (data, loadId) => dispatch({type:'SELECT_SESSION', data, loadId}),
  }), []);

  useEffect(() => {
    if (state.projectId) sessionStorage.setItem('ds_project', JSON.stringify({projectId:state.projectId, datasetName:state.datasetName}));
    else sessionStorage.removeItem('ds_project');
  }, [state.projectId, state.datasetName]);

  useEffect(() => {
    const projectId = restoring.current;
    if (!projectId) return;
    const controller = new AbortController();
    restoreProject(projectId, controller.signal)
      .then(data => { restoring.current = null; dispatch({type:'RESTORE', projectId, data}); })
      .catch(error => { if (!controller.signal.aborted) { restoring.current = null; dispatch({type:'RESTORE_FAILED', projectId, error:error.message}); } });
    return () => controller.abort();
  }, [actions]);

  useEffect(() => {
    if (!state.projectId || !state.jobId || !['queued','running'].includes(state.jobStatus)) return;
    const controller = new AbortController();
    const projectId = state.projectId, jobId = state.jobId;
    pollJobUntilDone(jobId, status => actions.updateJob(status.status, status.progress, status.current_step, projectId, jobId), 1500, controller.signal)
      .then(result => actions.setAnalysis(result, projectId, jobId))
      .catch(error => {
        if (!controller.signal.aborted) {
          actions.updateJob('failed', 0, error.message, projectId, jobId);
          actions.setError(error.message, projectId);
        }
      });
    return () => controller.abort();
  }, [state.projectId, state.jobId, actions]);

  useEffect(() => {
    if (!state.projectId || !state.automlJobId || !state.automlTraining) return;
    const controller = new AbortController();
    const projectId = state.projectId, jobId = state.automlJobId;
    pollJobUntilDone(jobId, status => dispatch({type:'UPDATE_AUTOML_JOB', projectId, jobId, automl:true, status}), 1500, controller.signal)
      .then(result => dispatch({type:'SET_AUTOML_RESULTS', projectId, jobId, automl:true, result}))
      .catch(error => {
        if (!controller.signal.aborted) {
          dispatch({type:'UPDATE_AUTOML_JOB', projectId, jobId, automl:true, status:{status:'failed', error:error.message}});
          actions.setError(error.message, projectId);
        }
      });
    return () => controller.abort();
  }, [state.projectId, state.automlJobId, actions]);

  return <StoreContext.Provider value={{state, actions}}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const value = useContext(StoreContext);
  if (!value) throw new Error('useStore must be used within StoreProvider');
  return value;
}

export function useProjectState(key) {
  const {state, actions} = useStore();
  const projectId = state.projectId;
  return [state[key], value => actions.setField(key, value, projectId)];
}
