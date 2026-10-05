import { DialogBody, DialogButton, DialogFooter, DialogHeader, DropdownItem, Focusable,
  ModalRoot, TextField, ToggleField, showModal } from '@decky/ui';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Entry, MatchRequest, Operation, Result, Status, Session } from './types';
import type { MatchPrompt } from './match-notices';
import { currentApp } from './steam';
import { createUpdateReview, type ReviewState } from './update-review';

type Command = (action: string, args: Record<string, unknown>) => Promise<Result<unknown>>;
type Props = { match: MatchRequest; read: () => Promise<Result<Status>>; command: Command; finish(): void };
const duration = (seconds: number) => `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m ${Math.floor(seconds % 60)}s`;

function ActionRow({children}: {children: ReactNode}) {
  return <DialogFooter>
    <Focusable flow-children="row" style={{display: 'flex', gap: 12, width: '100%'}}>
      {children}
    </Focusable>
  </DialogFooter>;
}

function CheckpointDialog({session, command, finish}: {session: Session; command: Command; finish(): void}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [discard, setDiscard] = useState(false);
  const pending = useRef(false);
  const close = () => {if (!pending.current) {if (discard) setDiscard(false); else finish();}};
  const confirm = async (action: 'checkpoint' | 'discard_checkpoint') => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try {
      const result = await command(action, {id: session.id});
      if (result.ok) { finish(); return; }
      setError('Could not save your choice. Check the session status.');
    } catch { setError('Connection interrupted. Check the session status.'); }
    finally {pending.current = false; setBusy(false);}
  };
  return <ModalRoot onCancel={close} closeModal={close} bCancelDisabled={busy}
    bDisableBackgroundDismiss bHideCloseIcon={busy}>
    <DialogHeader>{discard ? 'Discard session?' : 'Recover session'}</DialogHeader>
    <DialogBody style={{display: 'flex', flexDirection: 'column', gap: 12}}>
      <div style={{fontSize: 22, fontWeight: 600}}>{session.name}</div>
      <div>Saved: {duration(session.elapsed)}</div>
      <div>{discard ? 'This saved time will not be sent. Existing HLTB time stays unchanged.'
        : 'Tracking was interrupted. Only the saved time can be synced.'}</div>
      {error && <div role="alert">{error}</div>}
    </DialogBody>
    <ActionRow>
      {discard ? <>
        <DialogButton disabled={busy} onClick={() => setDiscard(false)}>Back</DialogButton>
        <DialogButton disabled={busy} onClick={() => void confirm('discard_checkpoint')}>{busy ? 'Saving…' : 'Confirm discard'}</DialogButton>
      </> : <>
        <DialogButton disabled={busy} onClick={() => void confirm('checkpoint')}>{busy ? 'Saving…' : 'Sync recovered time'}</DialogButton>
        <DialogButton disabled={busy} onClick={() => {setError(''); setDiscard(true);}}>Discard session</DialogButton>
      </>}
    </ActionRow>
  </ModalRoot>;
}

export function showCheckpointDialog(session: Session, command: Command): MatchPrompt {
  let settle: (handled: boolean) => void = () => {};
  const closed = new Promise<boolean>(resolve => {settle = resolve;});
  const modal = showModal(<CheckpointDialog session={session} command={command}
    finish={() => {settle(true); modal.Close();}} />, undefined,
  {strTitle: 'HLTB Sync', bNeverPopOut: true, fnOnClose: () => settle(false)});
  return {closed, close: () => {settle(false); modal.Close();}};
}

