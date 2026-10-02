# On-device acceptance procedure

This is product acceptance, not a console-script workflow. SSH is only for
authorized installation/diagnostics; normal operation must require no PC.

## Installation gate

Run tests, typecheck and build, then `pnpm package`. Review the ZIP and SHA256.
Never include .local, databases, browser profiles or credentials. Obtain
installation authorization and ensure no game is running. Preserve plugin data
on upgrade. Never restart Steam/Decky during gameplay.

## Account gate

1. Open **Quick Access Menu > Decky > HLTB Sync for Deck**.
2. Choose **Connect to HLTB**. Sign in on the official site only.
3. The plugin reopens after confirmation; use **Account options > Refresh library** if needed. Check title,
   platform, personal time and lists against the website.
4. Verify the login keyboard disappears and the visible HLTB page returns to
   the previous Steam screen before the plugin panel opens. A plugin-owned hidden
   browser target must retain the same account; reread a record after returning.
   If the background handoff fails, keep the visible login page open and report
   the failure. Navigating elsewhere or launching a game must prevent focus theft.
5. Test expired login and Disconnect. Sessions must survive; account payloads
   and raw errors must never appear in logs. Disconnect is not website logout.

## Vexx / PS2 gate

1. Launch the direct Vexx Steam shortcut, not ES-DE or a general emulator.
2. Play a measured interval and exit before linking it. Confirm that a local
   session and confirmation dialog appear without opening the plugin. Inspect
   the PS2 hint, suggested account record and before/after total. Choose
   **Confirm and sync** only when authorized to link and send that update.
   Verify **Later** preserves the session and **Review match** in
   the panel reopens the dialog. Never stack dialogs or interrupt another game.
3. If no record exists, choose **Choose another**, search the catalog, confirm game/edition and exact
   platform. Preview zero-time creation. Creating it is an account write and
   requires explicit authorization.
4. Repeat with suspend, wait, resume, play again and exit. Compare
   local time with active intervals, accounting for polling boundary error.
5. In the popup, compare the before/after proposal without opening Quick Access.
6. **Confirm and sync** is the single approval action in the popup; it must not
   redirect to Quick Access or require another checkbox. Verify
   progress plus unchanged notes, ratings, lists, dates and completion fields.
   Confirm the popup reports **Synced** only after verification. On an uncertain
   response, **Check status** must reconcile without sending again.

## Steam lifetime gate

For a game with an existing HLTB record, automatic first association must add
only the captured session seconds to the current remote total. Check lower,
equal and missing Steam totals: none should replace remote progress or suppress
the session. For a new Steam record, initialize it with Steam lifetime once,
without adding the captured sessions on top. Manual import below is opt-in.

For one-time import, enable **Import past hours once** in the match dialog or
linked-game panel. Review **Lifetime total (minutes)** and explicitly accept
that it includes the locally saved sessions. The proposal must set the exact
reviewed total, not add local sessions on top. After an authorized verified
send, the import option must disappear and new sessions must add normally.
Verify repeat blocking after restart and reconciliation after uncertain sends.

Explicitly select Steam lifetime mode for a Steam game. Close it and wait for
Steam's total to refresh. The preview must assign that total, not add it to the
HLTB total. Lower totals are blocked. This mode imports pre-install history only
through explicit user selection.

## Recovery and automation

Test offline exit, frontend/backend restart, expired login, external HLTB
changes and ambiguous records. Use simulated transports for deliberate uncertain
writes until account testing is authorized. Never provoke duplicate writes on
a personal record.

After the confirmed update verifies, check that later session sync is enabled
without extra setup. Repeat exit/offline/recovery tests and verify remote edits
pause sync rather than overwrite unseen changes.
