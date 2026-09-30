// Run manually in DevTools Console on the existing HLTB edit page, after login.
// Reads only the page already loaded; no fetch, cookie access, logging or submission.
(() => {
  if (location.origin !== 'https://howlongtobeat.com' ||
      !/^\/submit\/edit\/\d+\/?$/.test(location.pathname)) {
    throw new Error('Open the existing HLTB record edit page.');
  }
  const node = document.getElementById('__NEXT_DATA__');
  if (!node) throw new Error('Unrecognized page format.');
  const record = JSON.parse(node.textContent).props?.pageProps?.editData;
  const submissionId = Number(location.pathname.split('/')[3]);
  if (!record || record.submissionId !== submissionId ||
      !Number.isInteger(record.userId) || record.userId <= 0 ||
      !Number.isInteger(record.gameId) || record.gameId <= 0 ||
      typeof record.platform !== 'string' || !record.platform ||
      !record.general?.progress) {
    throw new Error('Missing or unsupported record, or login required.');
  }
  // Report no user identifiers, username, IP, notes, cookies or full page data.
  const report = {
    schema: 1, source: 'hltb-edit-page',
    title: record.title, platform: record.platform,
    progress: record.general.progress,
    fields: Object.keys(record).sort(),
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)],
    { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url; a.download = 'hltb-read-probe.private.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
})();
