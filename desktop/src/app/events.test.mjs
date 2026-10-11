import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('./api.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext } });
const { mergeEvents } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const event = id => ({ id, time: '2026-10-10', type: 'message', data: { role: 'containment' } });

test('overlapping initial snapshot and poll produce one timeline row per event', () => {
  const snapshot = [event(1), event(2), event(3)];
  const poll = [event(2), event(3), event(4)];
  assert.deepEqual(mergeEvents(snapshot, poll).map(e => e.id), [1, 2, 3, 4]);
  assert.equal(snapshot.length, 3);
});

test('replayed responses cannot duplicate the approval checkpoint', () => {
  const checkpoint = { ...event(2), type: 'approval_requested' };
  const first = mergeEvents([event(1)], [checkpoint]);
  assert.equal(mergeEvents(first, [checkpoint]).filter(e => e.type === 'approval_requested').length, 1);
});

test('out-of-order responses retain server event order', () => {
  assert.deepEqual(mergeEvents([event(3)], [event(1), event(2)]).map(e => e.id), [1, 2, 3]);
});
