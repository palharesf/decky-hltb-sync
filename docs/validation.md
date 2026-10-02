# Validation evidence

## Existing-record session policy, 2026-10-02

Version 0.3.11 changes automatic first association of existing HLTB records to
session deltas, superseding the initial-total policy tested earlier with Beetle
Ninja. Only automatic creation of a new Steam record imports lifetime history.
No previously verified import or historical session is replayed or corrected
retroactively. Explicit advanced manual imports remain available.

All 108 tests (83 Python, 25 JavaScript), typecheck and build passed. Regression
coverage checks preservation of every other existing-record field, lower/equal/
missing Steam totals, renamed records resolved by catalog identity, no duplicate
first sync, and continued lifetime initialization for new records. Dedicated
Playnite interoperability testing was removed from acceptance scope; generic
external-edit and uncertain-write protections remain.

After Vexx exited, version 0.3.11 was installed through Decky with a verified
artifact SHA256, without restarting Steam or Decky. Authentication recovered
automatically: Connected, tracker observing, ten saved sessions, three mappings,
no pending sessions, no match requests and no error. The preceding Vexx session
was verified on 0.3.10 before installation: 1,309 seconds added to 7,265 seconds,
for a total of 8,574 seconds (2:22:54). The revised existing-record
first-association policy has local coverage but still awaits hardware acceptance
with another previously unlinked game.

## Existing Steam account-record matching passed, 2026-10-02

Before gameplay, Beetle Ninja had 18 Steam minutes and an existing PC Playing
record with 1,116 seconds in HLTB, without a local mapping. The user played a
short session (70.001 seconds captured) and exited. Normal resolution reused the
same submission automatically, with no manual link command. The first-use Steam
history import assigned the refreshed Steam total of 19 minutes (1,140 seconds),
verified the operation, consumed the saved session and enabled future session
sync. No match request remained. A fresh account-library read found one record
for this game; an editable-record reread confirmed Playing true, Completed false
and 1,140 seconds. Comparing persisted before/after proposals confirmed all fields
except general.progress unchanged; post-submit verification passed as well.

Precision note: Steam lifetime is exposed in whole minutes, whereas HLTB already
contained seconds. Therefore this initial absolute-total assignment increased
HLTB by 24 seconds despite 70 seconds of locally captured gameplay. Subsequent
syncs use local session seconds. The user also reported missing PC saves, which
was not investigated or modified as part of HLTB acceptance.

## Full reboot recovery passed, 2026-10-02

The user restarted the Deck with 0.3.10 installed and then re-enabled SSH.
Before any connection or library-refresh command, status already reported
Connected, a fresh library, tracker observing and no error. All eight sessions,
both mappings, their automatic-sync settings and one-time history markers were
preserved; no unresolved operation remained. The keyboard was hidden. A separate
editable-record read succeeded and confirmed the unchanged 2024 total of 52,084
seconds. No Connect command, login navigation or account write was used for
this verification. This passes authenticated recovery across a full reboot
with the existing valid Steam browser session.

## Restart recovery candidate, 2026-10-02

The hardware restart on 0.3.9 preserved eight sessions and two mappings but lost
the authenticated browser target. Version 0.3.10 adds startup recovery: a hidden
Steam browser view is recreated and the previously connected account identity
is verified before adopting it. Startup/network failures retry every 30 seconds;
expired login and account mismatch require explicit reconnection. Disconnect
revokes restoration. Recovery neither opens a login page nor changes UI focus.
Legacy installations derive the expected user ID only from a single consistent
mapped account when a previous connected target was persisted.

All 105 tests (80 Python, 25 JavaScript), typecheck and build passed. Tests cover
dead-target replacement, account identity, disconnect, expired login, retry
serialization and silent recovery. Hardware recovery verification is pending.

Installed 0.3.10 on the already-rebooted Deck with no game running. Without a
Connect command or manual browser launch, the startup poll restored Connected
with no error, tracker observing, eight sessions and both automatic mappings
preserved. Steam remained on /library/home with its keyboard hidden. A fresh
editable-record read succeeded and confirmed the unchanged 2024 total of 52,084
seconds. This verifies recovery from the dead target left by the prior reboot;
a full reboot with 0.3.10 installed remains the final repetition of this case.

## Session row spacing, 2026-10-02

Version 0.3.9 adds 18 pixels between recent-session entries and 6 pixels between
each title and its time/status row. All 103 tests, typecheck and build passed.
The matching policy is unchanged: high-confidence resolution runs automatically;
manual linking remains an advanced exception tool. The build was installed with
no running games. Restart recovery is the next hardware acceptance case.

## Compact panel installed and visually reviewed, 2026-10-02

