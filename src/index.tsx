import { callable, definePlugin, toaster } from '@decky/api';
import { ButtonItem as DeckyButtonItem, DropdownItem as DeckyDropdownItem, Navigation, QuickAccessTab, PanelSection, PanelSectionRow, TextField, ToggleField } from '@decky/ui';
import { useEffect, useState, type ComponentProps } from 'react';
import { canShowMatchPrompt, currentApp, libraryApps, startTracker } from './steam';
import { createLoginReturn } from './login';
import { createLoginBrowser, startLoginRecovery } from './login-browser';
import { startMatchNotices, type MatchPrompt } from './match-notices';
import { showMatchDialog, showUpdateDialog, showCheckpointDialog } from './match-dialog';
import type { App, Entry, MatchRequest, Operation, Result, SearchResult, Status, Session } from './types';

const getStatus = callable<[], Result<Status>>('status');
const command = callable<[action: string, args: Record<string, unknown>], Result<unknown>>('command');
const observe = callable<[epoch: string, sequence: number, apps: App[], event: string], Result<null>>('observe');
const duration = (seconds: number) => `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m ${Math.floor(seconds % 60)}s`;
const ButtonItem = (props: ComponentProps<typeof DeckyButtonItem>) =>
  <DeckyButtonItem layout="below" childrenContainerWidth="max" bottomSeparator="none" {...props} />;
const DropdownItem = (props: ComponentProps<typeof DeckyDropdownItem>) =>
  <DeckyDropdownItem layout="below" childrenContainerWidth="max" {...props} />;
const states: Record<string, string> = { local: 'Saved', pending: 'Pending', synced: 'Synced', attention: 'Review' };
const messages: Record<string, string> = {
  connect_required: 'Reconnect to HLTB', login_required: 'Login expired · Reconnect',
  browser_unavailable: 'Connection unavailable · Saved',
  browser_closed_or_navigated: 'Reconnect · Sessions saved',
  login_window_not_found: 'Waiting for login',
  remote_changed_review_required: 'HLTB changed · Review',
  incomplete_or_unknown_library: 'Library unavailable',
  sync_waiting_connection: 'Waiting for connection · Saved',
  network_or_session_error: 'Connection unavailable · Saved',
  automatic_sync_needs_attention: 'Sync needs review',
  search_contract_changed: 'Search unavailable',
  operation_failed_review_required: 'Update needs review',
};

