import type { Result, Status } from './types';

// Owned by the plugin, not its panel: closing the panel must not stop login.
export function createLoginReturn(read: () => Promise<Result<Status>>, complete: () => void | Promise<void>,
  now: () => number = Date.now) {
  let generation = 0;
  let timer: ReturnType<typeof setInterval> | undefined;
  const cancel = () => {
    generation++;
    if (timer !== undefined) clearInterval(timer);
    timer = undefined;
  };
  const begin = () => {
    cancel();
    const current = generation;
    const deadline = now() + 300_000;
    let busy = false;
    timer = setInterval(async () => {
      if (now() >= deadline) { cancel(); return; }
      if (busy) return;
      busy = true;
      try {
        const result = await read();
        if (current !== generation) return;
        if (result.ok && result.data.auth === 'connected' && !result.data.libraryCached) {
          cancel();
          await complete();
        } else if (result.ok && result.data.auth === 'disconnected') cancel();
      } catch { /* A temporary RPC failure must not interrupt authentication. */ }
      finally { busy = false; }
    }, 1000);
  };
  return { begin, cancel };
}
