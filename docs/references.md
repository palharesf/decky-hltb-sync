# Reference evidence and feature comparison

Sources refreshed on 2026-09-30. Our implementations are original; no
Playnite/PlayTime/HLTB for Deck code was transplanted. Endpoint names and field
shapes are compatibility information. The template's build configuration retains
its original BSD-3-Clause notice in LICENSE.

| Reference | Inspected commit | Evidence |
| --- | --- | --- |
| [Decky template](https://github.com/SteamDeckHomebrew/decky-plugin-template/tree/90d0780e882a17f5714fc6de044c645f22608290) | 90d0780 | Build, Python entry point, settings directory |
| [Playnite HLTB](https://github.com/Lacro59/playnite-howlongtobeat-plugin/tree/809c1890b0ce27942fd92c9b50ae7e38a8c89e30) | 809c189 | MIT, account session, games list, EditData, submit, total assignment |
| [PlayTime](https://github.com/0u73r-h34v3n/SDH-PlayTime/tree/64d5faf8127f7e8588c8d26fae4567d58dc3f4f0) | 64d5faf | RunningApps and System/User suspension callbacks |
| [HLTB for Deck](https://github.com/morwy/hltb-for-deck/tree/f5d203f9a7af8335f02f9925f9365c48c130a518) | f5d203f | Catalog search bootstrap, duration fields |
| [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader/tree/75563316f9119ee7e36be7f43885be65e877fad0) | 7556331 | Loopback CEF discovery and Runtime.evaluate |
| [Plugin database](https://github.com/SteamDeckHomebrew/decky-plugin-database/tree/0bd244f2bd0c2c5bfd6d3904efa336dd1f001cd3) | 0bd244f | Publication via reviewed submodule PR |

Playnite HowLongToBeatApi.cs reads /api/user, POSTs
/api/user/{id}/games/list, reads /submit/edit/{id}, and POSTs /api/submit.
UserGamesListParam.cs defines selected lists and the 5,000-entry limit.
EditData.cs defines the complete submission shape. These are unofficial
website contracts, not stable public APIs.

HowLongToBeatDatabase.GetAggregatedPlaytime sums local Playnite games linked
to the same HLTB game; SetCurrentPlayTime assigns the result to progress.
Optional score/list synchronization is deliberately not automatic here because
preserving existing data is a project requirement.

## Functional comparison

Implemented means code/local tests exist, not live HLTB or Deck acceptance.

| Capability | Candidate status |
| --- | --- |
| Official-site login | Integrated Steam browser flow; login return and revoked-session recovery passed on hardware |
| Personal library/platform/lists/progress | Implemented with complete-list validation |
| Catalog search and duration estimates | Implemented against inspected bootstrap contract |
| Explicit mapping | Implemented, one shortcut per submission |
| New Playing record | High-confidence automatic creation, duplicate checks and readback; manual fallback |
| Steam lifetime upload | Automatic once for new Steam records; explicit one-time import for existing mappings |
| Non-Steam sessions | Mapped direct shortcuts, checkpoints, suspend/resume |
| Automatic session upload | High-confidence matching and verified sync enable automation; no single-writer acknowledgment |
| Offline queue/uncertain outcomes | Persistent with explicit reconciliation |
| Existing notes/ratings/lists/completion | Preserved; never automatically changed |
| Manual metadata editor | Use the HLTB website; not implemented in this candidate |
| Multi-device convergence | Not guaranteed; other writers may replace totals; no dedicated Playnite certification |
| Remapping/shared submissions | Not yet implemented |
| VNDB, QuickSearch, themes and tags | Not ported; outside HLTB account/session integration |
| Full Playnite feature parity | Not claimed |

The initial Portuguese commit remains in history. Current repository content
and future commits use English; published history was not rewritten.
