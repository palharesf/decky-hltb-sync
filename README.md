# HLTB Sync for Deck

Account-linked HowLongToBeat playtime for Decky. React/TypeScript frontend,
Python/SQLite backend, official Decky build tooling. Our code is MIT; the
original template BSD license is preserved in LICENSE.

**0.3.16 is a public beta, not a stable release.** It runs entirely on the Deck
after installation. See [installation](docs/installation.md),
[release notes](docs/release-0.3.16.md) and the known limitations below.

## Acknowledgments

This project is inspired by [HowLongToBeat for Playnite](https://github.com/Lacro59/playnite-howlongtobeat-plugin),
created by **Lacro59 and its contributors**. Their MIT-licensed implementation
was our primary reference for HLTB account authentication, personal library
queries, edit-record fields and playtime submission behavior. Thank you for
making that work available to the community.

HLTB Sync for Deck is an independent Python/TypeScript implementation, not a
direct port of the Playnite plugin. Our Steam integration, session ledger and
conflict-handling policy are implemented separately. This acknowledgment does
not imply affiliation or endorsement.

We also thank [Steam Deck Homebrew](https://github.com/SteamDeckHomebrew/decky-plugin-template)
for Decky and its plugin template, [PlayTime](https://github.com/0u73r-h34v3n/SDH-PlayTime)
for the game-session and suspension references, and
[HLTB for Deck](https://github.com/morwy/hltb-for-deck) for the catalog-search
reference. See [reference evidence](docs/references.md) for inspected versions
and implementation details.

Unlinked games are resolved against the current HLTB library before showing a
dialog. Unique title/platform records can be linked automatically. When catalog
lookup is needed for a Steam game, its HLTB Steam AppID must match before an
automatic creation. New Steam records start with the current lifetime total,
including saved sessions. Existing records receive only new local session time,
including their first sync from this Deck. Steam totals never replace an existing
record automatically. Explicit manual history import remains an advanced option.
Hardware acceptance covered Steam games, the direct Vexx/PS2 shortcut,
automatic matching and sync, suspend/resume, offline recovery, login return,
reboot recovery and checkpoint discard. Local tests cover additional failure
cases. See [validation evidence](docs/validation.md) for exact scope.

## Features

- Connect through the official HLTB login page in Steam's browser. Requests
  execute in the same origin; no password capture, cookie export or PC bridge.
- After login, verify a hidden Steam browser view for subsequent requests,
  dismiss the keyboard and visible login page, then reopen Decky once.
- View your account library, platform, lists and personal playtime.
- Search the catalog and see Main / Main + Extra / Completionist estimates.
- Resolve unique existing records automatically; verify catalog Steam AppIDs
  before automatic Steam creation. Manual linking remains a fallback.
- Record local sessions before mapping, with suspend/resume and persistent checkpoints.
- Resolve unlinked games after exit before considering a dialog. Only ambiguous
  identity or errors need attention; the account picker has a title filter.
- Infer platform hints from ROM folders and direct PCSX2 shortcuts. Ambiguous
  hints stay unknown; ES-DE and known launcher sessions are excluded.
- Import Steam lifetime when creating a record; add sessions to existing records.
- Optionally import past hours once, including Non-Steam AppDetails totals.
  Set a reviewed total without double-counting saved sessions; future play uses
  session deltas. A verified import cannot be repeated for that mapping.
- Preview, approve and verify updates while preserving existing account fields.
- Complete matching, preview, approval, submission and verification inside the
  popup. Pending updates can also be reopened with Review in popup.
- Confirm and sync is available for manual fallback. Resolved games sync on
  exit without approval dialogs. Remote changes pause sync.
- Persist uncertain operations and reconcile without blindly resubmitting.
- Verified first sync enables later session autosync automatically.

Automatic completion is intentionally excluded. Use direct game shortcuts for
emulators: observing ES-DE does not identify the game running inside it.

## Known beta limitations

- **Forced backend termination:** deliberately killing the plugin backend made
  Decky unresponsive during testing. A device restart restored service and the
  saved checkpoint survived. Automatic recovery from this failure is not proven.
- **Recovered-time submission:** discarding an interrupted checkpoint passed on
  hardware. Sending its saved time has local regression coverage only. Time
  after the last persisted observation cannot be reconstructed automatically.
- **Unofficial integration:** HLTB website endpoints and Steam internals are not
  stable public APIs. Changes may break login, matching, capture or submission.
  Natural login expiration was not tested separately; explicit logout/relogin
  recovery passed on hardware.
- **Matching:** high-confidence matches are automatic; ambiguous identities or
  errors may need manual review. Remapping and multiple shortcuts sharing one
  HLTB submission are not implemented.
- **Platform coverage:** Steam games and Vexx/PS2 through a direct shortcut were
  tested. Epic/GOG launchers and other emulators are not broadly certified.
  An ES-DE session cannot identify individual games launched inside it.
- **Other writers:** this plugin adds sessions to existing records, but cannot
  stop Playnite, another device or a manual edit from later replacing that total.
  Multi-device convergence and exactly-once delivery are not guaranteed.
  Uncertain writes pause for reconciliation rather than blind retries.
- **Feature scope:** full Playnite feature parity is not claimed. Edit ratings,
  notes and completion status on HLTB; this plugin preserves those fields.

This beta is distributed through GitHub releases. It has not been submitted to
or approved for the Decky plugin catalog.

## Author and support

Created by [Fernando Palhares](https://palharesf.github.io/).

If you find the plugin useful, a GitHub star, bug report or contribution is
always welcome. You can also [buy me a coffee on Ko-fi](https://ko-fi.com/fernandopa)
or [gift a game from my Steam wishlist](https://store.steampowered.com/wishlist/id/fernandopaa/).
Support is entirely optional; the plugin is free and open source.

The development version also includes **Account + > GitHub** in the plugin
to open the repository for stars, issues and contribution guidelines.
This shortcut is not included in the published 0.3.16 beta.

## Development

Want to contribute? Read the [contribution guidelines](CONTRIBUTING.md).
Search existing issues and pull requests first, then open or join an issue
before implementing a change. A proposed approach and codebase references are
welcome, but are not required to report a problem.

Requires Python 3.11+, Node.js 22 and pnpm. The backend uses the Python standard
library only. The lockfile uses pnpm format 9.

```powershell
pnpm install --frozen-lockfile
pnpm test
pnpm typecheck
pnpm build
pnpm package
```

The ZIP and SHA256 are written to ignored `.local/artifacts/`. Packaging uses an
explicit file allowlist and does not install or publish anything.

- [Architecture and sync policy](docs/architecture.md)
- [On-device acceptance procedure](docs/acceptance.md)
- [Reference evidence and feature comparison](docs/references.md)
- [Validation evidence and limitations](docs/validation.md)

All repository text and future commits use English. Private development files
belong under `.local/`. Runtime data lives in Decky's private plugin settings
directory, never its publicly served assets.
