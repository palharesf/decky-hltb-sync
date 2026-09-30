# Repository conventions

- Use English for code, UI text, documentation, filenames, and commit messages.
- Keep private development data under `.local/`, which must remain ignored.
- Never log credentials, browser cookies, account payloads, or raw HTTP errors.
- Do not read or export browser/Playnite cookies. Use same-origin requests in the
  HLTB browser target explicitly connected through the plugin.
- Preserve existing HLTB fields. Never automatically mark a game completed.
- Persist write intent before sending; reconcile uncertain outcomes without retrying.
- Run `pnpm test`, `pnpm typecheck`, and `pnpm build` before shipping changes.
- Installation on hardware, account writes, and store publication are separate
  authorization steps. Do not restart Steam or Decky during gameplay.