After Vexx exited, version 0.3.8 was installed through Decky's normal installer
with matching artifact SHA256 and no running games. Login returned with the
keyboard hidden; status reported connected, observing and no error. A Deck
screenshot confirmed the compact account controls and three recent session rows
with short Synced labels, without the old explanatory paragraphs or mandatory
association instructions. The offline label has local regression coverage but
has not yet been visually tested during another hardware outage.

The preceding Vexx session had already auto-synced before installation: 725
seconds added to 6,540 seconds, yielding 7,265 seconds (2:01:05). A fresh HLTB
editable-record read after installation independently confirmed that total.

## Compact panel candidate, 2026-10-02

Version 0.3.8 keeps connection and recent-session states on the main panel.
Account details and advanced linking/import/recovery controls are collapsed.
Obsolete mandatory-match instructions and visible-browser instructions were
removed. Pre-submission network failure reports Waiting for connection / Saved;
uncertain or blocked operations still require review. A regression test checks
that offline pending sessions retain their state and automatically clear the
connection message after verified synchronization. Local tests (80 Python,
23 JavaScript), typecheck and build passed. On-device visual review is pending;
installation was deferred while Vexx was running.

## Offline exit and reconnection passed, 2026-10-02

The user disabled Wi-Fi, played 2024 and exited before reconnecting. While
offline, the panel reported automatic sync needed attention. After the user
restored Wi-Fi, read-only diagnostics found the 210-second session synced,
no backend error and one verified update from 51,874 to 52,084 seconds.
No manual send, preview or reconciliation command was used during this test.
A fresh editable-record read independently confirmed 14:28:04, Playing true
and Completed false. This passes offline capture and automatic retry of the
pre-submission read after connectivity returns, not an uncertain POST retry.
The panel still needs clearer offline/pending status and removal of obsolete
instructions telling users to confirm every game's association.

## Suspend/resume autosync passed, 2026-10-02

The next 2024 session retained one session across suspend and resume, then synced
automatically after exit. The ledger recorded start, suspend, resume and stop
(including repeated Steam suspend/resume notifications) with 64 heartbeats and
324.860 seconds of active elapsed time. No interruption/error state was raised.
Kernel timestamps independently confirmed deep suspend from 16:34:59 to 16:38:49
America/Sao_Paulo (3 minutes 50 seconds). This sleep interval was excluded from
active accounting. One verified session update added 324 whole seconds, from
51,550 to 51,874 seconds. A fresh editable-record read confirmed 14:24:34,
Playing true and Completed false. Fractional seconds are truncated per session.

## Subsequent-session autosync passed, 2026-10-02

On installed version 0.3.7, the user played 2024: Mosaic Retrospective and exited
without manually requesting synchronization. The tracker captured 310 seconds.
One session operation verified the update from 51,240 to 51,550 seconds
(14:14:00 to 14:19:10). Backend status showed no running game, no error, the new
session synced and automatic synchronization still enabled. An independent
editable-record reread confirmed 51,550 seconds, Playing true and Completed false.
The initial history import was not repeated. This passes ordinary mapped-game
exit autosync; suspension, offline recovery and reboot remain separate cases.

## Automatic matching and Steam history, 2026-10-02

Version 0.3.6 was installed with no running games. Its normal frontend resolver
identified 2024: Mosaic Retrospective, created the PC Playing record automatically
and sent the refreshed Steam lifetime total of 854 minutes (51,240 seconds).
A subsequent account library read confirmed that total. No manual association
was used. Verification remained uncertain because HLTB omitted empty editor
defaults: adminId, customLabels, manualTimer and general.progressBefore.
Version 0.3.7 permits only those observed empty omissions during creation
verification; updates to existing records retain strict preservation checks.
Reconciliation must reread the existing operation without resubmitting it.

Version 0.3.7 passed 79 Python tests, 23 JavaScript tests, typecheck and build.
It was installed with no running games. Read-only reconciliation of the existing
creation operation succeeded without resubmission. A fresh editable-record read
confirmed 51,240 seconds, Playing true and Completed false. Backend status showed
one verified creation, all three captured sessions synced, history import consumed
and session automation enabled. The native dialog's Check status action refreshed
the result. Subsequent gameplay exit, suspension/offline and reboot recovery still
require hardware acceptance.

The user's revised policy authorizes automatic identity resolution and importing
Steam lifetime on the first sync, without adding saved sessions on top. Subsequent
syncs use session deltas. The 0.3.6 candidate implements this policy, including
existing records, new Playing records, one-time import persistence, identity
mismatch, lower totals and uncertain-send protection. The fallback account picker
filters by title and caps visible results rather than listing the entire library.

