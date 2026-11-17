import assert from 'node:assert/strict';
import test from 'node:test';
import {submissionIntent,submitOnce,readPendingIntent,startDistinctIntent} from '../.submission-test/submissionIntent.js';
const map=new Map();
globalThis.localStorage={getItem:(key)=>map.get(key)??null,setItem:(key,val)=>map.set(key,val),removeItem:(key)=>map.delete(key)};
const notFound={status:404};
test('same payload creates one shared intent across two browser tabs',async()=>{
  map.clear();
  const payload={document_id:'random-document-id',settings:{provider:'ollama',unified:false}};
  const [a,b]=await Promise.all([submissionIntent('ws','jd_extract',payload),submissionIntent('ws','jd_extract',payload)]);
  assert.equal(a.key,b.key);
  assert.ok(/^ui-[a-f0-9]{64}$/.test(a.key));
  assert.doesNotMatch(JSON.stringify([...map.values()]),/random-document-id|ollama/);
});
test('lost response is recovered using GET without a second POST',async()=>{
  map.clear();let accepted=null;let sends=0;
  const lookup=async()=>{if(!accepted)throw notFound;return accepted};
  const submit=async()=>{sends++;accepted={id:'only-one-job'};throw new Error('Connection terminated after acceptance')};
  const first=await submitOnce('ws','assess',{candidate_ids:['random-uuid']},lookup,submit);
  assert.equal(first.id,'only-one-job');
  assert.equal(sends,1);
  const second=await submitOnce('ws','assess',{candidate_ids:['random-uuid']},lookup,submit);
  assert.equal(second.id,first.id);
  assert.equal(sends,1);
  assert.equal(readPendingIntent('ws','assess').state,'accepted');
});
test('independent run requires explicit action, changed request gets distinct fingerprint',async()=>{
  map.clear();
  const a=await submissionIntent('ws','assess',{candidate_ids:['A']});
  const b=await submissionIntent('ws','assess',{candidate_ids:['B']});
  assert.notEqual(a.key,b.key);
  startDistinctIntent('ws','assess');
  const c=await submissionIntent('ws','assess',{candidate_ids:['A']});
  assert.notEqual(a.key,c.key);
});
test('ambiguous submission lookup failure does not dispatch another operation',async()=>{
  map.clear();let sent=0;
  await assert.rejects(submitOnce('ws','assess',{x:1},async()=>{throw new Error('offline')},async()=>{sent++;return {id:'not-expected'}}));
  assert.equal(sent,0);
  assert.equal(readPendingIntent('ws','assess').state,'pending');
});
