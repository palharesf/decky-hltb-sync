import { test } from 'node:test';
import assert from 'node:assert/strict';
import { startTracker, libraryApps, currentApp } from '../.local/test-build/steam.js';

const app = {appid: 999, display_name: 'Example', app_type: 1073741824, minutes_playtime_forever: 0};
const flush = () => new Promise(resolve => setImmediate(resolve));

test('Steam adapter preserves shortcut IDs and reads lifetime totals', () => {
  globalThis.appStore = {allApps: [app], GetAppOverviewByAppID: () => app};
  assert.equal(libraryApps('exam')[0].steam, false);
  assert.equal(currentApp('999').id, '999');
  assert.equal(libraryApps('missing').length, 0);
});

test('Non-Steam history reads AppDetails minutes instead of an empty overview total', () => {
  globalThis.appStore = {allApps: [app], GetAppOverviewByAppID: () => app};
  globalThis.appDetailsStore = {GetAppDetails: () => ({nPlaytimeForever: 109})};
  try {
    assert.equal(currentApp('999').minutes, 109);
    assert.equal(currentApp('999').steam, false);
  } finally {delete globalThis.appDetailsStore;}
});

test('polls running apps, serializes suspend/resume and unregisters', async () => {
  const originalInterval = globalThis.setInterval;
  const originalClear = globalThis.clearInterval;
  let poll, suspend, resume, removed = 0;
  globalThis.setInterval = callback => {poll = callback; return 1;};
  globalThis.clearInterval = () => {};
  globalThis.appStore = {allApps: [app], GetAppOverviewByAppID: () => app};
  globalThis.SteamUIStore = {RunningApps: [app]};
  globalThis.SteamClient = {System: {
    RegisterForOnSuspendRequest: callback => {suspend = callback; return {unregister: () => removed++};},
    RegisterForOnResumeFromSuspend: callback => {resume = callback; return {unregister: () => removed++};},
  }};
  const calls = [];
  try {
    const stop = startTracker(async (...args) => {calls.push(args); return {ok: true, data: null};}, () => assert.fail('unexpected error'));
    await flush(); suspend(); await flush(); resume(); await flush();
    globalThis.SteamUIStore.RunningApps = []; poll(); await flush();
    assert.deepEqual(calls.map(c => c[3]), ['snapshot', 'suspend', 'resume', 'snapshot']);
    assert.deepEqual(calls.map(c => c[1]), [0, 1, 2, 3]);
    assert.deepEqual(calls[3][2], []);
    stop(); await flush(); assert.equal(removed, 2);
    assert.equal(calls.at(-1)[3], 'unavailable');
  } finally {globalThis.setInterval = originalInterval; globalThis.clearInterval = originalClear;}
});

test('missing suspend support disables capture', async () => {
  globalThis.SteamClient = {};
  let error = false; const calls = [];
  const stop = startTracker(async (...args) => {calls.push(args); return {ok: true, data: null};}, () => {error = true;});
  await flush(); stop();
  assert.ok(error); assert.equal(calls[0][3], 'unavailable');
});

test('uses the User suspension callbacks present on the inspected Steam Deck', async () => {
  const calls = [];
  let suspend, resume;
  globalThis.SteamClient = {User: {
    RegisterForPrepareForSystemSuspendProgress: callback => {suspend = callback; return {unregister() {}};},
    RegisterForResumeSuspendedGamesProgress: callback => {resume = callback; return {unregister() {}};},
  }};
  const stop = startTracker(async (...args) => {calls.push(args); return {ok: true, data: null};}, () => assert.fail());
  try {
    await flush(); suspend(); await flush(); resume(); await flush();
    assert.deepEqual(calls.map(c => c[3]), ['snapshot', 'suspend', 'resume']);
  } finally { stop(); }
});
