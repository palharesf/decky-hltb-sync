# HLTB Sync for Deck

Account-linked HowLongToBeat playtime for Decky. React/TypeScript frontend,
Python/SQLite backend, official Decky build tooling. Our code is MIT; the
original template BSD license is preserved in LICENSE.

**0.2.0 is an integration candidate, not a hardware-certified release.** No
authenticated HLTB read/write or installed-plugin acceptance test has been
performed. Private website endpoints and Steam internals can change.

## Features

- Connect through the official HLTB login page in Steam's browser. Requests
  execute in the same origin; no password capture, cookie export or PC bridge.
- View your account library, platform, lists and personal playtime.
- Search the catalog and see Main / Main + Extra / Completionist estimates.
- Explicitly link Steam games or direct Non-Steam shortcuts to existing records.
- Preview new Playing records at zero, with duplicate checks and approval.
- Track mapped games with suspend/resume events and persistent checkpoints.
- Add local sessions or explicitly import Steam lifetime playtime.
- Preview, approve and verify updates while preserving existing account fields.
- Persist uncertain operations and reconcile without blindly resubmitting.
- Optional session autosync after a verified manual session update and explicit
  single-writer acknowledgment. Steam-total updates remain manual.

Automatic completion is intentionally excluded. Use direct game shortcuts for
emulators: observing ES-DE does not identify the game running inside it.

## Development

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
