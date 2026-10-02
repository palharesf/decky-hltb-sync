import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shortcutHints } from '../.local/test-build/platform.js';
import { startMatchNotices } from '../.local/test-build/match-notices.js';

test('automatic resolution handles previously dismissed sessions without a popup and waits for login', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, auth = 'disconnected', resolved = 0, shown = 0;
  globalThis.setInterval = fn => {tick = fn; return 1;};
  globalThis.clearInterval = () => {};
  const flush = () => new Promise(resolve => setImmediate(resolve));
  try {
    const stop = startMatchNotices(async () => ({ok: true, data: {auth, sessions: [],
      matches: resolved ? [] : [{app: {id: '42'}, notice: null}]}}),
      () => {shown++; throw Error('Unexpected popup');}, async () => {}, () => true,
      async () => {resolved++; return null;});
    await flush(); assert.equal(resolved, 0);
    auth = 'connected'; tick(); await flush();
    assert.equal(resolved, 1); assert.equal(shown, 0);
    tick(); await flush(); assert.equal(resolved, 1);
    stop();
  } finally {globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear;}
});

test('shortcut evidence identifies PS2 without returning private command arguments', () => {
  assert.deepEqual(shortcutHints('"/home/example/Emulation/tools/launchers/pcsx2-qt.sh"',
    '-batch -fullscreen /home/example/Emulation/roms/ps2/Example.iso'),
  {platform: 'PlayStation 2', platformSource: 'ROM folder'});
  assert.deepEqual(shortcutHints('/emulators/PCSX2.AppImage', '/games/Example.chd'),
    {platform: 'PlayStation 2', platformSource: 'PCSX2'});
  assert.deepEqual(shortcutHints('flatpak', 'run org.example.Game'), {});
  assert.deepEqual(shortcutHints('dolphin', '/roms/gc/game.rvz'),
    {platform: 'Nintendo GameCube', platformSource: 'ROM folder'});
});

test('ambiguous hints stay unknown and launchers are excluded', () => {
  assert.equal(shortcutHints('pcsx2', '/roms/psx/game.bin').platform, undefined);
  assert.equal(shortcutHints('retroarch', '/roms/ps2/game.iso /roms/psx/game.bin').platform, undefined);
  assert.equal(shortcutHints('pcsx2', '').excluded, true);
  assert.equal(shortcutHints('ES-DE.AppImage', '').excluded, true);
});

test('closed-session dialogs wait for dismissal and serialize without duplicates', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, dismiss, shown = 0, acknowledged = 0, matches = [];
  globalThis.setInterval = fn => {tick = fn; return 1;};
  globalThis.clearInterval = () => {};
  const flush = () => new Promise(resolve => setImmediate(resolve));
  try {
    const stop = startMatchNotices(async () => ({ok: true, data: {matches}}),
      () => {shown++; return {closed: new Promise(r => {dismiss = r;}), close: () => dismiss(false)};},
      async () => {acknowledged++;});
    await flush();
    assert.equal(shown, 0);
    matches = [{app: {id: '42'}, notice: 'session-1'}];
    tick(); await flush(); tick(); await flush();
    assert.equal(shown, 1); assert.equal(acknowledged, 0);
    dismiss(true); await flush();
    assert.equal(acknowledged, 1);
    tick(); await flush(); assert.equal(shown, 1);
    matches = [{app: {id: '42'}, notice: 'session-2'}];
    tick(); await flush();
    assert.equal(shown, 2);
    stop(); tick(); await flush();
    assert.equal(shown, 2);
    assert.equal(acknowledged, 1); // Unload preserves the second pending notice.
  } finally {globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear;}
});

test('dialogs defer during gameplay or suspension and retry failed presentation', async () => {
  const originalSet = globalThis.setInterval, originalClear = globalThis.clearInterval;
  let tick, playing = true, fail = true, shown = 0, acknowledged = 0, sessions = [];
  globalThis.setInterval = fn => {tick = fn; return 1;};
  globalThis.clearInterval = () => {};
  const flush = () => new Promise(resolve => setImmediate(resolve));
  try {
    const stop = startMatchNotices(async () => ({ok: true, data: {sessions,
      matches: [{app: {id: '42'}, notice: 'session'}]}}), () => {
      if (fail) throw Error('No modal host');
      shown++; return {closed: Promise.resolve(true), close() {}};
    }, async (app, notice) => {assert.equal(app, '42'); assert.equal(notice, 'session'); acknowledged++;}, () => !playing);
    await flush(); assert.equal(shown, 0);
    playing = false; sessions = [{phase: 'suspended'}]; tick(); await flush();
    assert.equal(shown, 0);
    sessions = []; tick(); await flush(); assert.equal(acknowledged, 0);
    fail = false; tick(); await flush(); assert.equal(shown, 1); assert.equal(acknowledged, 1);
    stop();
  } finally {globalThis.setInterval = originalSet; globalThis.clearInterval = originalClear;}
});
