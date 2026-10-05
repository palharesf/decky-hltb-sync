# Install the public beta

Requires a Steam Deck with SteamOS and Decky Loader already installed. The
plugin runs locally on the Deck; a PC or SSH bridge is not needed for normal use.
Read the [known limitations](../README.md#known-beta-limitations) first.

1. Close any running game before installing or updating.
2. Open the [0.3.17 beta release](https://github.com/palharesf/decky-hltb-sync/releases/tag/v0.3.17).
   Use the attached `hltb-sync-for-deck-0.3.17.zip`, not GitHub's source archives.
3. On the Deck, open **Quick Access Menu > Decky > Settings** (gear icon).
   Enable **Developer mode** in **General** if the **Developer** page is hidden.
4. In **Developer**, use **Install Plugin from URL**, paste the URL below and
   choose **Install**. Alternatively, download the asset on the Deck and use
   **Install Plugin from ZIP File** to select it. Confirm the installation dialog.

   ```text
   https://github.com/palharesf/decky-hltb-sync/releases/download/v0.3.17/hltb-sync-for-deck-0.3.17.zip
   ```

5. Open **Quick Access Menu > Decky > HLTB Sync for Deck** and select
   **Connect to HLTB**. Sign in on the official HLTB page. The plugin should
   return to its panel with **Connected** after recognizing the session.
6. Launch a game normally and close it when finished. A high-confidence match
   syncs automatically. Check the session status in the plugin.

Menu wording can vary with the Decky version. This release is not in the plugin
catalog. Update through the same manual installation flow; existing plugin
settings and sessions are retained. Do not delete plugin settings to update.

## Time and recovery

Existing HLTB records receive only newly captured sessions. A new Steam record
starts with Steam lifetime once, including the current session rather than
adding it twice. **Import past hours once** is an explicit advanced option.
Suspended time is excluded; games are never automatically marked completed.

Use direct Non-Steam game shortcuts for emulators. Steam's Non-Steam playtime
display may disagree with HLTB; the plugin does not write Steam playtime.

**Pending** means the session is saved locally. Restore the network or reconnect
the account as needed. **Review** means attention is required. An interrupted
session offers **Sync recovered time** or **Discard session**, followed by
**Confirm discard**. Discard removes only that segment from future sync; it
does not subtract existing HLTB time. Closing the dialog keeps the saved segment.
An uncertain submission must be reconciled before another send.

## Verify the download

The release includes a matching `.zip.sha256` file. In Desktop Mode, download
both assets to the same directory, open a terminal there and run:

```sh
sha256sum -c hltb-sync-for-deck-0.3.17.zip.sha256
```

For problems, search [existing issues](https://github.com/palharesf/decky-hltb-sync/issues)
before opening one. Include plugin, SteamOS and Decky versions, the game type
and reproduction steps. Never attach cookies, passwords or account payloads.
