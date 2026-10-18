import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {authorizedFetch, setToken} from '../src/api.js';

test('versioned workflows and split settings share the configured authenticated API', async () => {
  const source=(await readFile(new URL('../src/api.js',import.meta.url),'utf8')).replace('import.meta.env?.VITE_API_URL',JSON.stringify('https://workspace.example'));
  const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const priorFetch=globalThis.fetch,priorStorage=globalThis.sessionStorage,calls=[];
  globalThis.sessionStorage={getItem:()=> 'workspace-token'};
  globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({ok:true})};};
  try {
    const split={split_strategy:'chronological',date_column:'date',holdout_fraction:.3};
    await api.startAutoML('p','sales','regression',split);
    await api.workspaceRequest('p','/clean/preview',{plan:{remove_duplicates:true},revision:2});
    await api.workspaceRequest('p','/models/text/start',{settings:{text_column:'body',target_column:'label'}});
    await api.saveReportTemplate('Template',{title:'Report'});
    assert.deepEqual(calls.map(c=>c.url),['https://workspace.example/api/automl/start','https://workspace.example/api/workspace/p/clean/preview','https://workspace.example/api/workspace/p/models/text/start','https://workspace.example/api/report-templates']);
    assert.ok(calls.every(c=>c.options.headers.get('Authorization')==='Bearer workspace-token'));
    const body=JSON.parse(calls[0].options.body);
    assert.equal(body.split_strategy,'chronological');assert.equal(body.date_column,'date');assert.equal(body.holdout_fraction,.3);
  } finally {globalThis.fetch=priorFetch;globalThis.sessionStorage=priorStorage;}
});

test('sign-out and expired sessions clear the previous account dataset selection', async () => {
  const originalStorage = globalThis.sessionStorage;
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const values = new Map();
  let signedOut = false;
  globalThis.sessionStorage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  globalThis.window = {dispatchEvent: event => {signedOut = event.type === 'ds_signed_out';}};
  globalThis.fetch = async () => ({status:401});
  try {
    for (const expired of [false, true]) {
      setToken('test-token');
      values.set('ds_project', 'previous-account-project');
      if (expired) await authorizedFetch('/api/auth/me');
      else setToken(null);
      assert.equal(values.has('ds_access_token'), false);
      assert.equal(values.has('ds_project'), false);
    }
    assert.equal(signedOut, true);
  } finally {
    globalThis.sessionStorage = originalStorage;
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
  }
});

test('training, prediction and polling use the configured backend and bearer token', async () => {
  const source = (await readFile(new URL('../src/api.js', import.meta.url),'utf8'))
    .replace('import.meta.env?.VITE_API_URL', JSON.stringify('https://backend.example/'));
  const api = await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const originalFetch = globalThis.fetch, originalStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.sessionStorage = {getItem:()=> 'token'};
  globalThis.fetch = async (url, options) => {
    calls.push({url,options});
    return {ok:true, status:200,json:async()=>url.endsWith('/status')?{status:'completed'}:{value:1}};
  };
  try {
    await api.startAutoML('project','target','classification');
    await api.predict('project',{sales:10});
    await api.pollJobUntilDone('job',()=>{},1,new AbortController().signal);
    assert.deepEqual(calls.map(c=>c.url),[
      'https://backend.example/api/automl/start', 'https://backend.example/api/predict',
      'https://backend.example/api/job/job/status', 'https://backend.example/api/job/job/result']);
    assert.ok(calls.every(c=>c.options.headers.get('Authorization')==='Bearer token'));
    assert.equal(JSON.parse(calls[0].options.body).target_column,'target');
    const controller = new AbortController(); controller.abort();
    await assert.rejects(api.pollJobUntilDone('job',null,1,controller.signal),{name:'AbortError'});
    assert.equal(calls.length,4);
  } finally {globalThis.fetch=originalFetch; globalThis.sessionStorage=originalStorage;}
});

test('batch uploads and reusable recipes use configured authentication and preserve multipart boundaries', async () => {
  const source=(await readFile(new URL('../src/api.js',import.meta.url),'utf8')).replace('import.meta.env?.VITE_API_URL',JSON.stringify('https://backend.example/'));
  const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
  const oldFetch=globalThis.fetch,oldStorage=globalThis.sessionStorage;const calls=[];
  globalThis.sessionStorage={getItem:()=> 'test-token'};
  globalThis.fetch=async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({batch_id:'saved'})};};
  try {
    const file=new Blob(['feature\n1\n'],{type:'text/csv'});
    await api.batchPredict('project','run',file,.7,'yes');
    await api.saveCleaningRecipe('Reusable',{missing:{feature:{strategy:'constant',value:0}}});
    assert.equal(calls[0].url,'https://backend.example/api/workspace/project/runs/run/batch');
    assert.equal(calls[0].options.headers.get('Authorization'),'Bearer test-token');
    assert.equal(calls[0].options.headers.has('Content-Type'),false);
    assert.equal(calls[0].options.body.get('threshold'),'0.7');
    assert.equal(calls[0].options.body.get('positive_label'),'yes');
    assert.equal(calls[1].url,'https://backend.example/api/cleaning-recipes');
    assert.equal(JSON.parse(calls[1].options.body).plan.missing.feature.value,0);
  } finally {globalThis.fetch=oldFetch;globalThis.sessionStorage=oldStorage;}
});