function Content({ loginReturn, openMatch, openReview, openCheckpoint, cancelRestore, rememberLoginWindow }: { loginReturn: ReturnType<typeof createLoginReturn>; cancelRestore(): void; rememberLoginWindow(): void; openCheckpoint(session: Session): MatchPrompt;
  openMatch: (match: MatchRequest) => MatchPrompt; openReview: (operation: Operation) => MatchPrompt }) {
  const [data, setData] = useState<Status>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [accountOptions, setAccountOptions] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [history, setHistory] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [importHistory, setImportHistory] = useState(false);
  const [importMinutes, setImportMinutes] = useState('');
  const [matchChoices, setMatchChoices] = useState<Record<string, number>>({});
  const [query, setQuery] = useState('');
  const [appId, setAppId] = useState('');
  const [submission, setSubmission] = useState<number>();
  const [mode, setMode] = useState('sessions');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [gameId, setGameId] = useState<number>();
  const [platform, setPlatform] = useState('');
  const [approval, setApproval] = useState<string>();
  const [review, setReview] = useState<{previous: Entry; current: Entry; changed: boolean}>();
  const refresh = async () => {
    try {
      const result = await getStatus();
      if (result.ok) setData(result.data);
      else setError(result.error);
    } catch { setError('Plugin unavailable'); }
  };
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(), 5000); return () => clearInterval(timer); }, []);
  const run = async <T,>(action: string, args: Record<string, unknown> = {}): Promise<T | undefined> => {
    setBusy(true); setError('');
    try {
      const result = await command(action, args);
      if (!result.ok) { setError(messages[result.error] ?? 'Action needs review'); return undefined; }
      await refresh();
      return result.data as T;
    } catch { setError('Connection interrupted'); return undefined; }
    finally { setBusy(false); }
  };
  const apps = libraryApps(query);
  const app = appId ? currentApp(appId) : undefined;
  const mapping = data?.mappings.find(m => m.app === appId);
  const library = (data?.library ?? []).filter(e => !query || e.title.toLowerCase().includes(query.toLowerCase()));
  const selectedGame = results.find(r => r.gameId === gameId);
  const selectedEntry = data?.library.find(e => e.submissionId === submission);
  const connected = data?.auth === 'connected';
  const connecting = data?.auth === 'connecting';
  const openOperations = data?.operations.filter(o => ['prepared', 'uncertain', 'conflict'].includes(o.state)) ?? [];
  const recent = data?.sessions.slice(0, history ? 20 : 3) ?? [];
  const pending = data?.sessions.filter(s => s.state !== 'synced' && !['running', 'suspended'].includes(s.phase)).length ?? 0;
  const selectApp = (id: string) => {
    setAppId(id); setReview(undefined); setApproval(undefined);
    setImportHistory(false); setImportMinutes(String(currentApp(id)?.minutes ?? ''));
  };
  const connect = async () => {
    if (connected || connecting) return;
    cancelRestore();
    loginReturn.cancel();
    const result = await run<{url: string}>('connect');
    if (result) {
      Navigation.CloseSideMenus(); Navigation.NavigateToExternalWeb(result.url);
      rememberLoginWindow();
      loginReturn.begin();
    }
  };
  return <>
    <PanelSection title="Account">
      {(error || data?.error) && <PanelSectionRow>{error || messages[data?.error ?? ''] || 'Needs review'}</PanelSectionRow>}
      <PanelSectionRow><ButtonItem disabled={busy || !data || connected || connecting} onClick={connect}>
        {connected ? 'Connected' : connecting ? 'Connecting…' : 'Connect to HLTB'}
      </ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem onClick={() => setAccountOptions(!accountOptions)}>{accountOptions ? 'Account −' : 'Account +'}</ButtonItem></PanelSectionRow>
      {accountOptions && <>
        <PanelSectionRow>{data?.library.length ?? 0} records</PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => run('library')}>Refresh library</ButtonItem></PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => { cancelRestore(); loginReturn.cancel(); void run('disconnect'); }}>Disconnect</ButtonItem></PanelSectionRow>
      </>}
    </PanelSection>
    <PanelSection title={pending ? `Sessions · ${pending} pending` : 'Sessions'}>
      {data && data.tracker !== 'observing' && <PanelSectionRow>Tracker unavailable</PanelSectionRow>}
      {!recent.length && <PanelSectionRow>No sessions</PanelSectionRow>}
      {recent.map((s, index) => <PanelSectionRow key={s.id}>
        <div style={{fontWeight: 600, overflowWrap: 'anywhere', marginTop: index ? 18 : 0, marginBottom: 6}}>{s.name}</div>
        <div style={{display: 'flex', justifyContent: 'space-between', gap: 8}}>
          <span>{duration(s.elapsed)}</span>
          <span>{s.phase === 'running' ? 'Playing' : s.phase === 'suspended' ? 'Suspended' : states[s.state] ?? 'Saved'}</span>
        </div>
        {s.state === 'attention' && <ButtonItem onClick={() => {
          if (['restart', 'observation_gap'].includes(s.reason ?? '') && !['running', 'suspended'].includes(s.phase)) {
            void openCheckpoint(s).closed.then(() => refresh());
          } else {selectApp(s.app); setAdvanced(true);}
        }}>Review</ButtonItem>}
      </PanelSectionRow>)}
      {(data?.sessions.length ?? 0) > 3 && <ButtonItem onClick={() => setHistory(!history)}>{history ? 'Show less' : 'History'}</ButtonItem>}
      {openOperations.map(o => <PanelSectionRow key={o.id}>
        <ButtonItem onClick={() => openReview(o)}>Review · {o.title}</ButtonItem>
      </PanelSectionRow>)}
      <ButtonItem onClick={() => setAdvanced(!advanced)}>{advanced ? 'Advanced −' : 'Advanced +'}</ButtonItem>
    </PanelSection>
    {advanced && <>
    {!!data?.matches?.length && <PanelSection title="Match games">
      {data.matches.map(match => {
        const selected = matchChoices[match.app.id] ?? match.recommended ?? undefined;
        return <PanelSectionRow key={match.app.id}>
          <div style={{fontWeight: 600, marginTop: 12}}>{match.app.name}</div>
          <div>{duration(match.seconds)} · Saved</div>
          <ButtonItem onClick={() => openMatch(match)}>Review match</ButtonItem>
          <div>{match.app.platform ? `${match.app.platform} · ${match.app.platformSource}` : 'Platform unknown'}</div>
          <DropdownItem label="HLTB match" selectedOption={selected}
            strDefaultLabel="Choose match" rgOptions={match.candidates.map(e => ({data: e.submissionId,
              label: `${e.title} · ${e.platform}`}))}
            onChange={o => setMatchChoices(previous => ({...previous, [match.app.id]: o.data}))} />
          {match.recommended === selected && <div>Suggested match</div>}
          {data.libraryCached && <div>Cached matches</div>}
          <ButtonItem disabled={busy || !selected || !connected} onClick={async () => {
            const linked = await run<Entry>('bind', {app: match.app, submissionId: selected, mode: 'sessions'});
            if (linked) { selectApp(match.app.id); await run('preview', {appId: match.app.id}); }
          }}>Confirm match</ButtonItem>
          <ButtonItem onClick={() => {selectApp(match.app.id); setQuery(match.app.name); setPlatform(match.app.platform ?? '');}}>Choose another</ButtonItem>
        </PanelSectionRow>;
      })}
    </PanelSection>}
    <PanelSection title="Games">
      <PanelSectionRow><TextField label="Find a game" value={query} onChange={e => setQuery(e.target.value)} /></PanelSectionRow>
      <DropdownItem label="Steam game" rgOptions={apps.map(a => ({data: a.id, label: `${a.name}${a.steam ? '' : ' (Non-Steam)'}`}))}
        selectedOption={appId} onChange={o => selectApp(o.data)} strDefaultLabel="Select game" />
      {app && <PanelSectionRow>{app.name} · {app.steam && app.minutes !== null ? `Steam total: ${duration(app.minutes * 60)}` : 'Local session tracking'}</PanelSectionRow>}
      {data?.libraryCached && <PanelSectionRow>Cached library</PanelSectionRow>}
      {!mapping && app && <>
        <DropdownItem label="HLTB record" selectedOption={submission} onChange={o => setSubmission(o.data)}
          strDefaultLabel="Select record" rgOptions={library.map(e => ({data: e.submissionId,
            label: `${e.title} · ${e.platform} · ${duration(e.seconds)} · ${Array.isArray(e.lists) ? e.lists.join(', ') : ''}`}))} />
        <DropdownItem label="Time source" selectedOption={mode} onChange={o => setMode(o.data)} rgOptions={[
          {data: 'sessions', label: 'Deck sessions'},
          ...(app?.steam ? [{data: 'steam_total', label: 'Steam total (import)'}] : [])]} />
        {selectedEntry && <PanelSectionRow>{selectedEntry.title} · {selectedEntry.platform}</PanelSectionRow>}
        {mode === 'steam_total' && <PanelSectionRow>Includes Steam history</PanelSectionRow>}
        <PanelSectionRow><ButtonItem disabled={busy || !app || !submission || data?.libraryCached} onClick={() => run('bind', {app, submissionId: submission, mode})}>Link game</ButtonItem></PanelSectionRow>
        <PanelSectionRow><ButtonItem onClick={() => setCatalogOpen(!catalogOpen)}>{catalogOpen ? 'Hide catalog' : 'Find another record'}</ButtonItem></PanelSectionRow>
      </>}
      {mapping && <>
        <PanelSectionRow>{mapping.platform} · HLTB {duration(mapping.seconds)}</PanelSectionRow>
        <PanelSectionRow><ButtonItem disabled={busy} onClick={async () => {
          const result = await run<typeof review>('review', {appId}); if (result) setReview(result);
        }}>Refresh record</ButtonItem></PanelSectionRow>
        {review && <PanelSectionRow>HLTB {duration(review.current.seconds)} · {review.changed ? 'Changed' : 'Unchanged'}</PanelSectionRow>}
        {review?.changed && <PanelSectionRow><ButtonItem disabled={busy} onClick={async () => {
          await run('accept_remote', {appId, expectedSeconds: review.current.seconds}); setReview(undefined);
        }}>Accept HLTB baseline</ButtonItem></PanelSectionRow>}
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => run('preview', {appId, steamMinutes: currentApp(appId)?.minutes})}>Preview sync</ButtonItem></PanelSectionRow>
        {!mapping.historyImported && <>
          <ToggleField label="Import past hours once" checked={importHistory} onChange={setImportHistory}
            description="Includes saved sessions" />
          {importHistory && <>
            <PanelSectionRow><TextField label="Lifetime total (minutes)" mustBeNumeric value={importMinutes}
              onChange={e => setImportMinutes(e.target.value)} /></PanelSectionRow>
            <PanelSectionRow>Replaces total · Not added</PanelSectionRow>
            <PanelSectionRow><ButtonItem disabled={busy || !/^[1-9]\d*$/.test(importMinutes)}
              onClick={() => run('preview_import', {appId, totalMinutes: Number(importMinutes), includesSaved: true})}>Preview import</ButtonItem></PanelSectionRow>
          </>}
        </>}
        <ToggleField label="Auto-sync sessions" checked={mapping.automatic} disabled={busy || mapping.mode !== 'sessions'}
          description="Pauses on conflicts"
          onChange={enabled => { void run('automatic', {appId, enabled}); }} />
      </>}
    </PanelSection>
    {!mapping && app && catalogOpen && <PanelSection title="HLTB catalog">
      <PanelSectionRow><ButtonItem disabled={busy || query.trim().length < 2} onClick={async () => {
        const found = await run<SearchResult[]>('search', {query}); if (found) { setResults(found); setGameId(undefined); }
      }}>Search catalog</ButtonItem></PanelSectionRow>
      <DropdownItem label="Catalog game" selectedOption={gameId} onChange={o => setGameId(o.data)}
        strDefaultLabel="Confirm the correct edition" rgOptions={results.map(r => ({data: r.gameId, label: `${r.title} (#${r.gameId})`}))} />
      {selectedGame && <PanelSectionRow>Main: {duration(selectedGame.main)} · Main + Extra: {duration(selectedGame.extra)} · Completionist: {duration(selectedGame.completionist)}</PanelSectionRow>}
      <PanelSectionRow><TextField label="Platform (exact name)" value={platform} onChange={e => setPlatform(e.target.value)} /></PanelSectionRow>
      <PanelSectionRow>New record · Playing · 0h</PanelSectionRow>
      <PanelSectionRow><ButtonItem disabled={busy || !selectedGame || !platform.trim()} onClick={() => run('create', {app,
        gameId, title: selectedGame?.title, platform: platform.trim()})}>Preview new record</ButtonItem></PanelSectionRow>
    </PanelSection>}
    <PanelSection title="Sync review">
      {!data?.operations.length && <PanelSectionRow>No proposals yet.</PanelSectionRow>}
      {data?.operations.filter(o => !appId || o.app === appId).map((o: Operation) => <PanelSectionRow key={o.id}>
        <div>{o.title} · {o.platform} · {o.state}</div>
        <div>{duration(o.before)} → {duration(o.after)} {o.kind === 'create' ? '(new Playing record)' : ''}</div>
        {o.kind === 'history_import' && <div>History import</div>}
        {['prepared', 'sending', 'uncertain', 'conflict'].includes(o.state) &&
          <ButtonItem onClick={() => openReview(o)}>Review in popup</ButtonItem>}
        {o.state === 'prepared' && <>
          <ButtonItem disabled={busy} onClick={() => openReview(o)}>Confirm and sync</ButtonItem>
          <ButtonItem disabled={busy} onClick={() => run('cancel', {id: o.id})}>Cancel proposal</ButtonItem>
        </>}
        {o.state === 'uncertain' && <ButtonItem disabled={busy} onClick={() => run('reconcile', {id: o.id})}>Check HLTB status</ButtonItem>}
        {['uncertain', 'conflict'].includes(o.state) && o.kind === 'create' && <>
          <div>Use existing record · No new entry</div>
          <ToggleField label="Correct record selected" checked={approval === o.id} onChange={v => setApproval(v ? o.id : undefined)} />
          <ButtonItem disabled={busy || !submission || approval !== o.id} onClick={() => run('adopt_created_record', {id: o.id, submissionId: submission})}>Use selected record</ButtonItem>
        </>}
        {['uncertain', 'conflict'].includes(o.state) && o.kind !== 'create' && <>
          <div>Check HLTB first · Prevent lost or duplicate time</div>
          <ToggleField label="I checked HLTB" checked={approval === o.id} onChange={v => setApproval(v ? o.id : undefined)} />
          <ButtonItem disabled={busy || approval !== o.id} onClick={() => run('resolve', {id: o.id, decision: 'included'})}>Already included in HLTB</ButtonItem>
          <ButtonItem disabled={busy || approval !== o.id} onClick={() => run('resolve', {id: o.id, decision: 'not_included'})}>Not included: keep pending</ButtonItem>
        </>}
      </PanelSectionRow>)}
    </PanelSection>
    <PanelSection title="Local sessions">
      {!data?.sessions.length && <PanelSectionRow>No sessions</PanelSectionRow>}
      {data?.tracker !== 'observing' && <PanelSectionRow>Capture: {data?.tracker ?? 'Waiting'}</PanelSectionRow>}
      {data?.sessions.filter(s => !appId || s.app === appId).map(s => <PanelSectionRow key={s.id}>
        <div>{s.name}: {duration(s.elapsed)} · {states[s.state] ?? s.state} · {s.phase}</div>
        {s.reason && <div>Reason: {s.reason.replace(/_/g, ' ')}</div>}
        {s.state === 'attention' && ['restart', 'observation_gap'].includes(s.reason ?? '') && !['running', 'suspended'].includes(s.phase) &&
          <ButtonItem disabled={busy} onClick={() => run('checkpoint', {id: s.id})}>Keep saved time only</ButtonItem>}
      </PanelSectionRow>)}
    </PanelSection>
    </>}
  </>;
}

