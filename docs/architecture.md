# Architecture and synchronization policy

## Components

| Component | Responsibility |
| --- | --- |
| src/index.tsx | Account, mapping, previews, approval, reconciliation and sessions UI |
| src/steam.ts | Steam library, lifetime minutes, running apps, suspend/resume |
| main.py | Allowlisted RPC, serialized account operations and background worker |
| browser.py | Standard-library CDP client connected to Steam's loopback CEF |
| client.py | HLTB identity, personal library, search, edit read and submit |
| service.py | Mapping, capture, proposals, creation, reconciliation and auto policy |
| records.py | Lossless edit-data parsing and progress-only changes |
| store.py | SQLite ledger, schema migration and recovery |
| sync.py | Original synchronous protocol retained for regression tests/demo |

## Authentication

Connect snapshots existing browser targets and opens the official HTTPS login
page through Decky's Navigation.NavigateToExternalWeb. A random fragment marks
the request. Only a marked target or a new HLTB target opened during the
five-minute connection window can be bound; ambiguity is rejected. The backend
checks identity and library while the user signs in directly on the website.
It never reads password fields or exports cookies.

The target ID is persisted privately. Reuse is limited to that exact target and
HLTB origin, checked again inside each request. After explicit login, the plugin
creates a hidden Steam browser view and verifies the same account before
closing the visible login page. It hides the keyboard and reopens its panel only
while the user is still on the HLTB page and no game is running. Restart recovery
recreates the hidden view silently when the persisted login remains valid.
Disconnect forgets the target and disables automatic sync, but does not log out
of the website. This is not a separate browser profile.

The login watcher stays active until the handoff and UI return succeed.
Transient failures retry serially, at most once every five seconds, within a
two-minute return window after a fresh authenticated status is observed. Login
itself has a five-minute window. A deadline invalidates late results; it does not
launch overlapping commands when an earlier request remains outstanding.
Timeout produces one short notification. No login form or HLTB account write is
resent by this recovery mechanism. A verified hidden view is reused when only
navigation or window metadata needs another attempt. New connection attempts,
disconnect and unload invalidate stale returns. Background startup recovery is
suppressed while explicit login return is active. User navigation and game
launches prevent focus theft.

CEF uses the existing loopback port 8080 mechanism used by Decky. WebSocket
addresses are restricted to localhost/127.0.0.1:8080. Handshakes, message size and
deadlines are checked. HLTB fetches use same-origin credentials, no redirects
and a timeout. Responses and raw exceptions are never logged.

## Data and identity

SQLite schema 2 migrates original mappings/jobs without dropping sessions.
Tables: mappings, apps, sessions, events, operations, preferences and legacy
jobs. WAL and synchronous FULL are enabled. On Linux, the private directory is
0700 and the database 0600.

Mapping binds a local AppID to a complete remote snapshot containing account,
game, submission and platform identity. Direct game sessions are tracked before
mapping. Known launcher/desktop shortcuts are excluded, including ES-DE.
Multiple shortcuts sharing a submission and remapping are not yet supported.
Platform hints come from shortcut metadata: supported ROM directories and
direct PCSX2 launches. Paths and arguments are inspected in frontend memory,
never sent to the backend or persisted. Only the platform and hint source are
stored. Conflicting hints stay unknown. Catalog estimates remain distinct from
personal progress.

After an unlinked game closes, its local session remains durable. A plugin-lifetime
poller first resolves it against a fresh account library. A unique exact normalized
title/platform record is linked automatically. Otherwise catalog candidates are
checked against the exact Steam AppID, or an exact title and inferred emulator
platform. A unique identity reuses an existing record by game ID or creates a
Playing record after duplicate checks. Ambiguous identity and errors fall back
to a native dialog. Prompts are serialized and deferred
while games are running or suspended. Dismissal acknowledges only the session
shown and never consumes sessions. Unloading closes the dialog without
acknowledging it. The pending match card remains available after dismissal.
The match dialog displays the before/after total and a single Confirm and sync
action. That explicit action links the selected record, prepares the durable
proposal and sends it without another confirmation. Success or uncertain
outcomes stay in that dialog. Check status reconciles without resubmission;
one dialog permits only one send attempt. Existing proposals can be reopened
through Review in popup. The panel is a fallback, not a required navigation step.

