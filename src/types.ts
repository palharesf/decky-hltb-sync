export type App = { id: string; name: string; steam: boolean; minutes: number | null };
export type Session = { id: string; app: string; name: string; elapsed: number; state: string; phase: string; reason: string | null };
export type Entry = { submissionId: number; gameId: number; title: string; platform: string; seconds: number; lists: string[] | Record<string, boolean> };
export type Mapping = Entry & { app: string; mode: string; automatic: boolean };
export type Operation = { id: string; app: string; kind: string; state: string; title: string; platform: string; before: number; after: number; resolution: string | null };
export type SearchResult = { gameId: number; title: string; main: number; extra: number; completionist: number };
export type Status = { auth: string; error: string | null; mappings: Mapping[]; sessions: Session[]; operations: Operation[]; library: Entry[]; libraryCached: boolean; tracker: string };
export type Result<T> = { ok: true; data: T } | { ok: false; error: string };
