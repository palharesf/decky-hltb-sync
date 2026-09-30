import asyncio
import tempfile
import unittest
from pathlib import Path
from test_integration import FakeClient, APP
from hltb_sync.store import Store
from hltb_sync.service import Service
import main


class PluginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Path('.local').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir='.local')
        self.plugin = main.Plugin()
        self.plugin.store = Store(Path(self.temp.name) / 'test.sqlite3')
        self.plugin.service = Service(self.plugin.store, FakeClient(), lambda: 1)
        self.plugin.login_task = None

    async def asyncTearDown(self):
        await self.plugin._unload()
        self.temp.cleanup()

    async def test_command_whitelist_and_safe_errors(self):
        result = await self.plugin.command('arbitrary_python', {})
        self.assertFalse(result['ok'])
        result = await self.plugin.command('read', {})
        self.assertEqual(result['error'], 'operation_failed_review_required')

    async def test_observation_does_not_wait_for_network_lock(self):
        await self.plugin.service.bind(APP, 3, 'sessions')
        async with self.plugin.service.lock:
            result = await asyncio.wait_for(self.plugin.observe('test', 0, [APP], 'snapshot'), timeout=1)
        self.assertTrue(result['ok'])
        self.assertEqual(len(self.plugin.store.sessions()), 1)

    async def test_submit_rpc_requires_explicit_approval(self):
        await self.plugin.service.bind(APP, 3, 'sessions')
        self.plugin.store.event('a', '999', 'start', 'test', 0)
        self.plugin.store.event('b', '999', 'stop', 'test', 10)
        proposal = await self.plugin.service.prepare('999')
        result = await self.plugin.command('send', {'id': proposal['id']})
        self.assertFalse(result['ok'])
        self.assertEqual(self.plugin.service.client.writes, 0)
