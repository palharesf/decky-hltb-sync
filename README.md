# HLTB Sync for Deck

Account-linked HowLongToBeat playtime for Decky. React/TypeScript frontend,
Python/SQLite backend, official Decky build tooling. Our code is MIT; the
original template BSD license is preserved in LICENSE.

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

**0.3.11 is an integration candidate, not a hardware-certified release.**

Unlinked games are resolved against the current HLTB library before showing a
dialog. Unique title/platform records can be linked automatically. When catalog
lookup is needed for a Steam game, its HLTB Steam AppID must match before an
automatic creation. New Steam records start with the current lifetime total,
including saved sessions. Existing records receive only new local session time,
including their first sync from this Deck. Steam totals never replace an existing
record automatically. Explicit manual history import remains an advanced option.
Installation, frontend loading and backend status passed a Deck smoke test.
Authenticated reads and the first pilot import reached HLTB on the Deck;
ongoing automatic gameplay/suspend acceptance remains outstanding.
Private website endpoints and Steam internals can change.

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
