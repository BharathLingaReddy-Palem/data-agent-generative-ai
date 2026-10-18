import test from 'node:test';
import assert from 'node:assert/strict';
import {initialState, reducer} from '../src/storeState.js';
import {boxTraces, distributionTrace} from '../src/chartData.js';

test('simulation predictions follow the fitted artifact and reject late results from older models', () => {
  const state={...initialState,projectId:'one',automlResults:{run_id:'old'},predictionResult:{predictions:['yes']},whatIfInputs:{segment:'A'}};
  assert.deepEqual(reducer(state,{type:'SET_TAB',tab:'runs'}).predictionResult,state.predictionResult);
  const started=reducer(state,{type:'SET_AUTOML_JOB',projectId:'one',jobId:'new-job'});
  assert.equal(started.predictionResult,null);
  assert.deepEqual(started.whatIfInputs,{});
  const completed=reducer(started,{type:'SET_AUTOML_RESULTS',automl:true,projectId:'one',jobId:'new-job',result:{run_id:'new'}});
  const late={type:'SET_FIELD',projectId:'one',key:'predictionResult',value:{predictions:['yes']},modelRunId:'old'};
  assert.equal(reducer(completed,late),completed);
  assert.deepEqual(reducer(completed,{...late,modelRunId:'new',value:{predictions:[2.5]}}).predictionResult,{predictions:[2.5]});
});

test('model settings and report drafts survive navigation but never cross dataset boundaries', () => {
  let state={...initialState,projectId:'first'};
  for (const [key,value] of Object.entries({textSettings:{text_column:'body',target_column:'label'},
      forecastSettings:{date_column:'date',target_column:'sales',horizon:6},automlSplit:'grouped',automlSplitColumn:'customer',
      reportDraft:{title:'Board review',commentary:'Private draft',chart_ids:['missing']}})) {
    state=reducer(state,{type:'SET_FIELD',projectId:'first',key,value});
  }
  const next=reducer(state,{type:'SET_TAB',tab:'history'});
  for (const key of ['textSettings','forecastSettings','automlSplit','automlSplitColumn','reportDraft']) assert.deepEqual(next[key],state[key]);
  const changed=reducer(next,{type:'SELECT_SESSION',data:{project_id:'second',profile:{},dataset_name:'Second'}});
  assert.equal(changed.textSettings.target_column,'');
  assert.equal(changed.forecastSettings.target_column,'');
  assert.equal(changed.reportDraft.commentary,'');
  assert.equal(changed.automlSplit,'random');
  assert.equal(reducer(changed,{type:'SET_FIELD',projectId:'first',key:'textSettings',value:{stale:true}}),changed);
});

test('saved dataset selection restores only that dataset and rejects stale selection responses', () => {
  const state = {...initialState, projectId:'old', datasetLoadId:'new-load', chatInput:'old draft', predictionResult:{old:true}};
  const action = {type:'SELECT_SESSION', loadId:'new-load', data:{project_id:'saved',dataset_name:'Saved',profile:{rows:2000},messages:['saved message'],automl:{model:'Ridge'}}};
  assert.equal(reducer(state,{...action,loadId:'stale'}),state);
  const selected = reducer(state,action);
  assert.equal(selected.projectId,'saved');
  assert.equal(selected.chatInput,'');
  assert.equal(selected.predictionResult,null);
  assert.deepEqual(selected.chatMessages,['saved message']);
  assert.equal(selected.automlResults.model,'Ridge');
});

test('changing datasets clears all derived state and rejects late responses', () => {
  const old = {...initialState, projectId:'old', profile:{rows:10}, analysis:{old:true},
    chatMessages:[{content:'hello'}], automlResults:{model:'old'}, automlJobId:'old-job', predictionResult:{value:1}};
  const state = reducer(old, {type:'SET_PROJECT', projectId:'new', datasetName:'New'});
  for (const key of ['profile','analysis','automlResults','automlJobId','predictionResult']) assert.equal(state[key], null);
  assert.deepEqual(state.chatMessages, []);
  assert.equal(reducer(state, {type:'SET_ANALYSIS', projectId:'old', analysis:{stale:true}}), state);
  assert.equal(reducer(state, {type:'SET_FIELD', projectId:'old', key:'chatMessages', value:['late']}), state);
});

test('page navigation preserves chat and AutoML state including pending work', () => {
  const state = {...initialState, projectId:'one', chatMessages:['hello'], chatInput:'draft', automlResults:{model:'winner'}, automlTraining:true, automlJobId:'job'};
  const navigated = reducer(state, {type:'SET_TAB', tab:'overview'});
  for (const key of ['chatMessages','chatInput','automlResults','automlTraining','automlJobId']) assert.deepEqual(navigated[key], state[key]);
});