Live read-only inspection found the current search init returns a token without
optional hpKey/hpVal fields. The adapter now accepts that contract, as the Playnite
reference does. Catalog lookup identified the pilot Steam game by the exact Steam
AppID. A fresh account library lookup found no record for that catalog game ID.
No account update had been made at this stage. On 0.3.5, login return completed
with the keyboard hidden, Steam's previous route restored, and fresh library reads
succeeding through the hidden view after leaving the visible login page.

## Login return candidate, 2026-10-02

Version 0.3.5 verifies the same account in a plugin-owned hidden Steam browser
view before dismissing the login keyboard and returning from ExternalWeb.
The visible page is left open if the handoff fails. Return navigation is skipped
if the user navigated elsewhere or launched a game. The hidden view performs
same-origin requests; no cookies are read or exported. Plugin unload destroys
the owned view, so reconnect after reload/reboot remains a separate test.

Local validation: 72 Python tests, 22 JavaScript tests, typecheck and build passed.
New coverage checks marked-target binding, account mismatch, failure retention,
keyboard/navigation ordering and avoiding focus changes during gameplay.
The package was transferred to the Deck and its SHA256 matched. Installation
was skipped because a game was running. Version 0.3.4 remains installed;
the new login-return behavior still requires hardware validation.

## Local candidate, 2026-09-30

| Check | Result |
| --- | --- |
| Python tests | 71 passed |
| JavaScript/browser/Steam/login/matching/review tests | 19 passed |
| TypeScript typecheck | Passed |
| Rollup build | Passed |
| Frozen-lockfile install | Passed |
| Package generation | ZIP and SHA256 generated under .local/artifacts |

The suite covers the ledger, browser binding, HLTB client, application service
and Steam frontend adapter with synthetic account data. Reproduce using
`pnpm test`, `pnpm typecheck`, `pnpm build` and `pnpm package`.

Coverage includes origin/target restrictions, account switching, expired login,
incomplete libraries, identity, field preservation, zero-time creation, creation
timeout, approval, remote changes, total/delta semantics, crash recovery, manual
resolution, automation gates, observation epochs, suspension with empty app lists,
and subscription cleanup. No test submits to a real account.

## Read-only Deck probe, 2026-09-30

The new CEF client was executed in memory through SSH, without remote file
writes or installation. Its WebSocket connection successfully evaluated a bounded
read-only expression in Steam's SharedJSContext. Observed:

- appStore and RunningApps are available.
- Vexx exists as a direct Non-Steam shortcut.
- System suspension callbacks are absent in this Steam version.
- User suspension/resume callbacks are present; that fallback is implemented.
- A running application was reported. Nothing was stopped or restarted.

This proves CEF transport and API availability, not event timing, login-window
behavior or accounting accuracy during a real suspend cycle.

## Installed Deck smoke test, 2026-09-30

With user authorization and no running games, version 0.2.1 was installed
through Decky's installer over the existing SSH connection. The transferred
ZIP SHA256 matched the local artifact. Steam and Decky were not restarted.

The initial 0.2.0 backend failed because Decky's frozen Python omits
`html.parser`. Version 0.2.1 uses a bounded Next.js script contract parser
instead, with regression coverage for quotes and ambiguous payloads. CEF
target discovery now uses direct loopback `http.client` without relying on
`urllib.request` being bundled.

Decky reported version 0.2.1 enabled and the frontend loaded. The backend
status RPC returned `ok: true`, `tracker: observing`, `auth: disconnected`,
no error, and empty mappings, sessions and operations. This verifies startup
and frontend/backend communication, not authentication or gameplay accuracy.

## Outstanding acceptance

The first user-requested pilot history import reached HLTB. A fresh editable
record read confirmed the approved total. Strict verification initially marked
the result uncertain because the server replaced userIp metadata and normalized
an unset storefront from null to an empty string. A private in-memory field
comparison found no other differences. Version 0.3.4 accepts only those observed
normalizations during post-submit comparison, retaining the actual server
snapshot as the next baseline. Tests still reject changes to notes and other
user fields. Reconciliation must reread without resending the import.

On the installed 0.3.4 build, the native dialog's Check status action completed
that read-only reconciliation successfully, without a second submission. The
Vexx PS2 record contained 6,540 seconds (1 hour 49 minutes). Backend status
reported the history import verified, the captured session synced, the one-time
import consumed, and automatic synchronization enabled. The native dialog
displayed Saved and verified on HLTB. The next real gameplay session must still
validate automatic synchronization on exit; suspend/offline acceptance remains
outstanding.

