# Contributing

Contributions start with an issue, before implementation or a pull request.
This applies to bug fixes, features, documentation and other changes.

## Start with an issue

1. Search **open and closed issues**, and existing pull requests, for the same
   problem or proposal. Check the current documentation too.
2. If an issue already covers your contribution, use it instead of opening a
   duplicate. Comment with any new evidence and say that you would like to work
   on it. Check whether someone is already working on a solution.
3. If no matching issue exists, open one before starting work. Explain the
   problem, the expected behavior and why the change would help.
4. When possible, include a potential approach: affected components, alternatives,
   tradeoffs and how you would verify the result. It is a proposal, not a promise
   to implement everything exactly that way.

Showing familiarity with the codebase is a plus. Links to relevant files,
functions or tests make discussion easier, but you do not need a complete
technical solution to report a bug or suggest an improvement.

For bugs, include reproduction steps, expected and actual behavior, plugin
version, SteamOS/Decky versions when relevant, and whether the game is Steam
or a direct Non-Steam shortcut. Share only sanitized diagnostics.

Discuss substantial feature or architecture changes in the issue before
investing in a large implementation. An issue makes the work visible; it does
not guarantee that a particular solution will be merged.

## Understand the project

Read [AGENTS.md](AGENTS.md), the [README](README.md),
[architecture and sync policy](docs/architecture.md), and
[validation evidence](docs/validation.md).

Useful starting points:

| Area | Location |
| --- | --- |
| Decky UI and Steam integration | `src/` |
| Backend entry point and commands | `main.py` |
| Session ledger, matching and HLTB integration | `py_modules/hltb_sync/` |
| Regression coverage | `tests/` |
| Packaging | `tools/package.py` |

Use English for code, UI, documentation, filenames, issues, pull requests and
commit messages. Follow existing patterns and keep dependencies minimal.

Preserve the core behavior: high-confidence matching is automatic; existing
HLTB records receive session deltas; new Steam records can start with lifetime
history. Preserve other account fields and never automatically complete a game.
Persist write intent and reconcile uncertain responses without blind retries.

Never include credentials, cookies, private account payloads or raw HTTP errors
in commits, screenshots, issues or logs. Keep private development files under
ignored `.local/`. Do not read or export browser or Playnite cookies.

## Prepare a pull request

- Link the issue and explain the resulting behavior, not just the files changed.
- Keep the change focused. Avoid unrelated refactoring or formatting churn.
- Add meaningful regression coverage for behavior changes. Describe what was
  tested locally, what was tested on hardware and what remains unverified.
- Run `pnpm test`, `pnpm typecheck` and `pnpm build` before submitting code changes.
  For documentation-only changes, check links and formatting; say that code
  checks were not run.
- Follow the [on-device acceptance procedure](docs/acceptance.md) for hardware
  tests. Installation, account writes and publication need separate authorization
  from the device/account owner. Never restart Steam or Decky during gameplay.
- Be available to answer review questions and address regressions in your change.

Pull requests without a linked issue may be returned for discussion first.
Documentation corrections also need an issue, but a short explanation is enough.

Contributions are made under this repository's [MIT license](LICENSE). Preserve
the licenses, notices and attribution of any reused material.

The issue-first workflow is inspired by
[FreeTube's contribution guidelines](https://github.com/FreeTubeApp/FreeTube/blob/development/CONTRIBUTING.md)
and adapted to this project.
