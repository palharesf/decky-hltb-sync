"""Decky entry point. Account writes require reviewed, persistent proposals."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'py_modules'))
from hltb_sync.store import Store
from hltb_sync.browser import BrowserSession, IntegrationError
from hltb_sync.client import HLTBClient, summary
from hltb_sync.service import Service


class Plugin:
    async def _main(self):
        import decky
        self.store = Store(Path(decky.DECKY_PLUGIN_SETTINGS_DIR) / 'private' / 'sessions.sqlite3')
        self.store.recover()
        browser = BrowserSession()
        browser.target_id = self.store.preference('browser_target')
        self.service = Service(self.store, HLTBClient(browser))
        self.login_task = None
        self.worker = asyncio.create_task(self._worker())

    async def _worker(self):
        while True:
            await asyncio.sleep(5)
            try:
                async with self.service.lock:
                    if self.service.auth == 'connected':
                        await self.service.auto_sync()
            except Exception:
                self.service.error = 'automatic_sync_needs_attention'

    async def _wait_for_login(self):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            await asyncio.sleep(2)
            try:
                async with self.service.lock:
                    await self.service.refresh_library()
                    self.store.set_preference('browser_target', self.service.client.browser.target_id)
                    self.service.error = None
                return
            except Exception:
                pass
        self.service.auth = 'disconnected'
        self.service.error = 'login_timed_out'

    async def status(self):
        if not hasattr(self, 'service'):
            return {'ok': False, 'error': 'backend_starting'}
        return {'ok': True, 'data': self.service.status()}

    async def observe(self, epoch: str, sequence: int, apps: list, event: str):
        if not hasattr(self, 'service'):
            return {'ok': False, 'error': 'backend_starting'}
        try:
            # Observations must continue while network operations are pending.
            self.service.observe(epoch, sequence, apps, event)
            return {'ok': True, 'data': None}
        except Exception:
            return {'ok': False, 'error': 'observation_failed'}

    async def command(self, action: str, args: dict):
        if not hasattr(self, 'service'):
            return {'ok': False, 'error': 'backend_starting'}
        service = self.service
        try:
            async with service.lock:
                if action == 'connect':
                    if self.login_task:
                        self.login_task.cancel()
                    result = await service.connect()
                    self.login_task = asyncio.create_task(self._wait_for_login())
                elif action == 'disconnect':
                    service.background_client = None
                    if self.login_task:
                        self.login_task.cancel()
                    service.client.browser.disconnect()
                    service.client.user_id = None
                    service.auth = 'disconnected'
                    service.library_cache = []
                    service.library_loaded = False
                    self.store.set_preference('browser_target', None)
                    self.store.set_preference('connected_user', None)
                    self.store.set_preference('library_cache', [])
                    with self.store.db:
                        self.store.db.execute('UPDATE apps SET automatic=0')
                    for operation in self.store.operations():
                        self.store.set_preference('auto_after:' + operation['id'], False)
                    result = None
                elif action == 'library':
                    result = await service.refresh_library()
                    self.store.set_preference('browser_target', service.client.browser.target_id)
                elif action == 'prepare_background':
                    result = await service.prepare_background()
                elif action == 'prepare_restore':
                    result = await service.prepare_restore()
                elif action == 'retain_background':
                    result = await service.retain_background()
                elif action == 'search':
                    result = await service.client.search(args['query'])
                elif action == 'resolve_match':
                    result = await service.resolve_match(args['app'])
                elif action == 'read':
                    result = summary(await service.client.read(args['submissionId']))
                elif action == 'bind':
                    result = await service.bind(args['app'], args['submissionId'], args['mode'])
                elif action == 'ack_match':
                    result = service.acknowledge_match(args['appId'], args.get('notice'))
                elif action == 'preview':
                    result = await service.prepare(args['appId'], args.get('steamMinutes'))
                elif action == 'preview_import':
                    result = await service.prepare_history_import(args['appId'], args['totalMinutes'], args.get('includesSaved'))
                elif action == 'create':
                    result = await service.prepare_create(args['app'], args['gameId'], args['title'], args['platform'])
                elif action == 'send':
                    result = await service.send(args['id'], args.get('approved'), args.get('enableAutomatic', False))
                elif action == 'reconcile':
                    result = await service.reconcile(args['id'])
                elif action == 'review':
                    result = await service.remote_review(args['appId'])
                elif action == 'accept_remote':
                    result = await service.accept_remote(args['appId'], args['expectedSeconds'])
                elif action == 'resolve':
                    result = await service.resolve(args['id'], args['decision'])
                elif action == 'adopt_created_record':
                    result = await service.adopt_created_record(args['id'], args['submissionId'])
                elif action == 'cancel':
                    result = service.cancel_prepared(args['id'])
                elif action == 'checkpoint':
                    result = service.accept_checkpoint(args['id'])
                elif action == 'discard_checkpoint':
                    result = service.discard_checkpoint(args['id'])
                elif action == 'automatic':
                    result = service.set_automatic(args['appId'], args['enabled'], args.get('singleWriter'))
                else:
                    return {'ok': False, 'error': 'unknown_command'}
                service.error = None
                return {'ok': True, 'data': result}
        except IntegrationError as exc:
            service.error = str(exc)
            if str(exc) in ('login_required', 'browser_closed_or_navigated', 'connect_required'):
                service.auth = 'reconnect_required'
            return {'ok': False, 'error': str(exc)}
        except (ValueError, PermissionError) as exc:
            return {'ok': False, 'error': str(exc)}
        except Exception:
            return {'ok': False, 'error': 'operation_failed_review_required'}

    async def _unload(self):
        tasks = [t for t in (getattr(self, 'worker', None), getattr(self, 'login_task', None)) if t]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if hasattr(self, 'store'):
            self.store.recover()
            self.store.close()

    async def _uninstall(self):
        # Retain unsynced data. Website logout is separate from disconnect.
        pass
