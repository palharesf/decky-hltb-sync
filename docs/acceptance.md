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
2. Play a measured interval and exit. A unique high-confidence title/platform
   match must associate and sync automatically, without a confirmation popup or
   opening Quick Access. Infer PlayStation 2 from direct shortcut metadata.
3. With an existing mapping, add only the captured session to the existing HLTB
   record. Verify unchanged notes, ratings, lists, dates and completion fields.
4. Repeat with suspend, wait, resume, play again and exit. Compare local time
   with active intervals, allowing for polling boundary error.
5. Keep manual matching as a fallback for genuinely ambiguous identities only.
   It must not be part of the normal high-confidence flow. Never stack dialogs
   or interrupt another game. An uncertain write must reconcile without resend.

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

## Resume checklist after 0.3.11 installation

Recorded on 2026-10-02. See [validation evidence](validation.md) for measured
results and version-specific limitations.

| Case | Status | Next action and expected result |
| --- | --- | --- |
| Existing HLTB record, first local association | Passed on 0.3.11, 2026-10-05 (Aperture Desk Job) | Use an installed Steam game with an existing positive PC total and no local mapping. Record the remote baseline, play briefly, exit. Match automatically and add only captured seconds. Reuse the same submission and preserve every other field. |
| New Steam record | Passed before 0.3.11; local regression coverage retained | Initial total includes Steam lifetime once; subsequent sessions add deltas. Do not add the same session twice. |
| Already linked Vexx / PS2 | Passed on 0.3.10 before upgrade | Latest verified total was 8,574 seconds. A future 0.3.11 session should add only its active time. |
| Suspend / resume | Passed | Suspended time excluded; one logical session. |
| Offline exit / reconnect | Passed | Save locally, then sync automatically on reconnect without duplication. |
| Full reboot and silent login recovery | Passed on 0.3.10; upgrade recovery passed on 0.3.11 | Connected without opening login or keyboard; preserve saved sessions and mappings. |
| Expired login | Revoked-login recovery passed on 0.3.11, 2026-10-05; natural expiration not separately tested | Preserve sessions, reconnect through normal login, then resume without lost time or duplicate writes. |
| Unexpected interruption during gameplay | Pending on hardware | Recover only persisted time and flag uncertain intervals; never count downtime. Arrange a controlled test separately. |
| Uncertain write / preservation / duplicate events | Covered locally | Use simulated transport failures; do not deliberately produce uncertain writes in a personal account. |

For the next first-association test, refresh and reread the candidate immediately
before playing. A cached total is not a test baseline. After exit, compare the
same submission against baseline plus captured session seconds. Steam lifetime
must not replace an existing HLTB total. No dedicated Playnite conflict test is
required. Account-specific candidate IDs and snapshots belong in ignored
`.local/`, not in contribution examples.
