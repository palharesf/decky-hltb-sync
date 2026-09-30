# Validation evidence

## Local candidate, 2026-09-30

| Check | Result |
| --- | --- |
| Python tests | 58 passed |
| JavaScript/Steam adapter tests | 7 passed |
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

## Outstanding acceptance

Installed UI/controller navigation, login-window lifecycle, authenticated
identity/library/edit reads, real creation/update and server normalization,
gameplay/suspend/offline tests, Steam total freshness, Playnite coexistence and
automatic activation all remain to be tested. Store review and Stable/Beta
channel acceptance are also outstanding.

No installation, account write, cookie extraction, Steam restart or catalog
publication was performed while implementing this candidate.
