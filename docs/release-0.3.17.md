# HLTB Sync for Deck 0.3.17 — Public beta

Track Steam Deck sessions and sync playtime to your HLTB account after closing
a game. Runs entirely on the Deck after installation, with Steam's browser for
login and a persistent local session queue. This is a beta, not a stable release.

## New in 0.3.17

- Added **Account + > GitHub** for stars, issues and contributions.
- Added portfolio, Ko-fi and Steam wishlist links to the README.
- Verified on the Deck: the repository opens, B returns to Steam, and HLTB
  remains Connected with sessions and mappings preserved.
- Session counting and synchronization behavior are unchanged from 0.3.16.

## Included

- Automatic high-confidence matching against existing HLTB records and catalog
  identities; direct emulator shortcuts can provide platform hints.
- Session deltas for existing records, Steam lifetime once for new Steam records,
  and explicit one-time history import.
- Suspension exclusion, offline persistence and recovery after login loss.
- Preservation of notes, ratings, lists and completion fields; no automatic
  completion. Durable write intents and reconciliation of uncertain responses.
- Browser return after login, compact Decky UI and direct recovery dialogs with
  horizontal controller navigation. Explicit recovered-time sync or confirmed
  discard, with discarded segments excluded from later updates.

## Validation

All 124 automated tests (87 Python, 37 JavaScript), typecheck and build passed.
The previous beta's hardware tests covered Steam games, Vexx/PS2 via a direct shortcut, automatic
association/sync, suspension, offline recovery, login return, reboot recovery
and checkpoint discard. The final Vexx session added 31m44s in one verified
operation; a fresh HLTB read confirmed the result, with other fields unchanged
and discarded time excluded. See [validation evidence](https://github.com/palharesf/decky-hltb-sync/blob/v0.3.17/docs/validation.md).

## Known limitations

- Forcibly killing the backend made Decky unresponsive in testing. A device
  restart was required; the persisted checkpoint survived.
- Sending recovered checkpoint time is tested locally only; the discard branch
  passed on hardware. Unrecorded time after an interruption cannot be recovered
  automatically.
- HLTB endpoints and Steam internals are unofficial and may change. Explicit
  logout/relogin passed; natural session expiration was not separately tested.
- Ambiguous matches may require manual review. Remapping and multiple shortcuts
  sharing one HLTB submission are not implemented.
- Steam and the direct Vexx/PS2 shortcut were tested. Broad Epic/GOG and emulator
  compatibility is unverified. ES-DE sessions do not identify individual games.
- Other applications can overwrite the HLTB total later. Multi-device convergence
  and exactly-once delivery are not guaranteed; uncertain writes require
  reconciliation, not blind retries.
- Full Playnite feature parity is not claimed; metadata editing stays on HLTB.

## Install

Install the attached **hltb-sync-for-deck-0.3.17.zip** through Decky's
**Settings > Developer > Install Plugin from URL** or **Install Plugin from ZIP
File**. Close games first. Do not install the automatically generated source
archives. A matching SHA256 checksum is attached.

See the [installation guide](https://github.com/palharesf/decky-hltb-sync/blob/v0.3.17/docs/installation.md).
Existing settings and sessions are retained during an update. Catalog submission
and approval have not taken place; this is a manually installed GitHub beta.

Inspired by Lacro59's [HowLongToBeat for Playnite](https://github.com/Lacro59/playnite-howlongtobeat-plugin).
Our implementation is MIT licensed; the original Decky template license and
community acknowledgments are preserved in the repository and package.
