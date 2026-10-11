import {test} from 'node:test';
import assert from 'node:assert/strict';
import {suggestions,roleQuestions} from './interactions.mjs';
test('decision suggestions cannot overwrite a written reason or bypass review',()=>{
  assert.deepEqual(suggestions({decision:true,pending:true}).map(s=>s.action),['plan','evidence','cancel']);
  assert.ok(suggestions({pending:true}).every(s=>s.action!=='draft'));
});
test('inference offers exploration without inventing completed responses',()=>{
  assert.ok(suggestions({running:true}).some(s=>s.action==='models'));
  assert.ok(suggestions({running:true,latestRole:'containment'}).some(s=>s.action==='latest'));
  assert.ok(suggestions({view:'evidence'}).some(s=>s.action==='activity'));
});
test('escalation offers review, never approval, and each agent has distinct questions',()=>{
  const choices=suggestions({escalated:true});
  assert.ok(choices.some(s=>s.action==='escalation'));
  assert.ok(!choices.some(s=>s.action==='approve'));
  assert.equal(new Set(Object.values(roleQuestions).flat().map(q=>q[1])).size,8);
});
