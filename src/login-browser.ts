import type { Result } from './types';

type View = { SetVisible(visible: boolean): void; SetFocus(focused: boolean): void };
type WindowInstance = {
  LocationPathName?: string;
  VirtualKeyboardManager?: { SetVirtualKeyboardHidden(): void };
  MenuStore?: { OpenQuickAccessMenu(tab: number): void };
  NavigateBack(): void;
};
type Runtime = {
  SteamClient?: { BrowserView?: {
    Create(options: { strInitialURL: string; bOnlyAllowTrustedPopups: boolean }): View;
    Destroy(view: View): void;
  } };
  SteamUIStore?: { RunningApps: unknown[]; GetFocusedWindowInstance(): WindowInstance | null;
    WindowStore?: { GamepadUIMainWindowInstance?: WindowInstance } };
  BrowserAndBackstackInstances?: { name: string; URL: string }[];
};
type Command = (action: string, args: Record<string, unknown>) => Promise<Result<unknown>>;
const isHLTB = (url: string) => {
  try { return new URL(url).origin === 'https://howlongtobeat.com'; } catch { return false; }
};

// Keep authenticated same-origin requests alive after Steam clears ExternalWeb.
// This view belongs to the plugin and never reads or exports cookies.
export function createLoginBrowser(command: Command, openPanel: (win: WindowInstance) => void,
  runtime: Runtime = globalThis as unknown as Runtime,
  wait: () => Promise<void> = () => new Promise(resolve => setTimeout(resolve, 500))) {
  let retained: View | undefined;
  let pending: View | undefined;
  let disposed = false;
  let generation = 0;
  let returnPending = false;
  let loginWindow: WindowInstance | undefined;
  let navigatedWindow: WindowInstance | undefined;
  let returnRoute: string | undefined;
  const api = runtime.SteamClient?.BrowserView;
  const destroy = (view?: View) => { if (view) api?.Destroy(view); };
  const finishReturn = async (valid: () => boolean): Promise<boolean> => {
    if (!valid()) return false;
    const store = runtime.SteamUIStore;
    const focused = store?.GetFocusedWindowInstance();
    const win = loginWindow ?? focused;
    const external = runtime.BrowserAndBackstackInstances?.find(b => b.name === 'ExternalWeb');
    // Missing window metadata may be temporary; do not silently claim UI success.
    if (!store || !win || !Array.isArray(store.RunningApps)) return false;
    if (store.RunningApps.length || (focused && focused !== win)) {
      returnPending = false;
      return true;
    }
    if (navigatedWindow === win && win.LocationPathName !== '/externalweb') {
      if (returnRoute !== '/externalweb' && win.LocationPathName !== returnRoute) {
        returnPending = false;
        return true;
      }
      openPanel(win);
      returnPending = false;
      return true;
    }
    if (win.LocationPathName !== '/externalweb') { returnPending = false; return true; }
    if (!external) return false;
    if (!isHLTB(external.URL)) { returnPending = false; return true; }
    win.VirtualKeyboardManager?.SetVirtualKeyboardHidden();
    win.NavigateBack();
    navigatedWindow = win;
    const routeAfterBack = win.LocationPathName;
    returnRoute = routeAfterBack;
    await wait();
    if (!valid()) return false;
    if (store.RunningApps.length) { returnPending = false; return true; }
    if (win.LocationPathName === '/externalweb') return false;
    if (routeAfterBack !== '/externalweb' && win.LocationPathName !== routeAfterBack) {
      returnPending = false;
      return true;
    }
    const focusedAfterBack = store.GetFocusedWindowInstance();
    if (!focusedAfterBack || focusedAfterBack === win) openPanel(win);
    returnPending = false;
    return true;
  };
  const complete = async (silent = false, isCurrent: () => boolean = () => true): Promise<boolean> => {
    if (!api || disposed) return false;
    const current = ++generation;
    const valid = () => !disposed && current === generation && isCurrent();
    if (!valid()) return false;
    if (!silent && returnPending) return finishReturn(valid);
    if (!silent && !loginWindow) loginWindow = runtime.SteamUIStore?.GetFocusedWindowInstance() ?? undefined;
    const prepared = await command(silent ? 'prepare_restore' : 'prepare_background', {});
    if (!prepared.ok || !valid()) return false;
    const url = (prepared.data as {url?: string})?.url;
    if (!url || !isHLTB(url)) return false;
    const view = api.Create({strInitialURL: url, bOnlyAllowTrustedPopups: true});
    pending = view;
    view.SetVisible(false);
    view.SetFocus(false);
    let verified = false;
    try {
      for (let attempt = 0; attempt < 20 && valid(); attempt++) {
        await wait();
        if (!valid()) break;
        const result = await command('retain_background', {});
        if (result.ok && result.data === true) { verified = true; break; }
        if (!result.ok && !['login_window_not_found', 'network_or_session_error',
          'login_required', 'hltb_http_error'].includes(result.error)) break;
      }
      if (!verified || !valid()) return false;
      destroy(retained);
      retained = view;
      pending = undefined;
      if (silent) return true;
      returnPending = true;
      return await finishReturn(valid);
    } finally {
      if (pending === view) { pending = undefined; destroy(view); }
    }
  };
  const cancelPending = () => {
    generation++; returnPending = false; loginWindow = navigatedWindow = undefined; returnRoute = undefined;
    destroy(pending); pending = undefined;
  };
  const rememberLoginWindow = () => {
    const store = runtime.SteamUIStore;
    loginWindow = store?.GetFocusedWindowInstance() ?? store?.WindowStore?.GamepadUIMainWindowInstance;
    navigatedWindow = undefined; returnRoute = undefined;
  };
  return { complete: (isCurrent?: () => boolean) => complete(false, isCurrent), restore: () => complete(true),
    rememberLoginWindow, cancelPending, dispose: () => {
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
