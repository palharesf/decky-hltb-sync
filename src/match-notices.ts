import type { MatchRequest, Result, Status } from './types';

export type MatchPrompt = { closed: Promise<boolean>; close(): void };

// Keep this alive while the panel is closed. The backend persists unread matches.
export function startMatchNotices(read: () => Promise<Result<Status>>,
  show: (match: MatchRequest) => MatchPrompt,
  acknowledge: (appId: string, notice: string) => Promise<unknown>, canPresent: () => boolean = () => true,
  resolve?: (match: MatchRequest) => Promise<MatchRequest | null>) {
  let disposed = false, busy = false;
  let active: MatchPrompt | undefined;
  const shown = new Set<string>();
  const poll = async () => {
    if (disposed || busy || !canPresent()) return;
    busy = true;
    try {
      const result = await read();
      if (disposed || !result.ok || !canPresent()) return;
      if (resolve && result.data.auth !== 'connected') return;
      if (result.data.sessions?.some(s => ['running', 'suspended'].includes(s.phase))) return;
      for (const match of result.data.matches ?? []) {
        const noticeKey = match.notice ?? (resolve ? 'pending:' + match.app.id : null);
        if (!noticeKey || shown.has(noticeKey)) continue;
        const unresolved = resolve ? await resolve(match) : match;
        if (disposed || !canPresent()) return;
        if (!unresolved) return;
        active = show(unresolved);
        const handled = await active.closed;
        active = undefined;
        if (disposed || !handled) return;
        shown.add(noticeKey);
        if (match.notice) await acknowledge(match.app.id, match.notice);
        return; // Re-read state before opening the next dialog, never stack them.
      }
    } catch { /* Offline capture continues; the pending card remains available. */ }
    finally { busy = false; }
  };
  const timer = setInterval(() => void poll(), 3000);
  void poll();
  return () => { disposed = true; clearInterval(timer); active?.close(); };
}
