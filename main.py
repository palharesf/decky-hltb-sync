"""Decky entry point. No network writes or browser credential access."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'py_modules'))
from hltb_sync.store import Store


class Plugin:
    async def _main(self):
        import decky
        # Persistent, private settings path; never use a public /plugins/.../data URL.
        self.store = Store(Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / 'private' / 'sessions.sqlite3')
        self.store.recover()

    async def status(self):
        return {'sessions': self.store.sessions(), 'mode': 'local-pilot',
                'auth': 'not-validated', 'automatic': False}

    async def _unload(self):
        if hasattr(self, 'store'):
            self.store.recover()
            self.store.close()

    async def _uninstall(self):
        # Preserve unsynced sessions. Deletion requires a separate explicit action.
        pass
