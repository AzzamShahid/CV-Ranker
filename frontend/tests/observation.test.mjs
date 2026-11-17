import assert from 'node:assert/strict';
import test from 'node:test';
import {consumeSequence,isTerminalJob,newerSnapshot,nextReconnectMs} from '../.observation-test/observation.js';
test('duplicate and out of order events are ignored',()=>{
  assert.equal(consumeSequence(4,4),null);
  assert.equal(consumeSequence(4,3),null);
  assert.equal(consumeSequence(4,5),5);
  assert.equal(consumeSequence(4,NaN),null);
});
test('snapshots never regress',()=>{
 const a={id:'job',sequence:6,result_revision:3,state:'running'};
 assert.equal(newerSnapshot(a,{...a,sequence:5}),a);
 assert.equal(newerSnapshot(a,{...a,result_revision:2}),a);
 assert.equal(newerSnapshot(a,{...a,sequence:7}).sequence,7);
});
test('terminal states settle and reconnect backoff bounded',()=>{
 assert.equal(isTerminalJob('completed'),true);
 assert.equal(isTerminalJob('paused'),false);
 assert.equal(nextReconnectMs(0),1000);
 assert.equal(nextReconnectMs(50),30000);
});