Library queries include all supported lists. Unknown, duplicate or truncated
responses fail closed; errors never mean an empty library. The inspected
contract has a 5,000-entry limit; larger/incomplete libraries are rejected.

## Time sources

Session capture starts at the first observation after installation. Under the
user's revised policy, automatic Steam record creation imports lifetime history
once without adding saved sessions on top. Existing records always receive
only new session deltas, including the first automatic association. Their current
HLTB progress is preserved even if Steam lifetime is lower, equal or unavailable.
Explicit manual history import remains available separately.
The frontend polls RunningApps every five seconds,
serializes observations, and subscribes to System suspend callbacks with a User
callback fallback. Missing callbacks disable capture. Suspension is not closure;
resume does not immediately interpret an empty RunningApps list as exit.

Backend Linux monotonic time excludes sleep. Gaps over 30 seconds and outages
require attention instead of estimating missing time. Reload retires the old
observation epoch. Recovery keeps the last checkpoint; explicit acceptance of
that checkpoint excludes the unobserved gap. Polling can miss very short games
and introduces several seconds of boundary error.

Steam-total mode is an explicit lifetime-history import and assignment, not a
delta. It reads minutes_playtime_forever from the current Steam overview.
Lower totals are blocked. The value may be stale after exit or offline; verify
Steam's total before approval. Steam's own accounting is not guaranteed to
exclude every idle/suspend scenario. Strict local active-time accounting uses
session mode. Automatic Steam-total updates are disabled.

One-time history import is a separate manual operation (`history_import`). The
user reviews the lifetime minutes and confirms that the total includes saved
sessions. Non-Steam shortcuts use AppDetails.nPlaytimeForever when available,
because their overview total can be zero. The input is editable because Steam
metadata can be stale. The operation assigns the total rather than adding it;
decreases, no-op totals, active/interrupted sessions and unresolved proposals
are blocked. Verified import consumes only the snapshotted sessions, records
one-time completion durably, switches to session mode and disables automation.
When Confirm and sync requests ongoing automation, verification atomically
enables session autosync. Newer sessions remain pending. Uncertain sends use the same reconciliation
rules as ordinary updates. This manual option remains available for Non-Steam
history. Automatic first-use Steam import follows the policy above and persists
its completion only after verification; uncertain creation is never retried.

## Writes and reconciliation

1. Read the whole record and compare it with the confirmed baseline.
2. Prepare an immutable before/after proposal. Update only the three numeric
   fields of general.progress, retaining every other field including unknowns.
3. Obtain approval and reread immediately before writing.
4. Persist sending, then make one submission attempt.
5. Reread the complete record; only a matching result verifies the operation.
6. Timeout, restart or unexpected response means uncertain. Reread without
   automatically retrying. An old value does not prove the write never happened.

Creation is a separate zero-time Playing proposal. Any existing account entry
for that game blocks creation, even on a different platform. After sending,
locate a unique game/platform record and compare all fields, except the
server-assigned identity metadata. Ambiguous/unconfirmed creation stays blocked.

No exactly-once or multi-writer guarantee exists. No server CAS/ETag or
idempotency key has been established. Concurrent edits between read and write
can still be overwritten. Server normalization can cause conservative mismatch
states; do not weaken preservation checks without real evidence.

The UI supports cancelling unsent proposals, reading uncertain operations,
accepting a changed remote baseline, and explicitly declaring whether affected
sessions are already included remotely. These decisions change only the local
ledger and can omit/duplicate time if chosen incorrectly. Creation uncertainty
does not offer a blind retry. If the server normalized a created record, the
user can explicitly select and adopt its matching account/game/platform record
without creating another entry. This resolution is recorded in the ledger.

## External edits and automatic mode

Dedicated Playnite interoperability certification is outside the acceptance
scope. Generic preservation and uncertain-write safeguards remain: before an
update, the full remote snapshot must match the last confirmed baseline. Changes
pause synchronization for review. This detects drift but cannot prevent an
external overwrite after synchronization or a concurrent edit between read and
submit. High-confidence association and subsequent session sync remain automatic.

The worker checks closed pending sessions every five seconds. Unresolved operations
block later proposals for that game. Read failures preserve sessions. A prepared
proposal left after interrupted preflight requires review. Disconnect and manual
conflict resolution disable automation. No automatic changes to completion,
notes, ratings, lists or dates are made.