export default definePlugin(() => {
  let activePrompt: MatchPrompt | undefined;
  const openMatch = (match: MatchRequest): MatchPrompt => {
    if (activePrompt) return {closed: activePrompt.closed.then(() => false), close: () => {}};
    const prompt = showMatchDialog(match, getStatus, command);
    activePrompt = prompt;
    void prompt.closed.then(async handled => {
      if (activePrompt === prompt) activePrompt = undefined;
      if (handled && match.notice) await command('ack_match', {appId: match.app.id, notice: match.notice});
    }).catch(() => {});
    return prompt;
  };
  const stopNotices = startMatchNotices(getStatus, openMatch,
    (appId, notice) => command('ack_match', {appId, notice}), canShowMatchPrompt, async match => {
      const app = currentApp(match.app.id) ?? match.app;
      const result = await command('resolve_match', {app});
      const status = await getStatus();
      if (status.ok) {
        const operation = status.data.operations.find(o => o.app === app.id && ['prepared', 'sending', 'uncertain', 'conflict'].includes(o.state));
        if (operation) return {...match, app, operation};
      }
      if (result.ok && (result.data as {state: string}).state === 'linked') {
        toaster.toast({title: 'HLTB Sync', body: `${app.name}: synced.`});
        return null;
      }
      return {...(status.ok ? status.data.matches.find(m => m.app.id === app.id) ?? match : match), app,
        issue: result.ok ? 'No unique match. Search by title below.' : 'Automatic sync needs attention. Your time is saved.'};
    });
  const openReview = (operation: Operation): MatchPrompt => {
    if (activePrompt) return {closed: activePrompt.closed.then(() => false), close: () => {}};
    const prompt = showUpdateDialog(operation, getStatus, command);
    activePrompt = prompt;
    void prompt.closed.then(() => {if (activePrompt === prompt) activePrompt = undefined;});
    return prompt;
  };
  const openCheckpoint = (session: Session): MatchPrompt => {
    if (activePrompt) return {closed: activePrompt.closed.then(() => false), close: () => {}};
    const prompt = showCheckpointDialog(session, command);
    activePrompt = prompt;
    void prompt.closed.then(() => {if (activePrompt === prompt) activePrompt = undefined;});
    return prompt;
  };
  const loginBrowser = createLoginBrowser(command, win => {
    if (!win.MenuStore) throw Error('Login window unavailable');
    win.MenuStore.OpenQuickAccessMenu(QuickAccessTab.Decky);
  });
  const loginReturn = createLoginReturn(getStatus, async isCurrent => {
    const ready = await loginBrowser.complete(isCurrent);
    if (ready && isCurrent()) toaster.toast({title: 'HLTB Sync', body: 'Connected.'});
    return ready;
  }, Date.now, () => {
    loginBrowser.cancelPending();
    toaster.toast({title: 'HLTB Sync', body: 'Login return timed out. Sessions saved.'});
  });
  const stopRecovery = startLoginRecovery(async () => {
    const result = await getStatus();
    if (result.ok && loginReturn.active()) return {ok: true, data: {...result.data, canRestore: false}};
    return result;
  }, loginBrowser.restore);
  let notified = false;
  const stop = startTracker(observe, () => {
    if (!notified) { notified = true; toaster.toast({title: 'HLTB Sync', body: 'Session capture needs attention. Open the plugin to review.'}); }
  });
  return { name: 'HLTB Sync for Deck', titleView: <div style={{flex: 1}}>HLTB Sync</div>, content: <Content loginReturn={loginReturn} cancelRestore={loginBrowser.cancelPending} rememberLoginWindow={loginBrowser.rememberLoginWindow} openMatch={openMatch} openReview={openReview} openCheckpoint={openCheckpoint} />,
    icon: <span>◷</span>, onDismount: () => { stopRecovery(); loginReturn.cancel(); loginBrowser.dispose(); stopNotices(); activePrompt?.close(); stop(); } };
});
