import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../tools/browser-read-probe.js', import.meta.url), 'utf8');
function context(origin = 'https://howlongtobeat.com', loggedIn = true) {
  let download;
  const record = {userId: 11, gameId: 22, submissionId: 33, userName: 'SECRET',
    userIp: 'SECRET', title: 'Example', platform: 'PlayStation 2',
    general: { progress: {hours: 1, minutes: 0, seconds: 0}},
    additionals: {notes: 'SECRET'}};
  return {location: {origin, pathname: '/submit/edit/33'},
    document: {
      getElementById: () => ({textContent: JSON.stringify({props: {pageProps: {
        editData: loggedIn ? record : null}}})}),
      createElement: () => ({click() {}}),
      get cookie() { throw Error('Cookie access forbidden'); },
    }, Blob, URL: {createObjectURL: blob => {download = blob; return 'blob:test';}, revokeObjectURL() {}},
    setTimeout: fn => fn(), getDownload: () => download,
  };
}
test('reads authenticated page without cookies and omits private values', async () => {
  const ctx = context(); runInNewContext(script, ctx);
  const text = await ctx.getDownload().text();
  assert.ok(!text.includes('SECRET'));
  assert.equal(JSON.parse(text).platform, 'PlayStation 2');
});
test('rejects wrong origin', () => assert.throws(() => runInNewContext(script, context('https://example.com'))));
test('rejects expired login', () => assert.throws(() => runInNewContext(script, context(undefined, false))));
