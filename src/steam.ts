import type { App, Result } from './types';

type Overview = { appid: number; display_name: string; app_type: number; minutes_playtime_forever?: number };
type Subscription = { unregister(): void };
type Runtime = {
  appStore?: { allApps: Overview[]; GetAppOverviewByAppID(id: number): Overview | undefined };
  SteamUIStore?: { RunningApps: { appid: number; display_name: string }[] };
  SteamClient?: { User?: {
    RegisterForPrepareForSystemSuspendProgress?: (callback: () => void) => Subscription;
    RegisterForResumeSuspendedGamesProgress?: (callback: () => void) => Subscription;
  }; System?: {
    RegisterForOnSuspendRequest?: (callback: () => void) => Subscription;
    RegisterForOnResumeFromSuspend?: (callback: () => void) => Subscription;
  } };
};
const runtime = () => globalThis as unknown as Runtime;

function convert(app: Overview): App {
  const minutes = app.minutes_playtime_forever;
  return { id: String(app.appid >>> 0), name: app.display_name,
    steam: app.app_type !== 1073741824,
    minutes: Number.isInteger(minutes) && minutes! >= 0 ? minutes! : null };
}

export function libraryApps(query: string): App[] {
  const all = runtime().appStore?.allApps;
  if (!Array.isArray(all)) return [];
  return all.filter(a => a.display_name?.toLowerCase().includes(query.toLowerCase()))
    .slice(0, 50).map(convert);
}

export function currentApp(id: string): App | undefined {
  const app = runtime().appStore?.GetAppOverviewByAppID(Number(id));
  return app ? convert(app) : undefined;
}

type Event = 'snapshot' | 'suspend' | 'resume' | 'unavailable';
type Send = (epoch: string, sequence: number, apps: App[], event: Event) => Promise<Result<null>>;

export function startTracker(send: Send, onError: () => void): () => void {
  const epoch = crypto.randomUUID();
  let sequence = 0;
  let disposed = false;
  let chain: Promise<void> = Promise.resolve();
  let failed = false;
  let queued = 0;
  const subscriptions: Subscription[] = [];
  function enqueue(event: Event) {
    if (disposed) return;
    if (queued > 2 && event === 'snapshot') { failed = true; return; }
    queued++;
    chain = chain.then(async () => {
      if (disposed) return;
      try {
        if (failed) {
          const reset = await send(epoch, sequence++, [], 'unavailable');
          if (!reset.ok) throw Error();
          failed = false;
        }
        const running = runtime().SteamUIStore?.RunningApps;
        const apps = Array.isArray(running) ? running.map(a => {
          const overview = runtime().appStore?.GetAppOverviewByAppID(a.appid);
          if (!overview) throw Error();
          return convert(overview);
        }) : [];
        const result = await send(epoch, sequence++, apps, Array.isArray(running) ? event : 'unavailable');
        if (!result.ok) throw Error();
      } catch { failed = true; onError(); }
      finally { queued--; }
    });
  }
  const system = runtime().SteamClient?.System;
  const user = runtime().SteamClient?.User;
  try {
    if (system?.RegisterForOnSuspendRequest && system.RegisterForOnResumeFromSuspend) {
      subscriptions.push(system.RegisterForOnSuspendRequest(() => enqueue('suspend')));
      subscriptions.push(system.RegisterForOnResumeFromSuspend(() => enqueue('resume')));
    } else if (user?.RegisterForPrepareForSystemSuspendProgress && user.RegisterForResumeSuspendedGamesProgress) {
      subscriptions.push(user.RegisterForPrepareForSystemSuspendProgress(() => enqueue('suspend')));
      subscriptions.push(user.RegisterForResumeSuspendedGamesProgress(() => enqueue('resume')));
    } else {
      onError();
      void send(epoch, sequence++, [], 'unavailable').catch(onError);
      return () => { disposed = true; };
    }
  } catch {
    for (const subscription of subscriptions) subscription.unregister();
    onError();
    return () => { disposed = true; };
  }
  const interval = setInterval(() => enqueue('snapshot'), 5000);
  enqueue('snapshot');
  return () => {
    disposed = true;
    clearInterval(interval);
    for (const subscription of subscriptions) subscription.unregister();
    void send(epoch, sequence++, [], 'unavailable').catch(onError);
  };
}
