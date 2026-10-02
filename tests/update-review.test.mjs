import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createUpdateReview } from '../.local/test-build/update-review.js';

test('popup requires approval and blocks double submit until verified', async () => {
  let resolve, writes = 0;
  const review = createUpdateReview({id: 'op', state: 'prepared'}, async (action, args) => {
    assert.equal(action, 'send'); assert.deepEqual(args, {id: 'op', approved: true, enableAutomatic: true});
    writes++;
    return new Promise(r => {resolve = r;});
  }, async () => {throw Error('unexpected read');}, () => {});
  await review.send(false); assert.equal(writes, 0);
  const first = review.send(true);
  await review.send(true); assert.equal(writes, 1); assert.equal(review.state().busy, true);
  resolve({ok: true, data: true}); await first;
  assert.equal(review.state().phase, 'verified');
  await review.send(true); assert.equal(writes, 1);
});

test('popup handles timeout with reconciliation only, never blind resend', async () => {
  let state = 'prepared'; const calls = [];
  const review = createUpdateReview({id: 'op', state}, async action => {
    calls.push(action);
    if (action === 'send') {state = 'uncertain'; throw Error('Timeout');}
    if (action === 'reconcile') state = 'verified';
    return {ok: true, data: true};
  }, async () => ({ok: true, data: {operations: [{id: 'op', state}]}}), () => {});
  await review.send(true);
  assert.equal(review.state().phase, 'attention');
  await review.send(true); assert.deepEqual(calls, ['send']);
  await review.check();
  assert.equal(review.state().phase, 'verified');
  assert.deepEqual(calls, ['send', 'reconcile']);
});

test('backend false result and conflicts are not shown as successful sync', async () => {
  const calls = [];
  const review = createUpdateReview({id: 'op', state: 'prepared'}, async action => {
    calls.push(action); return {ok: true, data: false};
  }, async () => ({ok: true, data: {operations: [{id: 'op', state: 'conflict'}]}}), () => {});
  await review.send(true); assert.equal(review.state().phase, 'attention');
  await review.check(); await review.send(true);
  assert.deepEqual(calls, ['send']);
});

test('reopened uncertain proposal can be checked without another send', async () => {
  const calls = [];
  const review = createUpdateReview({id: 'op', state: 'uncertain'}, async action => {
    calls.push(action); return {ok: true, data: false};
  }, async () => ({ok: true, data: {operations: [{id: 'op', state: 'verified'}]}}), () => {});
  await review.send(true); await review.check();
  assert.equal(review.state().phase, 'verified'); assert.deepEqual(calls, []);
});
