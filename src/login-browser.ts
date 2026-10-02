import type { Result } from './types';

type View = { SetVisible(visible: boolean): void; SetFocus(focused: boolean): void };
type WindowInstance = {
  LocationPathName?: string;
  VirtualKeyboardManager?: { SetVirtualKeyboardHidden(): void };
  NavigateBack(): void;
};
type Runtime = {
  SteamClient?: { BrowserView?: {
    Create(options: { strInitialURL: string; bOnlyAllowTrustedPopups: boolean }): View;
    Destroy(view: View): void;
  } };
  SteamUIStore?: { RunningApps: unknown[]; GetFocusedWindowInstance(): WindowInstance };
  BrowserAndBackstackInstances?: { name: string; URL: string }[];
};
type Command = (action: string, args: Record<string, unknown>) => Promise<Result<unknown>>;
const isHLTB = (url: string) => {
  try { return new URL(url).origin === 'https://howlongtobeat.com'; } catch { return false; }
};

// Keep authenticated same-origin requests alive after Steam clears ExternalWeb.
// This view belongs to the plugin and never reads or exports cookies.
export function createLoginBrowser(command: Command, openPanel: () => void,
  runtime: Runtime = globalThis as unknown as Runtime,
  wait: () => Promise<void> = () => new Promise(resolve => setTimeout(resolve, 500))) {
  let retained: View | undefined;
  let pending: View | undefined;
  let disposed = false;
  let generation = 0;
  const api = runtime.SteamClient?.BrowserView;
  const destroy = (view?: View) => { if (view) api?.Destroy(view); };
  const complete = async (silent = false): Promise<boolean> => {
    if (!api || disposed) return false;
    const current = ++generation;
    const prepared = await command(silent ? 'prepare_restore' : 'prepare_background', {});
    if (!prepared.ok || disposed || current !== generation) return false;
    const url = (prepared.data as {url?: string})?.url;
    if (!url || !isHLTB(url)) return false;
    const view = api.Create({strInitialURL: url, bOnlyAllowTrustedPopups: true});
    pending = view;
    view.SetVisible(false);
    view.SetFocus(false);
    let verified = false;
    try {
      for (let attempt = 0; attempt < 20 && !disposed && current === generation; attempt++) {
        await wait();
        if (disposed || current !== generation) break;
        const result = await command('retain_background', {});
        if (result.ok && result.data === true) { verified = true; break; }
        if (!result.ok && !['login_window_not_found', 'network_or_session_error',
          'login_required', 'hltb_http_error'].includes(result.error)) break;
      }
      if (!verified || disposed || current !== generation) return false;
      destroy(retained);
      retained = view;
      pending = undefined;
      const store = runtime.SteamUIStore;
      const win = store?.GetFocusedWindowInstance();
      const external = runtime.BrowserAndBackstackInstances?.find(b => b.name === 'ExternalWeb');
      // Do not pull the user out of a game or a screen they opened meanwhile.
      if (!silent && store?.RunningApps.length === 0 && win?.LocationPathName === '/externalweb'
        && external && isHLTB(external.URL)) {
        win.VirtualKeyboardManager?.SetVirtualKeyboardHidden();
        win.NavigateBack();
        await wait();
        if (!disposed && store.RunningApps.length === 0) openPanel();
      }
      return true;
    } finally {
      if (pending === view) { pending = undefined; destroy(view); }
    }
  };
  const cancelPending = () => {generation++; destroy(pending); pending = undefined;};
  return { complete: () => complete(false), restore: () => complete(true), cancelPending, dispose: () => {
    disposed = true;
    cancelPending(); destroy(retained);
    pending = retained = undefined;
  } };
}

export function startLoginRecovery(read: () => Promise<Result<{auth: string; canRestore?: boolean}>>,
  restore: () => Promise<boolean>) {
  let disposed = false, busy = false;
  const poll = async () => {
    if (disposed || busy) return;
    busy = true;
    try {
      const result = await read();
      if (!disposed && result.ok && result.data.canRestore &&
        !['connected', 'connecting'].includes(result.data.auth)) await restore();
    } catch { /* Startup/network failures retry without opening any visible UI. */ }
    finally { busy = false; }
  };
  const timer = setInterval(() => void poll(), 30_000);
  void poll();
  return () => {disposed = true; clearInterval(timer);};
}
