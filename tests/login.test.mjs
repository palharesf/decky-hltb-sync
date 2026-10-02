import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLoginReturn } from '../.local/test-build/login.js';
import { createLoginBrowser, startLoginRecovery } from '../.local/test-build/login-browser.js';

function browserHarness(results = [{ok: true, data: true}]) {
  const calls = [];
  const view = {SetVisible: value => calls.push(['visible', value]), SetFocus: value => calls.push(['focus', value])};
  const win = {LocationPathName: '/externalweb', VirtualKeyboardManager: {
    SetVirtualKeyboardHidden: () => calls.push(['hide-keyboard'])}, NavigateBack: () => calls.push(['back'])};
  const runtime = {SteamClient: {BrowserView: {Create: () => view, Destroy: () => calls.push(['destroy'])}},
    SteamUIStore: {RunningApps: [], GetFocusedWindowInstance: () => win},
    BrowserAndBackstackInstances: [{name: 'ExternalWeb', URL: 'https://howlongtobeat.com/login'}]};
  const command = async action => {
    calls.push([action]);
    return ['prepare_background', 'prepare_restore'].includes(action) ? {ok: true, data: {url: 'https://howlongtobeat.com/#decky-hltb-sync=test'}}
      : results.shift() ?? {ok: false, error: 'login_window_not_found'};
  };
  return {calls, runtime, win, browser: createLoginBrowser(command, () => calls.push(['panel']), runtime, async () => {})};
}

test('login handoff verifies a hidden view before dismissing keyboard and returning', async () => {
  const h = browserHarness([{ok: false, error: 'login_window_not_found'}, {ok: true, data: true}]);
  assert.equal(await h.browser.complete(), true);
  assert.deepEqual(h.calls, [['prepare_background'], ['visible', false], ['focus', false],
    ['retain_background'], ['retain_background'], ['hide-keyboard'], ['back'], ['panel']]);
  h.browser.dispose();
  assert.equal(h.calls.at(-1)[0], 'destroy');
});

test('reboot recovery verifies a hidden view without navigation or keyboard changes', async () => {
  const h = browserHarness();
  assert.equal(await h.browser.restore(), true);
  assert.deepEqual(h.calls, [['prepare_restore'], ['visible', false], ['focus', false], ['retain_background']]);
  h.browser.dispose();
});

test('startup recovery retries startup failures, respects disconnect and avoids duplicate restores', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, auth = 'disconnected', canRestore = false, attempts = 0, settle;
  globalThis.setInterval = fn => {tick = fn; return 1;};
  globalThis.clearInterval = () => {};
  const flush = () => new Promise(r => setImmediate(r));
  try {
    const stop = startLoginRecovery(async () => ({ok: true, data: {auth, canRestore}}),
      () => {attempts++; return new Promise(r => {settle = r;});});
    await flush(); assert.equal(attempts, 0);
    canRestore = true; tick(); await flush(); tick(); await flush();
    assert.equal(attempts, 1);
    settle(false); await flush(); tick(); await flush(); assert.equal(attempts, 2);
    auth = 'connected'; settle(true); await flush(); tick(); await flush(); assert.equal(attempts, 2);
    auth = 'connecting'; tick(); await flush(); assert.equal(attempts, 2);
    auth = 'disconnected'; canRestore = false; tick(); await flush(); assert.equal(attempts, 2);
    stop(); canRestore = true; tick(); await flush(); assert.equal(attempts, 2);
  } finally {globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear;}
});

test('failed or wrong-account handoff leaves login page and keyboard alone', async () => {
  const h = browserHarness([{ok: false, error: 'account_changed_disconnect_first'}]);
  assert.equal(await h.browser.complete(), false);
  assert.equal(h.calls.at(-1)[0], 'destroy');
  assert.ok(!h.calls.some(([action]) => ['back', 'panel', 'hide-keyboard'].includes(action)));
});

test('successful handoff does not steal focus after navigation or game launch', async () => {
  for (const changed of ['route', 'game', 'origin']) {
    const h = browserHarness();
    if (changed === 'route') h.win.LocationPathName = '/library/home';
    if (changed === 'game') h.runtime.SteamUIStore.RunningApps = [{}];
    if (changed === 'origin') h.runtime.BrowserAndBackstackInstances[0].URL = 'https://example.com';
    assert.equal(await h.browser.complete(), true);
    assert.ok(!h.calls.some(([action]) => ['back', 'panel', 'hide-keyboard'].includes(action)));
    h.browser.dispose();
  }
});

test('login return survives panel closure, confirms fresh data and returns once', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, cleared = 0, returned = 0, auth = 'connecting', cached = true;
  globalThis.setInterval = fn => { tick = fn; return 1; };
  globalThis.clearInterval = () => { cleared++; };
  try {
    const login = createLoginReturn(async () => ({ok: true, data: {auth, libraryCached: cached}}), () => returned++);
    assert.equal(tick, undefined); // Loading an already-connected plugin never steals focus.
    login.begin();
    await tick();
    auth = 'connected';
    await tick();
    assert.equal(returned, 0);
    cached = false;
    await tick();
    await tick();
    assert.equal(returned, 1);
    assert.equal(cleared, 1);
  } finally { globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear; }
});

test('cancel, replacement and expiry discard late login results', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, resolve, clock = 0, returned = 0;
  globalThis.setInterval = fn => { tick = fn; return 1; };
  globalThis.clearInterval = () => {};
  try {
    const login = createLoginReturn(() => new Promise(r => { resolve = r; }), () => returned++, () => clock);
    for (const action of ['cancel', 'begin']) {
      login.begin();
      const pending = tick();
      login[action]();
      resolve({ok: true, data: {auth: 'connected', libraryCached: false}});
      await pending;
      assert.equal(returned, 0);
    }
    clock = 300001;
    await tick();
    assert.equal(returned, 0);
    login.cancel();
  } finally { globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear; }
});

test('temporary RPC failures recover, disconnected login cancels return', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, fail = true, returned = 0, auth = 'connecting';
  globalThis.setInterval = fn => { tick = fn; return 1; };
  globalThis.clearInterval = () => {};
  try {
    const login = createLoginReturn(async () => {
      if (fail) throw Error('Offline');
      return {ok: true, data: {auth, libraryCached: false}};
    }, () => returned++);
    login.begin(); await tick();
    fail = false; auth = 'connected'; await tick();
    assert.equal(returned, 1);
    login.begin(); auth = 'disconnected'; await tick();
    auth = 'connected'; await tick();
    assert.equal(returned, 1);
  } finally { globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear; }
});
