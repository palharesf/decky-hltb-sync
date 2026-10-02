import type { Operation, Result, Status } from './types';

export type ReviewCommand = (action: string, args: Record<string, unknown>) => Promise<Result<unknown>>;
export type ReviewState = { phase: 'prepared' | 'sending' | 'verified' | 'attention'; busy: boolean; message: string };

// One submission attempt per dialog. An uncertain response only permits checks.
export function createUpdateReview(operation: Operation, command: ReviewCommand,
  read: () => Promise<Result<Status>>, changed: (state: ReviewState) => void) {
  let attempted = operation.state !== 'prepared';
  let state: ReviewState = {phase: operation.state === 'verified' ? 'verified'
    : operation.state === 'prepared' ? 'prepared' : 'attention', busy: false, message: ''};
  const publish = (next: Partial<ReviewState>) => {state = {...state, ...next}; changed({...state});};
  const inspect = async (reconcile: boolean) => {
    let result = await read();
    let current = result.ok ? result.data.operations.find(o => o.id === operation.id) : undefined;
    if (reconcile && current?.state === 'uncertain') {
      await command('reconcile', {id: operation.id});
      result = await read();
      current = result.ok ? result.data.operations.find(o => o.id === operation.id) : undefined;
    }
    if (current?.state === 'verified') publish({phase: 'verified', message: 'Saved and verified on HLTB.'});
    else publish({phase: 'attention', message: current?.state === 'conflict'
      ? 'HLTB changed. Nothing is being resent.' : 'Not yet verified. Check status; do not resend.'});
  };
  return {
    state: () => ({...state}),
    send: async (approved: boolean) => {
      if (!approved || attempted || state.busy || state.phase !== 'prepared') return;
      attempted = true;
      publish({phase: 'sending', busy: true, message: 'Sending and verifying…'});
      try {
        const result = await command('send', {id: operation.id, approved: true, enableAutomatic: true});
        if (result.ok && result.data === true) publish({phase: 'verified', message: 'Saved and verified on HLTB.'});
        else await inspect(false);
      } catch {publish({phase: 'attention', message: 'Connection interrupted. Check status; do not resend.'});}
      finally {publish({busy: false});}
    },
    check: async () => {
      if (state.busy || state.phase === 'verified') return;
      publish({busy: true});
      try {await inspect(true);}
      catch {publish({phase: 'attention', message: 'Could not check HLTB. Your update is saved locally.'});}
      finally {publish({busy: false});}
    },
  };
}
