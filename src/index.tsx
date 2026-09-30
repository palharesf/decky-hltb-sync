import { callable, definePlugin, toaster } from '@decky/api';
import { ButtonItem, DropdownItem, Navigation, PanelSection, PanelSectionRow, TextField, ToggleField } from '@decky/ui';
import { useEffect, useState } from 'react';
import { currentApp, libraryApps, startTracker } from './steam';
import type { App, Entry, Operation, Result, SearchResult, Status } from './types';

const getStatus = callable<[], Result<Status>>('status');
const command = callable<[action: string, args: Record<string, unknown>], Result<unknown>>('command');
const observe = callable<[epoch: string, sequence: number, apps: App[], event: string], Result<null>>('observe');
const duration = (seconds: number) => `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m ${Math.floor(seconds % 60)}s`;
const states: Record<string, string> = { local: 'Recorded locally', pending: 'Pending', synced: 'Synced', attention: 'Needs attention' };
const messages: Record<string, string> = {
  connect_required: 'Connect to HowLongToBeat first.', login_required: 'Your HLTB login has expired. Please reconnect.',
  browser_unavailable: 'Steam browser integration is unavailable. Your sessions are safe.',
  browser_closed_or_navigated: 'The connected HLTB window was closed or navigated away. Please reconnect.',
  login_window_not_found: 'Waiting for the HLTB login window. Close older HLTB windows and try Connect again.',
  remote_changed_review_required: 'HLTB changed since the last confirmation. Review the current remote record first.',
  incomplete_or_unknown_library: 'HLTB returned an incomplete or unsupported library. Nothing was changed.',
  automatic_sync_needs_attention: 'Automatic sync needs attention. Review your pending sessions and proposals.',
  search_contract_changed: 'HLTB search changed. You can still select an existing record from your library.',
  operation_failed_review_required: 'The operation could not finish. Refresh and review its state before trying again.',
};

