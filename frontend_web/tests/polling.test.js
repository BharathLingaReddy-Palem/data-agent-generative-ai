import test from 'node:test';
import assert from 'node:assert/strict';
import {pollJobUntilDone} from '../src/api.js';

test('job polling recovers transient status and result failures but preserves authorization errors', async () => {
  const original={fetch:globalThis.fetch, storage:globalThis.sessionStorage};
  globalThis.sessionStorage={getItem:()=>null};
  const response=(value,status=200)=>({ok:status===200,status,json:async()=>value});
  let calls=0;
  try {
    globalThis.fetch=async()=>{
      calls++;
      if(calls===1 || calls===3) throw new TypeError('Failed to fetch');
      return response(calls===5 ? {answer:42} : {status:'completed'});
    };
    assert.deepEqual(await pollJobUntilDone('job',null,1),{answer:42});
    assert.equal(calls,5);
    calls=0;
    globalThis.fetch=async()=>{calls++;return response({detail:'Forbidden'},403);};
    await assert.rejects(pollJobUntilDone('job',null,1),/Forbidden/);
    assert.equal(calls,1);
    globalThis.fetch=async()=>{throw new TypeError('Offline');};
    await assert.rejects(pollJobUntilDone('job',null,1),/Offline/);
  } finally {globalThis.fetch=original.fetch;globalThis.sessionStorage=original.storage;}
});
