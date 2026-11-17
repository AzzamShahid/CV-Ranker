import assert from 'node:assert/strict';
import test from 'node:test';
import {parseMinimumYears} from '../.jdyears-test/jdYears.js';
test('DA021-02 null, omitted, zero, integer and decimal years',()=>{
  assert.equal(parseMinimumYears(''),null);
  assert.equal(parseMinimumYears('   '),null);
  assert.equal(parseMinimumYears('0'),0);
  assert.equal(parseMinimumYears('3'),3);
  assert.equal(parseMinimumYears('3.5'),3.5);
  assert.equal(parseMinimumYears('.25'),0.25);
});
test('DA021-02 refuses misleading nonfinite and invalid year text',()=>{
  for(const v of ['-2','NaN','Infinity','1e309','1..2','abc','4 years'])
    assert.throws(()=>parseMinimumYears(v));
});