Version 0.3.3 follows the requested one-confirmation workflow: Confirm and sync
authorizes the first send and enables future session autosync after verification.
The extra approval checkbox and single-writer setup gate were removed. Tests
cover ordinary exit autosync, history-import activation, uncertain outcomes,
remote drift and revoking pending automation when disabled. The preflight
snapshot check and no-blind-retry policy remain unchanged.

Version 0.3.2 keeps preview, approval, send and verification inside the native
dialog. Frontend protocol tests verify approval gating, double-click blocking,
uncertain-response reconciliation, backend false results, conflicts and reopening
an existing operation without duplicate writes. The account-write transport is
mocked in these tests; real write verification remains an acceptance gate.

Version 0.3.1 replaces exit toasts with native confirmation dialogs. Tests cover
serialization, dismissal, gameplay/suspension deferral, unload preservation and
session-specific acknowledgement. One-time history-import tests cover explicit
overlap confirmation, exact-total assignment, field preservation, durable
repeat blocking, later session deltas and uncertain-response reconciliation.
No test sends a real account update. The pilot's first actual game exit was
recorded locally and matched to PS2 in 0.3.0; its notification was acknowledged,
but user feedback showed a toast was insufficient for the intended workflow.

Installed 0.3.1 on the Deck with no game running. The retained session survived,
the authenticated library refreshed, and the native dialog was opened through
the panel's Review match fallback. On-device screenshot inspection confirmed
the PS2 candidate, Confirm match / Choose another / Later actions, and the
one-time import input populated from Steam AppDetails. The next real game exit
must still validate automatic dialog presentation. No account write was made
as part of installation or this dialog inspection.

Version 0.3.0 records direct games before linking. Synthetic tests cover offline
capture, suspension, restart recovery, deferred binding without losing time,
duplicate match ambiguity, incorrect platforms, launcher exclusion, and toast
deduplication. Suggestions never authorize writes.

Read-only Deck inspection confirmed the pilot shortcut uses a PCSX2 launcher
and a PS2 ROM folder. Inspection of the edit response shape (without recording
private values) showed that current saved records omit `manualTimer` and
`customLabels`. The adapter now treats those as optional, preserving them if
present and retaining all required game-data sections. A regression test checks
that only progress changes and no absent editor fields are synthesized.

The installed 0.3.0 backend successfully read the pilot's full editable record
and returned its PS2 platform and personal progress through the normal plugin
RPC. The actual shortcut metadata produced the expected PS2 hint using the
compiled frontend detector. Capture was observing with no sessions before the
user's first gameplay test. No account write or automatic mapping was made.

Versions 0.2.4–0.2.5 shorten the Quick Access copy and use full-width actions
and dropdowns. The header uses Decky's `titleView` contract to display HLTB Sync.
Account tools are expandable; record-linking controls appear after game
selection, and catalog creation is opt-in. Approval and conflict-resolution
gates are retained. All 69 tests, typecheck and build passed.

Deck screenshots revealed narrow inline action buttons and a wrapping header;
the updated layout was inspected on hardware with the current account session.
Private screenshots remain in ignored `.local/` storage.

Version 0.2.3 makes the account button reflect the confirmed backend state:
Connecting during login, Connected after authentication, and Connect when
disconnected. The connected button cannot start another login, and its help
text explains the active session instead of prompting the user to sign in.
The 59 Python and 10 JavaScript tests, typecheck and build passed.

Version 0.2.2 adds a plugin-owned login return monitor that survives panel
unmounting. It opens Decky's Quick Access tab once after fresh authenticated
library data arrives. Tests cover stale results, cancellation, timeout, transient
RPC failures and duplicate callbacks. It never closes the authenticated page.

The installed 0.2.2 reconnect smoke test used the existing authenticated Steam
browser session. Clicking Connect opened the HLTB page; the plugin then reopened
its visible Decky panel automatically and reported connected with a freshly
loaded library. No Steam/Decky restart or account write was required. The
password/CAPTCHA path with this new return monitor still needs a fresh-login test.
Decky retained the previous panel object during the hot update; reselecting this
plugin loaded the updated panel before testing.

Authenticated identity and library reads have now succeeded on the Deck.
The pilot's existing account entry was found, but its detailed read returned
`incomplete_edit_record`. The 0.3.0 adapter fixes the observed shape mismatch;
account writes and real gameplay acceptance remain separate gates.

Full controller navigation, fresh-login lifecycle, authenticated edit reads,
real creation/update and server normalization,
gameplay/suspend/offline tests, Steam total freshness, Playnite coexistence and
automatic activation all remain to be tested. Store review and Stable/Beta
channel acceptance are also outstanding.

No account write, cookie extraction, Steam restart or catalog publication
was performed. Installation was authorized separately for the smoke test.