test('older jobs and uploads cannot overwrite a newer selection', () => {
  let state = {...initialState, projectId:'one', jobId:'latest', automlJobId:'latest-ml'};
  assert.equal(reducer(state,{type:'SET_ANALYSIS', projectId:'one', jobId:'old', analysis:{}}),state);
  assert.equal(reducer(state,{type:'SET_AUTOML_RESULTS', projectId:'one', jobId:'old', automl:true, result:{}}),state);
  state = reducer(state,{type:'BEGIN_LOAD', loadId:'new-upload'});
  assert.equal(reducer(state,{type:'SET_PROJECT', projectId:'late', loadId:'old-upload'}),state);
  assert.equal(reducer(state,{type:'RESTORE', projectId:'one', data:{profile:{old:true}}}),state);
  state = reducer(state,{type:'SET_PROJECT', projectId:'new', loadId:'new-upload'});
  assert.equal(state.projectId,'new');
});

test('restoring a session restores results, messages, and active job polling', () => {
  const state = reducer({...initialState, projectId:'one'}, {type:'RESTORE',projectId:'one',data:{
    profile:{rows:600}, analysis:{complete:true}, messages:['saved'], automl:{model:'winner'},
    jobs:{analysis:{job_id:'analysis',status:'running',progress:48,current_step:'Running trend'}, automl:{job_id:'ml',status:'queued'}}}});
  assert.deepEqual(state.chatMessages,['saved']);
  assert.equal(state.automlResults.model,'winner');
  assert.equal(state.jobProgress,48);
  assert.equal(state.analyzing,true);
  assert.equal(state.automlTraining,true);
});

test('restored AutoML form uses the saved target, split and feature settings', () => {
  const state=reducer(initialState,{type:'SELECT_SESSION',data:{project_id:'p',dataset_name:'Fixture',automl:{
    run_id:'saved',target_column:'outcome',task_type:'regression',settings:{split_strategy:'chronological',date_column:'date',holdout_fraction:.3,include_columns:['amount'],selection_percentile:75,compare_features:true}}}});
  assert.equal(state.automlTarget,'outcome');assert.equal(state.automlTask,'regression');
  assert.equal(state.automlSplit,'chronological');assert.equal(state.automlSplitColumn,'date');assert.equal(state.automlHoldout,.3);
  assert.deepEqual(state.featureSettings,{include_columns:['amount'],selection_percentile:75,compare_features:true});
});

test('box plots consume explicit quartiles and observed whiskers including zero', () => {
  const [trace] = boxTraces(['sales'], {sales:{distribution:{box_summary:{q1:0,median:0,q3:3,lower_whisker:0,upper_whisker:4}}}});
  assert.deepEqual(trace.q1,[0]); assert.deepEqual(trace.median,[0]); assert.deepEqual(trace.upperfence,[4]);
  assert.equal(trace.y,undefined);
  assert.deepEqual(boxTraces(['sales'],{sales:{distribution:{percentiles:{p25:0,p50:1,p75:3}}}}),[]);
});

test('quantile fallback is a percentile curve, while histogram uses real counts', () => {
  const trace = distributionTrace({percentiles:{p90:10,p0:0,p50:3}},'sales');
  assert.equal(trace.type,'scatter'); assert.deepEqual(trace.x,[0,50,90]); assert.deepEqual(trace.y,[0,3,10]);
  const histogram = distributionTrace({histogram:{bin_centers:[1,2],counts:[20,40]}},'sales');
  assert.equal(histogram.type,'bar'); assert.deepEqual(histogram.y,[20,40]);
});

test('feature settings, batch previews and version indicators cannot survive a dataset/version switch', () => {
  const old={...initialState,projectId:'project',featureSettings:{include_columns:['private'],selection_percentile:50},batchRunId:'run',batchResult:{preview:['private']},workflowMeta:{version_number:2}};
  const navigated=reducer(old,{type:'SET_TAB',tab:'runs'});
  assert.equal(navigated.batchResult,old.batchResult);
  const versionChanged=reducer(navigated,{type:'SELECT_SESSION',data:{project_id:'project',dataset_name:'Updated',profile:{},active_version_id:'v3'}});
  assert.equal(versionChanged.batchResult,null);assert.equal(versionChanged.batchRunId,'');assert.equal(versionChanged.featureSettings.include_columns,null);assert.equal(versionChanged.workflowMeta,null);
  const other=reducer(old,{type:'SET_PROJECT',projectId:'other',datasetName:'Other'});
  assert.equal(reducer(other,{type:'SET_FIELD',projectId:'project',key:'workflowMeta',value:{version_number:99}}),other);
});
