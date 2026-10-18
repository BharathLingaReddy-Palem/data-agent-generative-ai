import test from 'node:test';
import assert from 'node:assert/strict';
import {downloadReport} from '../src/api.js';

test('report downloads send the bearer token and save the correct format',async () => {
  const original={fetch:globalThis.fetch,sessionStorage:globalThis.sessionStorage,document:globalThis.document,
    create:URL.createObjectURL,revoke:URL.revokeObjectURL};
  let clicked=0,removed=0;
  globalThis.sessionStorage={getItem:()=> 'private-session'};
  globalThis.document={body:{appendChild:()=>{}},createElement:()=>({click(){clicked++;},remove(){removed++;}})};
  URL.createObjectURL=()=> 'blob:test';URL.revokeObjectURL=()=>{};
  try {
    for (const format of ['pdf','pptx']) {
      globalThis.fetch=async (url,options)=>{
        assert.equal(url,`/api/reports/project/${format}/download`);
        assert.equal(options.headers.get('Authorization'),'Bearer private-session');
        return {ok:true,status:200,blob:async()=>new Blob(['report'])};
      };
      await downloadReport('project',format);
    }
    globalThis.fetch=async()=>({ok:false,status:404,json:async()=>({detail:'Report not generated.'})});
    await assert.rejects(downloadReport('project','pdf'),/Report not generated/);
    assert.equal(clicked,2);assert.equal(removed,2);
    await assert.rejects(downloadReport('project','zip'),/Unsupported report format/);
  } finally {
    globalThis.fetch=original.fetch;globalThis.sessionStorage=original.sessionStorage;globalThis.document=original.document;
    URL.createObjectURL=original.create;URL.revokeObjectURL=original.revoke;
  }
});
