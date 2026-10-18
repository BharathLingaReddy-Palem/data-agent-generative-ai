// api.js — Centralized API client
// All backend calls go through here for easy base URL switching

const BASE_URL = (import.meta.env?.VITE_API_URL || '').replace(/\/+$/, '');

export function setToken(token) {
  if (token) sessionStorage.setItem('ds_access_token', token);
  else {
    sessionStorage.removeItem('ds_access_token');
    sessionStorage.removeItem('ds_project');
  }
}

export async function authorizedFetch(path, options = {}) {
  const token = sessionStorage.getItem('ds_access_token');
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (res.status === 401 && token) {
    setToken(null);
    window.dispatchEvent(new Event('ds_signed_out'));
  }
  return res;
}

export async function downloadModel(projectId) {
  const res = await authorizedFetch(`/api/models/${projectId}/download`);
  if (!res.ok) throw new Error('Model download failed.');
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `model_${projectId}.joblib`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function downloadReport(projectId, format) {
  if (!['pdf','pptx'].includes(format)) throw new Error('Unsupported report format.');
  const res = await authorizedFetch(`/api/reports/${projectId}/${format}/download`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Report download failed.');
  }
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement('a');
  link.href = url;
  link.download = `executive_report_${projectId}.${format}`;
  document.body.appendChild(link);
  try {link.click();} finally {link.remove(); URL.revokeObjectURL(url);}
}

export const login = (username, password) => request('/api/auth/login', {method:'POST',body:JSON.stringify({username,password})});
export const register = (username, password) => request('/api/auth/register', {method:'POST',body:JSON.stringify({username,password})});
export const getAccount = () => request('/api/auth/me');
export const logout = () => request('/api/auth/logout', {method:'POST'});

async function request(path, options = {}) {
  const res = await authorizedFetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw Object.assign(new Error(err.detail || `HTTP ${res.status}`), {status:res.status});
  }
  return res.json();
}

// ── Profile (deterministic, instant) ──────────────────────
export async function profileDataset(file) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await authorizedFetch('/api/profile', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Upload ─────────────────────────────────────────────────
export async function uploadDataset(file, userQuestion = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (userQuestion) formData.append('user_question', userQuestion);
  const res = await authorizedFetch('/api/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Start Analysis Job (background) ────────────────────────
export async function startAnalysisJob(projectId, userQuestion = null) {
  return request('/api/analyze/start', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, user_question: userQuestion }),
  });
}

// ── Poll Job Status ────────────────────────────────────────
export async function getJobStatus(jobId, signal) {
  return request(`/api/job/${jobId}/status`, {signal});
}

// ── Get Job Result ─────────────────────────────────────────
export async function getJobResult(jobId, signal) {
  return request(`/api/job/${jobId}/result`, {signal});
}

// ── Chat ───────────────────────────────────────────────────
export async function sendChatMessage(projectId, message) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, message }),
  });
}

// ── Load Sample ────────────────────────────────────────────
export async function loadSampleDataset(sampleId) {
  const formData = new FormData();
  formData.append('sample_id', sampleId);
  const res = await authorizedFetch('/api/load-sample', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) throw new Error('Failed to load sample');
  return res.json();
}

// ── Key Health ─────────────────────────────────────────────
export async function getKeyHealth() {
  return request('/api/keys/health');
}

export const restoreProject = (projectId, signal) => request(`/api/projects/${projectId}/session`, {signal});
export const listProjects = () => request('/api/projects');
export const startAutoML = (projectId, targetColumn, taskType=null, evaluation={}) => request('/api/automl/start', {
  method:'POST', body:JSON.stringify({project_id:projectId, target_column:targetColumn || null, task_type:taskType, run_tuning:true,...evaluation})
});
export const workspaceRequest = (projectId, suffix='', payload, signal) => request(`/api/workspace/${projectId}${suffix}`,payload===undefined ? {signal} : {method:'POST',body:JSON.stringify(payload),signal});
export const reportTemplates = () => request('/api/report-templates');
export const cleaningRecipes = () => request('/api/cleaning-recipes');
export const saveCleaningRecipe = (name,plan) => request('/api/cleaning-recipes',{method:'POST',body:JSON.stringify({name,plan})});
export async function batchPredict(projectId,runId,file,threshold,positiveLabel) {
  const body=new FormData();body.append('file',file);
  if(threshold!==null&&threshold!==undefined){body.append('threshold',threshold);body.append('positive_label',positiveLabel);}
  const res=await authorizedFetch(`/api/workspace/${projectId}/runs/${runId}/batch`,{method:'POST',body});
  if(!res.ok){const err=await res.json().catch(()=>({}));throw new Error(err.detail||'Batch prediction failed.');}
  return res.json();
}
export const saveReportTemplate = (name,settings) => request('/api/report-templates',{method:'POST',body:JSON.stringify({name,settings})});
export async function downloadWorkspaceFile(projectId,path,filename,data) {
  const res=await authorizedFetch(`/api/workspace/${projectId}${path}`,data===undefined?undefined:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if (!res.ok) {const err=await res.json().catch(()=>({}));throw new Error(err.detail || 'Download unavailable.');}
  const url=URL.createObjectURL(await res.blob());const link=document.createElement('a');
  link.href=url;link.download=filename;document.body.appendChild(link);
  try {link.click();} finally {link.remove();URL.revokeObjectURL(url);}
}
export const predict = (projectId, inputData) => request('/api/predict', {
  method:'POST', body:JSON.stringify({project_id:projectId, input_data:inputData})
});

// Polling belongs to the provider and is canceled on dataset changes/unmount.
export async function pollJobUntilDone(jobId, onProgress, intervalMs=1500, signal) {
  let transientFailures = 0;
  while (true) {
    signal?.throwIfAborted();
    try {
      const status = await getJobStatus(jobId, signal);
      if (onProgress) onProgress(status);
      if (status.status === 'completed') return await getJobResult(jobId, signal);
      if (status.status === 'failed') throw new Error(status.error || 'Job failed');
      transientFailures = 0;
    } catch (error) {
      signal?.throwIfAborted();
      const transient = error instanceof TypeError || error.status >= 500;
      if (!transient || ++transientFailures > 3) throw error;
    }
    await new Promise((resolve, reject) => {
      if (signal?.aborted) {reject(signal.reason || new DOMException('Aborted','AbortError')); return;}
      const cancel = () => {clearTimeout(timer); reject(signal.reason || new DOMException('Aborted','AbortError'));};
      const timer = setTimeout(() => {signal?.removeEventListener('abort', cancel); resolve();}, intervalMs);
      signal?.addEventListener('abort', cancel, {once:true});
    });
  }
}
