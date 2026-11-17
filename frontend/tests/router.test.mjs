import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseWorkspaceRoute,workspacePath } from '../.route-test/router.js';

const workspace='57b64bc8a66f4a13b61abf1d2c4e9817';
const job='a35f1a2b3b924ef1889b';
const candidate='e212a0b0a3144cd9bd72';

test('candidate deep link survives parsed route and reserialization',()=>{
  const path=`/w/${workspace}/candidate/${job}/${candidate}`;
  assert.deepEqual(parseWorkspaceRoute(path),{
    kind:'workspace',workspaceId:workspace,page:'candidate',jobId:job,candidateId:candidate
  });
  assert.equal(workspacePath(workspace,'candidate',{jobId:job,candidateId:candidate}),path);
});
test('job progress and ranking are distinct, refreshable routes',()=>{
  for(const page of ['progress','rankings']) {
    const path=workspacePath(workspace,page,{jobId:job});
    assert.deepEqual(parseWorkspaceRoute(path),{
      kind:'workspace',workspaceId:workspace,page,jobId:job,candidateId:undefined
    });
  }
});
test('unknown, malformed or incomplete resource route never resolves overview',()=>{
  for(const bad of ['/w/'+workspace+'/candidate/'+job,'/w/'+workspace+'/candidate/'+job+'/'+candidate+'/unexpected',
    '/w/'+workspace+'/unrecognized','/api/v1/jobs','/w/not@valid/overview','/w/'+workspace+'/progress']) {
    assert.deepEqual(parseWorkspaceRoute(bad),{kind:'not-found'},bad);
  }
});
test('standard navigation routes have stable human-accessible URLs',()=>{
  for(const page of ['overview','uploads','jd','weights','run','reports','settings']) {
    const path=workspacePath(workspace,page);
    const parsed=parseWorkspaceRoute(path);
    assert.equal(parsed.kind,'workspace');
    assert.equal(parsed.page,page);
  }
  assert.deepEqual(parseWorkspaceRoute('/'),{kind:'workspaces'});
});
test('legacy direct overview URL remains supported',()=>{
  assert.equal(parseWorkspaceRoute(`/w/${workspace}/overview`).page,'overview');
});
