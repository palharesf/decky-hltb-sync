import type { Result, Status } from './types';

// Owned by the plugin, not its panel: closing the panel must not stop login.
export function createLoginReturn(read: () => Promise<Result<Status>>,
  complete: (isCurrent: () => boolean) => Promise<boolean>,
  now: () => number = Date.now, onTimeout: () => void = () => {}) {
  let generation = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  let busy = false;
  const cancel = () => {
    generation++;
    if (timer !== undefined) clearInterval(timer);
    timer = undefined;
  };
  const begin = () => {
    cancel();
    const current = generation;
    const loginDeadline = now() + 300_000;
    let returnDeadline: number | undefined;
    let retryAt = 0;
    const isCurrent = () => current === generation && timer !== undefined;
    timer = setInterval(async () => {
      if (!isCurrent()) return;
      if (now() >= (returnDeadline ?? loginDeadline)) { cancel(); onTimeout(); return; }
      if (busy || now() < retryAt) return;
      busy = true;
      try {
        const result = await read();
        if (!isCurrent()) return;
        if (now() >= (returnDeadline ?? loginDeadline)) { cancel(); onTimeout(); return; }
        if (result.ok && result.data.auth === 'connected' && !result.data.libraryCached) {
          returnDeadline ??= now() + 120_000;
          retryAt = now() + 5000;
          const done = await complete(isCurrent);
          if (isCurrent() && done) cancel();
        } else if (result.ok && result.data.auth === 'disconnected') cancel();
      } catch { /* A temporary RPC failure must not interrupt authentication. */ }
      finally { busy = false; }
    }, 1000);
  };
  return { begin, cancel, active: () => timer !== undefined };
}
