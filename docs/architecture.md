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
HLTB origin, checked again inside each request. After a Steam restart, Connect
may be needed again; website login persistence belongs to Steam's browser.
Disconnect forgets the target and disables automatic sync, but does not log out
of the website. This is not a separate browser profile.

The HLTB browser target must remain alive for requests. If Steam destroys it
when returning to Gaming Mode, reconnection is required and sessions remain
local. This is a key acceptance gate, not a proven background-login solution.

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
game, submission and platform identity. Only mapped games are tracked.
Multiple shortcuts sharing a submission and remapping are not yet supported.
No game/platform is guessed, and catalog estimates are distinct from personal
progress.

Library queries include all supported lists. Unknown, duplicate or truncated
responses fail closed; errors never mean an empty library. The inspected
contract has a 5,000-entry limit; larger/incomplete libraries are rejected.

## Time sources

Session mode starts at the first observation after mapping, never imports
historical Steam hours. The frontend polls RunningApps every five seconds,
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

## Playnite and automatic mode

Playnite can assign its aggregated local total and overwrite Deck additions.
Neither adding to remote nor taking the maximum solves this. Keep manual mode
with multiple writers. Session autosync requires a verified manual update and
explicit acknowledgment that competing writers for that record are disabled.
The plugin never modifies Playnite settings.

The worker checks closed pending sessions every minute. Unresolved operations
block later proposals for that game. Read failures preserve sessions. A prepared
proposal left after interrupted preflight requires review. Disconnect and manual
conflict resolution disable automation. No automatic changes to completion,
notes, ratings, lists or dates are made.