function UpdateDialog({operation, read, command, finish, autoStart = false}: {
  operation: Operation; read: Props['read']; command: Command; finish(): void; autoStart?: boolean;
}) {
  const [state, setState] = useState<ReviewState>({phase: operation.state === 'verified' ? 'verified'
    : operation.state === 'prepared' ? 'prepared' : 'attention', busy: false, message: ''});
  const mounted = useRef(true);
  const [review] = useState(() => createUpdateReview(operation, command, read, next => {
    if (mounted.current) setState(next);
  }));
  useEffect(() => () => {mounted.current = false;}, []);
  useEffect(() => {if (autoStart) void review.send(true);}, []);
  const later = () => {if (!review.state().busy) finish();};
  return <ModalRoot onCancel={later} closeModal={later} bCancelDisabled={state.busy}
    bDisableBackgroundDismiss bHideCloseIcon={state.busy}>
    <DialogHeader>{state.phase === 'verified' ? 'Synced' : 'Review HLTB update'}</DialogHeader>
    <DialogBody style={{display: 'flex', flexDirection: 'column', gap: 12}}>
      <div style={{fontSize: 22, fontWeight: 600}}>{operation.title} · {operation.platform}</div>
      <div>HLTB: {duration(operation.before)} → {duration(operation.after)}</div>
      {operation.kind === 'history_import' && <div>One-time import. Saved sessions are included in this total.</div>}
      {state.phase === 'prepared' && <div>Confirm sends this total. Future sessions sync automatically.</div>}
      {state.message && <div role="status">{state.message}</div>}
    </DialogBody>
    <ActionRow>
      {state.phase === 'prepared' && <DialogButton disabled={state.busy}
        onClick={() => void review.send(true)}>Confirm and sync</DialogButton>}
      {state.phase === 'sending' && <DialogButton disabled>Sending…</DialogButton>}
      {state.phase === 'attention' && <DialogButton disabled={state.busy}
        onClick={() => void review.check()}>Check status</DialogButton>}
      <DialogButton disabled={state.busy} onClick={later}>{state.phase === 'verified' ? 'Done' : 'Later'}</DialogButton>
    </ActionRow>
  </ModalRoot>;
}