function Content() {
  const [data, setData] = useState<Status>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [appId, setAppId] = useState('');
  const [submission, setSubmission] = useState<number>();
  const [mode, setMode] = useState('sessions');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [gameId, setGameId] = useState<number>();
  const [platform, setPlatform] = useState('');
  const [approval, setApproval] = useState<string>();
  const [singleWriter, setSingleWriter] = useState(false);
  const [review, setReview] = useState<{previous: Entry; current: Entry; changed: boolean}>();
  const refresh = async () => {
    try {
      const result = await getStatus();
      if (result.ok) setData(result.data);
      else setError(result.error);
    } catch { setError('Backend unavailable. Local sessions will recover when it returns.'); }
  };
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 5000); return () => clearInterval(timer); }, []);
  const run = async <T,>(action: string, args: Record<string, unknown> = {}): Promise<T | undefined> => {
    setBusy(true); setError('');
    try {
      const result = await command(action, args);
      if (!result.ok) { setError(messages[result.error] ?? result.error); return undefined; }
      await refresh();
      return result.data as T;
    } catch { setError('Connection interrupted. Review the operation before retrying.'); return undefined; }
    finally { setBusy(false); }
  };
  const apps = libraryApps(query);
  const app = appId ? currentApp(appId) : undefined;
  const mapping = data?.mappings.find(m => m.app === appId);
  const library = (data?.library ?? []).filter(e => !query || e.title.toLowerCase().includes(query.toLowerCase()));
  const selectedGame = results.find(r => r.gameId === gameId);
  const selectedEntry = data?.library.find(e => e.submissionId === submission);
  const selectApp = (id: string) => { setAppId(id); setReview(undefined); setApproval(undefined); setSingleWriter(false); };
  const connect = async () => {
    const result = await run<{url: string}>('connect');
    if (result) { Navigation.CloseSideMenus(); Navigation.NavigateToExternalWeb(result.url); }
  };
  return <>
    <PanelSection title="Account">
      <PanelSectionRow>HowLongToBeat: {data?.auth.replace(/_/g, ' ') ?? 'Loading'}</PanelSectionRow>
      <PanelSectionRow>Session capture: {data?.tracker ?? 'Waiting'}</PanelSectionRow>
      {(error || data?.error) && <PanelSectionRow>{error || messages[data?.error ?? ''] || data?.error}</PanelSectionRow>}
      <PanelSectionRow><ButtonItem disabled={busy} onClick={connect}>Connect to HowLongToBeat</ButtonItem></PanelSectionRow>
      <PanelSectionRow>Sign in on the official website, then return here. Passwords and cookies stay in Steam's browser. Keep the HLTB window available for synchronization.</PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy} onClick={() => run('library')}>Refresh HLTB library</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy} onClick={() => run('disconnect')}>Disconnect plugin</ButtonItem></PanelSectionRow>
      <PanelSectionRow>Disconnect disables automatic sync. To sign out of the website, use its own logout action.</PanelSectionRow>
    </PanelSection>
    <PanelSection title="Game mapping">
      <PanelSectionRow><TextField label="Find a game" value={query} onChange={e => setQuery(e.target.value)} /></PanelSectionRow>
      <DropdownItem label="Steam library entry" rgOptions={apps.map(a => ({data: a.id, label: `${a.name}${a.steam ? '' : ' (Non-Steam)'}`}))}
        selectedOption={appId} onChange={o => selectApp(o.data)} strDefaultLabel="Select a direct game shortcut" />
      {app && <PanelSectionRow>{app.name} · {app.steam && app.minutes !== null ? `Steam total: ${duration(app.minutes * 60)}` : 'Local session tracking'}</PanelSectionRow>}
      {data?.libraryCached && <PanelSectionRow>Cached HLTB data. Refresh before linking or creating a record.</PanelSectionRow>}
      {!mapping && <>
        <DropdownItem label="HLTB account record" selectedOption={submission} onChange={o => setSubmission(o.data)}
          strDefaultLabel="Choose an existing record" rgOptions={library.map(e => ({data: e.submissionId,
            label: `${e.title} · ${e.platform} · ${duration(e.seconds)} · ${Array.isArray(e.lists) ? e.lists.join(', ') : ''}`}))} />
        <DropdownItem label="Time source" selectedOption={mode} onChange={o => setMode(o.data)} rgOptions={[
          {data: 'sessions', label: 'Add locally recorded sessions'},
          ...(app?.steam ? [{data: 'steam_total', label: 'Use Steam lifetime total (explicit history import)'}] : [])]} />
        {selectedEntry && <PanelSectionRow>Link {app?.name ?? 'selected shortcut'} to {selectedEntry.title} on {selectedEntry.platform}. Existing lists and notes will be preserved.</PanelSectionRow>}
        <PanelSectionRow><ButtonItem disabled={busy || !app || !submission || data?.libraryCached} onClick={() => run('bind', {app, submissionId: submission, mode})}>Confirm link and time source</ButtonItem></PanelSectionRow>
      </>}
      {mapping && <>
        <PanelSectionRow>Linked: {mapping.title} · {mapping.platform} · confirmed HLTB time {duration(mapping.seconds)}</PanelSectionRow>
        <PanelSectionRow>Source: {mapping.mode === 'steam_total' ? 'Steam lifetime total' : 'Local sessions'}. Unmapped games are not tracked.</PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={busy} onClick={async () => {
          const result = await run<typeof review>('review', {appId}); if (result) setReview(result);
        }}>Read current HLTB record</ButtonItem></PanelSectionRow>
        {review && <PanelSectionRow>Previously confirmed: {duration(review.previous.seconds)}. Current HLTB: {duration(review.current.seconds)}. {review.changed ? 'Remote record changed.' : 'Record unchanged.'}</PanelSectionRow>}
        {review?.changed && <PanelSectionRow><ButtonItem disabled={busy} onClick={async () => {
          await run('accept_remote', {appId, expectedSeconds: review.current.seconds}); setReview(undefined);
        }}>Accept remote baseline; keep pending sessions</ButtonItem></PanelSectionRow>}
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => run('preview', {appId, steamMinutes: currentApp(appId)?.minutes})}>Preview playtime update</ButtonItem></PanelSectionRow>
        <ToggleField label="I have disabled other writers for this HLTB record" checked={singleWriter} onChange={setSingleWriter}
          description="Playnite can overwrite Deck time. Automatic sync requires one verified manual session update." />
        <ToggleField label="Automatically sync closed sessions" checked={mapping.automatic} disabled={busy || mapping.mode !== 'sessions'}
          onChange={enabled => { void run('automatic', {appId, enabled, singleWriter}); }} />
      </>}
    </PanelSection>
    {!mapping && app && <PanelSection title="Find or create an HLTB record">
      <PanelSectionRow><ButtonItem disabled={busy || query.trim().length < 2} onClick={async () => {
        const found = await run<SearchResult[]>('search', {query}); if (found) { setResults(found); setGameId(undefined); }
      }}>Search HLTB catalog</ButtonItem></PanelSectionRow>
      <DropdownItem label="Catalog game" selectedOption={gameId} onChange={o => setGameId(o.data)}
        strDefaultLabel="Confirm the correct edition" rgOptions={results.map(r => ({data: r.gameId, label: `${r.title} (#${r.gameId})`}))} />
      {selectedGame && <PanelSectionRow>Main: {duration(selectedGame.main)} · Main + Extra: {duration(selectedGame.extra)} · Completionist: {duration(selectedGame.completionist)}</PanelSectionRow>}
      <PanelSectionRow><TextField label="HLTB platform (exact name)" value={platform} onChange={e => setPlatform(e.target.value)} /></PanelSectionRow>
      <PanelSectionRow>For Vexx, confirm PlayStation 2. Creation checks all your lists, starts at zero, and never marks the game completed.</PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy || !selectedGame || !platform.trim()} onClick={() => run('create', {app,
        gameId, title: selectedGame?.title, platform: platform.trim()})}>Preview new Playing record</ButtonItem></PanelSectionRow>
    </PanelSection>}
    <PanelSection title="Proposals and reconciliation">
      {!data?.operations.length && <PanelSectionRow>No proposals yet.</PanelSectionRow>}
      {data?.operations.filter(o => !appId || o.app === appId).map((o: Operation) => <PanelSectionRow key={o.id}>
        <div>{o.title} · {o.platform} · {o.state}</div>
        <div>{duration(o.before)} → {duration(o.after)} {o.kind === 'create' ? '(new Playing record)' : ''}</div>
        {o.state === 'prepared' && <>
          <ToggleField label="I approve this exact update to my HLTB account" checked={approval === o.id} onChange={v => setApproval(v ? o.id : undefined)} />
          <ButtonItem disabled={busy || approval !== o.id} onClick={async () => {
            await run('send', {id: o.id, approved: true}); setApproval(undefined);
          }}>Submit approved update and verify</ButtonItem>
          <ButtonItem disabled={busy} onClick={() => run('cancel', {id: o.id})}>Cancel unsent proposal</ButtonItem>
        </>}
        {o.state === 'uncertain' && <ButtonItem disabled={busy} onClick={() => run('reconcile', {id: o.id})}>Reread HLTB without resending</ButtonItem>}
        {['uncertain', 'conflict'].includes(o.state) && o.kind === 'create' && <>
          <div>Refresh your HLTB library and select the matching account record above. Adopting it only changes the local link; it never creates another entry.</div>
          <ToggleField label="I confirm the selected existing record resolves this creation" checked={approval === o.id} onChange={v => setApproval(v ? o.id : undefined)} />
          <ButtonItem disabled={busy || !submission || approval !== o.id} onClick={() => run('adopt_created_record', {id: o.id, submissionId: submission})}>Use selected existing record</ButtonItem>
        </>}
        {['uncertain', 'conflict'].includes(o.state) && o.kind !== 'create' && <>
          <div>Inspect HLTB first. These decisions change the local ledger only; an incorrect decision can omit or duplicate time.</div>
          <ToggleField label="I checked HLTB and want to resolve this operation" checked={approval === o.id} onChange={v => setApproval(v ? o.id : undefined)} />
          <ButtonItem disabled={busy || approval !== o.id} onClick={() => run('resolve', {id: o.id, decision: 'included'})}>The sessions are already included remotely</ButtonItem>
          <ButtonItem disabled={busy || approval !== o.id} onClick={() => run('resolve', {id: o.id, decision: 'not_included'})}>The sessions are not included; keep them pending</ButtonItem>
        </>}
      </PanelSectionRow>)}
    </PanelSection>
    <PanelSection title="Local sessions">
      {!data?.sessions.length && <PanelSectionRow>Link a game, then launch its direct Steam shortcut to start tracking.</PanelSectionRow>}
      {data?.sessions.filter(s => !appId || s.app === appId).map(s => <PanelSectionRow key={s.id}>
        <div>{s.name}: {duration(s.elapsed)} · {states[s.state] ?? s.state} · {s.phase}</div>
        {s.reason && <div>Reason: {s.reason.replace(/_/g, ' ')}</div>}
        {s.state === 'attention' && ['restart', 'observation_gap'].includes(s.reason ?? '') && !['running', 'suspended'].includes(s.phase) &&
          <ButtonItem disabled={busy} onClick={() => run('checkpoint', {id: s.id})}>Accept saved time only; exclude the unobserved gap</ButtonItem>}
      </PanelSectionRow>)}
    </PanelSection>
  </>;
}

export default definePlugin(() => {
  let notified = false;
  const stop = startTracker(observe, () => {
    if (!notified) { notified = true; toaster.toast({title: 'HLTB Sync', body: 'Session capture needs attention. Open the plugin to review.'}); }
  });
  return { name: 'HLTB Sync for Deck', title: <div>HLTB Sync for Deck</div>, content: <Content />,
    icon: <span>◷</span>, onDismount: stop };
});
