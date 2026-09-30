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
2. Choose **Connect to HowLongToBeat**. Sign in on the official site only.
3. Return to the plugin; use **Refresh HLTB library** if needed. Check title,
   platform, personal time and lists against the website.
4. Verify the HLTB browser target survives returning to the plugin. If it does
   not, background account integration has not passed acceptance.
5. Test expired login and Disconnect. Sessions must survive; account payloads
   and raw errors must never appear in logs. Disconnect is not website logout.

## Vexx / PS2 gate

1. Select the direct Vexx Steam shortcut, not ES-DE or a general emulator.
2. Select the existing PlayStation 2 record, compare its current time, select
   local sessions and confirm the link.
3. If no record exists, search the catalog, confirm game/edition and exact
   platform. Preview zero-time creation. Creating it is an account write and
   requires explicit authorization.
4. Play a measured interval, suspend, wait, resume, play again and exit. Compare
   local time with active intervals, accounting for polling boundary error.
5. Preview an update and compare before/after.
6. Obtain approval for this exact account write, submit, reread, and verify
   progress plus unchanged notes, ratings, lists, dates and completion fields.

## Steam lifetime gate

Explicitly select Steam lifetime mode for a Steam game. Close it and wait for
Steam's total to refresh. The preview must assign that total, not add it to the
HLTB total. Lower totals are blocked. This mode imports pre-install history only
through explicit user selection.

## Recovery and automation

Test offline exit, frontend/backend restart, expired login, remote Playnite
changes and ambiguous records. Use simulated transports for deliberate uncertain
writes until account testing is authorized. Never provoke duplicate writes on
a personal record.

After a verified manual session update, disable competing writers, acknowledge
the policy and enable automatic session sync. Repeat exit/offline/recovery tests.