function MatchDialog({ match, read, command, finish }: Props) {
  const [selected, setSelected] = useState<number | undefined>(match.recommended ?? undefined);
  const [choosing, setChoosing] = useState(!match.recommended);
  const [entries, setEntries] = useState<Entry[]>(match.candidates);
  const [search, setSearch] = useState(match.app.name);
  const [busy, setBusy] = useState(false);
  const [linked, setLinked] = useState(false);
  const [proposal, setProposal] = useState<Operation>();
  const [error, setError] = useState('');
  const [importHistory, setImportHistory] = useState(false);
  const [totalMinutes, setTotalMinutes] = useState(String(currentApp(match.app.id)?.minutes ?? ''));
  const mounted = useRef(true);
  const pending = useRef(false);
  useEffect(() => {
    void read().then(result => {
      if (!mounted.current || !result.ok) return;
      const ids = new Set(match.candidates.map(e => e.submissionId));
      setEntries([...match.candidates, ...result.data.library.filter(e => !ids.has(e.submissionId))]);
    }).catch(() => {});
    return () => { mounted.current = false; };
  }, []);
  const candidate = entries.find(e => e.submissionId === selected);
  const later = () => { if (!pending.current) finish(); };
  const confirm = async () => {
    if (pending.current || linked || !candidate || (importHistory && !/^[1-9]\d*$/.test(totalMinutes))) return;
    pending.current = true; setBusy(true); setError('');
    try {
      const result = await command('bind', {app: match.app, submissionId: candidate.submissionId, mode: 'sessions'});
      if (!mounted.current) return;
      if (!result.ok) {
        setError('Could not confirm the match. Your time is saved. Reconnect or review it in HLTB Sync.');
        return;
      }
      setLinked(true);
      const preview = importHistory
        ? await command('preview_import', {appId: match.app.id, totalMinutes: Number(totalMinutes), includesSaved: true})
        : await command('preview', {appId: match.app.id});
      if (!mounted.current) return;
      if (preview.ok) setProposal(preview.data as Operation);
      else setError('Match saved. Use Review update to prepare or recover the preview here.');
    } catch {
      if (mounted.current) setError('Connection interrupted. Review the match in HLTB Sync. Your time is saved.');
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const retryPreview = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError('');
    try {
      const status = await read();
      if (!mounted.current) return;
      const existing = status.ok ? status.data.operations.find(o => o.app === match.app.id &&
        ['prepared', 'sending', 'uncertain', 'conflict'].includes(o.state)) : undefined;
      if (existing) {setProposal(existing); return;}
      const result = importHistory
        ? await command('preview_import', {appId: match.app.id, totalMinutes: Number(totalMinutes), includesSaved: true})
        : await command('preview', {appId: match.app.id});
      if (mounted.current) {
        if (result.ok) setProposal(result.data as Operation);
        else setError('Could not prepare the update. Your session is still saved.');
      }
    } catch {if (mounted.current) setError('Connection interrupted. Your session is saved.');}
    finally {pending.current = false; if (mounted.current) setBusy(false);}
  };
  if (proposal) return <UpdateDialog operation={proposal} read={read} command={command} finish={finish} autoStart />;
  return <ModalRoot onCancel={later} closeModal={later} bCancelDisabled={busy}
    bDisableBackgroundDismiss bHideCloseIcon={busy}>
    <DialogHeader>{linked ? 'Match saved' : 'Confirm HLTB match'}</DialogHeader>
    <DialogBody style={{display: 'flex', flexDirection: 'column', gap: 12}}>
      <div style={{fontSize: 22, fontWeight: 600, overflowWrap: 'anywhere'}}>{match.app.name}</div>
      <div>{match.app.platform ?? 'Platform unknown'} · Unsynced time: {duration(match.seconds)}</div>
      {linked ? <>
        <div>No hours sent. Prepare a preview to approve here.</div>
      </> : <>
        {!choosing && candidate && <>
          <div style={{fontWeight: 600}}>Suggested: {candidate.title} · {candidate.platform}</div>
          <div>HLTB time: {duration(candidate.seconds)}</div>
        </>}
        {match.issue && <div role="status">{match.issue}</div>}
        {choosing && <TextField label="Search your HLTB records" value={search}
          onChange={e => setSearch(e.target.value)} />}
        {choosing && <DropdownItem label="HLTB record" layout="below" childrenContainerWidth="max"
          selectedOption={selected} strDefaultLabel="Choose record" disabled={busy}
          rgOptions={entries.filter(e => e.title.toLowerCase().includes(search.toLowerCase())).slice(0,20)
            .map(e => ({data: e.submissionId, label: `${e.title} · ${e.platform}`}))}
          onChange={o => setSelected(o.data)} />}
        {!entries.length && <div>No account records available. Use HLTB Sync to connect or search.</div>}
        <ToggleField label="Import past hours once" checked={importHistory} disabled={busy}
          description="This total includes saved sessions. Future sessions add normally."
          onChange={setImportHistory} />
        {importHistory && <TextField label="Lifetime total (minutes)" mustBeNumeric disabled={busy}
          value={totalMinutes} onChange={e => setTotalMinutes(e.target.value)}
          description="Check this value. It replaces HLTB playtime; it is not added on top." />}
        {candidate && <div>HLTB: {duration(candidate.seconds)} → {duration(importHistory ? Number(totalMinutes) * 60 || 0 : candidate.seconds + match.seconds)}</div>}
        <div>Confirm links and syncs. Future sessions sync automatically.</div>
      </>}
      {error && <div role="alert">{error}</div>}
    </DialogBody>
    <ActionRow>
      {linked ? <DialogButton disabled={busy} onClick={() => void retryPreview()}>Sync saved update</DialogButton> : <>
        <DialogButton disabled={busy || !candidate || (importHistory && !/^[1-9]\d*$/.test(totalMinutes))} onClick={() => void confirm()}>{busy ? 'Checking…' : 'Confirm and sync'}</DialogButton>
        <DialogButton disabled={busy} onClick={() => setChoosing(true)}>Choose another</DialogButton>
      </>}
      <DialogButton disabled={busy} onClick={later}>Later</DialogButton>
    </ActionRow>
  </ModalRoot>;
}

export function showMatchDialog(match: MatchRequest, read: Props['read'], command: Command): MatchPrompt {
  let settle: (handled: boolean) => void = () => {};
  let aborted = false;
  const closed = new Promise<boolean>(resolve => {settle = resolve;});
  const finish = () => {settle(true); modal.Close();};
  const modal = showModal(match.operation
    ? <UpdateDialog operation={match.operation} read={read} command={command} finish={finish} />
    : <MatchDialog match={match} read={read} command={command} finish={finish} />, undefined,
  {strTitle: 'HLTB Sync', bNeverPopOut: true, fnOnClose: () => settle(!aborted)});
  return {closed, close: () => {aborted = true; settle(false); modal.Close();}};
}

export function showUpdateDialog(operation: Operation, read: Props['read'], command: Command): MatchPrompt {
  let settle: (handled: boolean) => void = () => {};
  let aborted = false;
  const closed = new Promise<boolean>(resolve => {settle = resolve;});
  const modal = showModal(<UpdateDialog operation={operation} read={read} command={command}
    finish={() => {settle(true); modal.Close();}} />, undefined,
  {strTitle: 'HLTB Sync', bNeverPopOut: true, fnOnClose: () => settle(!aborted)});
  return {closed, close: () => {aborted = true; settle(false); modal.Close();}};
}
