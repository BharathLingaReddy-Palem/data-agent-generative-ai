// Dataset-scoped state is kept above page navigation.
export const initialState = {
  projectId: null, datasetName: null, profile: null, datasetLoadId: null,
  jobId: null, jobStatus: null, jobProgress: 0, jobStep: '', analysis: null,
  activeTab: 'upload', uploading: false, profiling: false, analyzing: false, error: null,
  chatMessages: [], chatInput: '', chatLoading: false,
  forecastSettings: {date_column:'',target_column:'',horizon:12,season_length:12,frequency:'MS',aggregation:'mean',missing_policy:'reject'},
  textSettings: {text_column:'',target_column:''},
  automlSplit: 'random', automlSplitColumn: '', automlHoldout: .2,
  featureSettings: {include_columns:null,selection_percentile:100,compare_features:false},
  batchRunId:'',batchResult:null,workflowMeta:null,
  reportDraft: {title:'Dataset insights',organization:'',accent:'#287a65',context:'',commentary:'',chart_ids:[]},
  automlTarget: '', automlTask: 'auto', automlTraining: false, automlJobId: null,
  automlJobStatus: null, automlResults: null, automlTab: 'leaderboard',
  whatIfInputs: {}, predictionResult: null, isPredicting: false,
};

export function reducer(state, action) {
  // Reject late responses from datasets or runs that are no longer active.
  if (action.loadId && action.type !== 'BEGIN_LOAD' && action.loadId !== state.datasetLoadId) return state;
  if (action.projectId !== undefined && action.type !== 'SET_PROJECT' && action.projectId !== state.projectId) return state;
  if (action.modelRunId !== undefined && action.modelRunId !== state.automlResults?.run_id) return state;
  if (action.jobId && action.type !== 'SET_JOB' && action.type !== 'SET_AUTOML_JOB' &&
      action.jobId !== (action.automl ? state.automlJobId : state.jobId)) return state;
  switch (action.type) {
    case 'BEGIN_LOAD': return {...state, datasetLoadId:action.loadId};
    case 'RESTORE_FAILED': return state.datasetLoadId ? state : {...initialState, error:action.error};
    case 'SET_PROJECT':
      return action.projectId === state.projectId
        ? {...state, datasetName: action.datasetName, error: null}
        : {...initialState, activeTab: state.activeTab, datasetLoadId:state.datasetLoadId, projectId: action.projectId, datasetName: action.datasetName};
    case 'SET_PROFILE': return {...state, profile: action.profile, profiling: false};
    case 'SET_JOB': return {...state, jobId: action.jobId, jobStatus: 'queued', jobProgress: 0, jobStep: 'Queued', analyzing: true, analysis: null, error:null};
    case 'UPDATE_JOB': return {...state, jobStatus: action.status, jobProgress: action.progress, jobStep: action.step, analyzing: ['queued','running'].includes(action.status)};
    case 'SET_ANALYSIS': return {...state, analysis: action.analysis, jobStatus: 'completed', jobProgress: 100, analyzing: false, error:null};
    case 'SET_AUTOML_JOB': return {...state, automlJobId: action.jobId, automlTraining: true, automlResults: null, predictionResult:null, whatIfInputs:{}};
    case 'UPDATE_AUTOML_JOB': return {...state, automlJobStatus: action.status, automlTraining: ['queued','running'].includes(action.status.status)};
    case 'SET_AUTOML_RESULTS': return {...state, automlResults: action.result, automlTraining: false, predictionResult:null, whatIfInputs:{}};
    case 'SET_FIELD': return {...state, [action.key]: typeof action.value === 'function' ? action.value(state[action.key]) : action.value};
    case 'SELECT_SESSION':
    case 'RESTORE': {
      if (action.type === 'RESTORE' && state.datasetLoadId) return state;
      const data = action.data;
      const base = action.type === 'SELECT_SESSION'
        ? {...initialState, projectId:data.project_id, activeTab:'overview'} : state;
      const analysisJob = data.jobs?.analysis;
      const automlJob = data.jobs?.automl;
      const model=data.automl, setup=model?.settings||{};
      return {...base, datasetName: data.dataset_name, profile: data.profile, analysis: data.analysis,
        chatMessages: data.messages || [], automlResults: data.automl,
        ...(model ? {automlTarget:model.target_column||'',automlTask:setup.task_type||model.task_type||'auto',
          automlSplit:setup.split_strategy||model.evaluation?.split_strategy||'random',
          automlSplitColumn:setup.group_column||setup.date_column||'',automlHoldout:setup.holdout_fraction??.2,
          featureSettings:{include_columns:setup.include_columns??null,selection_percentile:setup.selection_percentile??100,compare_features:!!setup.compare_features}} : {}),
        jobId: analysisJob?.job_id || null, jobStatus: analysisJob?.status || null,
        jobProgress: analysisJob?.progress || 0, jobStep: analysisJob?.current_step || '',
        analyzing: ['queued','running'].includes(analysisJob?.status),
        automlJobId: automlJob?.job_id || null, automlJobStatus: automlJob || null,
        automlTraining: ['queued','running'].includes(automlJob?.status)};
    }
    case 'SET_TAB': return {...state, activeTab: action.tab};
    case 'SET_UPLOADING': return {...state, uploading: action.uploading};
    case 'SET_PROFILING': return {...state, profiling: action.profiling};
    case 'SET_ANALYZING': return {...state, analyzing: action.analyzing};
    case 'SET_ERROR': return {...state, error: action.error, uploading: false, profiling: false, analyzing: false};
    case 'RESET': return {...initialState};
    default: return state;
  }
}
