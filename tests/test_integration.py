import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_core import record
from hltb_sync.browser import BrowserSession, CEF, IntegrationError, is_hltb
from hltb_sync.client import HLTBClient, new_record
from hltb_sync.records import seconds
from hltb_sync.service import Service
from hltb_sync.store import Store

APP = {'id': '999', 'name': 'Example PS2 game', 'steam': False, 'minutes': None}


class FakeClient:
    def __init__(self):
        self.remote = record()
        self.remote['title'] = 'Example PS2 game'
        self.user_id = 1
        self.writes = 0
        self.fail = None
        self.exists = True

    async def read(self, submission):
        if self.fail == 'offline':
            raise IntegrationError('network_or_session_error')
        return copy.deepcopy(self.remote)

    async def library(self):
        if self.fail == 'offline':
            raise IntegrationError('network_or_session_error')
        return ([{'gameId': self.remote['gameId'], 'submissionId': self.remote['submissionId'],
                  'title': self.remote['title'], 'platform': self.remote['platform'],
                  'seconds': seconds(self.remote), 'lists': ['Playing']}] if self.exists else [])

    async def submit(self, payload):
        self.writes += 1
        if self.fail != 'before':
            self.remote = copy.deepcopy(payload)
            if self.remote['submissionId'] == 0:
                self.remote['submissionId'] = 123
                self.remote['userName'] = 'Synthetic account'
                self.exists = True
        if self.fail in ('before', 'after'):
            raise TimeoutError('PRIVATE ERROR MUST NOT ESCAPE')


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Path('.local').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=Path('.local'))
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)
        self.client = FakeClient()
        self.tick = 0
        self.service = Service(self.store, self.client, lambda: self.tick)
        await self.service.bind(APP, 3, 'sessions')
        self.seq = 0

    async def asyncTearDown(self):
        self.store.close()
        self.temp.cleanup()

    def observe(self, tick, apps=None, event='snapshot', epoch='epoch'):
        self.tick = tick
        self.service.observe(epoch, self.seq, [APP] if apps is None else apps, event)
        self.seq += 1

    async def proposal(self):
        self.observe(0)
        self.observe(10)
        self.observe(20, [])
        return await self.service.prepare('999')

    async def test_full_session_to_verified_operation(self):
        proposal = await self.proposal()
        self.assertEqual(proposal['after'] - proposal['before'], 20)
        self.assertTrue(await self.service.send(proposal['id'], True))
        self.assertEqual(self.store.sessions()[0]['state'], 'synced')
        self.assertEqual(self.client.remote['review'], record()['review'])
        self.assertFalse(self.client.remote['lists']['completed'])
        with self.assertRaises(ValueError):
            await self.service.send(proposal['id'], True)
        self.assertEqual(self.client.writes, 1)

    async def test_never_tracks_unmapped_launchers(self):
        self.observe(0, [{'id': '888', 'name': 'ES-DE', 'steam': False, 'minutes': None}])
        self.assertEqual(self.store.sessions(), [])

    async def test_suspend_empty_running_apps_does_not_close_session(self):
        self.observe(0)
        self.observe(10, [], 'suspend')
        self.observe(20, [])
        self.assertEqual(self.store.sessions()[0]['phase'], 'suspended')
        self.observe(900, [], 'resume')
        self.observe(910)
        self.observe(920, [])
        self.assertEqual(self.store.sessions()[0]['elapsed'], 30)

    async def test_reload_and_stale_epoch_preserve_checkpoint(self):
        self.observe(0)
        self.observe(10)
        self.observe(20, epoch='new')
        self.observe(30, epoch='epoch')
        self.assertEqual(len(self.store.sessions()), 2)
        self.assertEqual(self.store.sessions()[1]['elapsed'], 10)
        self.assertEqual(self.store.sessions()[1]['state'], 'attention')

    async def test_unavailable_is_not_game_exit(self):
        self.observe(0)
        self.observe(10)
        self.observe(20, [], 'unavailable')
        self.assertEqual(self.store.sessions()[0]['phase'], 'interrupted')
        self.assertEqual(self.store.sessions()[0]['elapsed'], 10)

    async def test_offline_preserves_sessions(self):
        self.observe(0)
        self.observe(10, [])
        self.client.fail = 'offline'
        with self.assertRaises(IntegrationError):
            await self.service.prepare('999')
        self.assertEqual(self.store.sessions()[0]['state'], 'pending')
        self.assertEqual(self.store.operations(), [])

    async def test_approval_is_required(self):
        proposal = await self.proposal()
        with self.assertRaises(PermissionError):
            await self.service.send(proposal['id'], False)
        self.assertEqual(self.client.writes, 0)

    async def test_uncertain_write_reconciles_without_duplicate(self):
        proposal = await self.proposal()
        self.client.fail = 'after'
        self.assertFalse(await self.service.send(proposal['id'], True))
        self.assertEqual(self.store.operation(proposal['id'])['state'], 'uncertain')
        self.assertTrue(await self.service.reconcile(proposal['id']))
        self.assertEqual(self.client.writes, 1)

    async def test_manual_resolution_requires_decision_and_disables_auto(self):
        proposal = await self.proposal()
        self.client.fail = 'before'
        await self.service.send(proposal['id'], True)
        with self.assertRaises(ValueError):
            await self.service.resolve(proposal['id'], 'retry')
        await self.service.resolve(proposal['id'], 'not_included')
        self.assertEqual(self.store.sessions()[0]['state'], 'pending')
        self.assertEqual(self.store.operation(proposal['id'])['resolution'], 'not_included')

    async def test_playnite_changes_before_send_are_blocked(self):
        proposal = await self.proposal()
        self.client.remote['review']['notes'] = 'Edited on PC'
        self.assertFalse(await self.service.send(proposal['id'], True))
        self.assertEqual(self.client.writes, 0)
        self.assertEqual(self.store.operation(proposal['id'])['state'], 'conflict')

    async def test_rebase_preserves_pending_sessions(self):
        self.observe(0)
        self.observe(10, [])
        self.client.remote['general']['progress']['hours'] = 2
        with self.assertRaises(IntegrationError):
            await self.service.prepare('999')
        review = await self.service.remote_review('999')
        await self.service.accept_remote('999', review['current']['seconds'])
        proposal = await self.service.prepare('999')
        self.assertEqual(proposal['after'] - proposal['before'], 10)

    async def test_automatic_requires_manual_verified_session_and_policy(self):
        with self.assertRaises(ValueError):
            self.service.set_automatic('999', True, True)
        proposal = await self.proposal()
        await self.service.send(proposal['id'], True)
        with self.assertRaises(ValueError):
            self.service.set_automatic('999', True, False)
        self.service.set_automatic('999', True, True)
        self.observe(30)
        self.observe(40, [])
        await self.service.auto_sync()
        await self.service.auto_sync()
        self.assertEqual(self.client.writes, 2)

    async def test_steam_total_is_assignment_not_addition(self):
        self.store.db.execute("UPDATE apps SET steam=1,mode='steam_total' WHERE app='999'")
        self.store.db.commit()
        proposal = await self.service.prepare('999', 120)
        self.assertEqual(proposal['after'], 7200)
        await self.service.send(proposal['id'], True)
        self.assertEqual(seconds(self.client.remote), 7200)
        with self.assertRaises(ValueError):
            await self.service.prepare('999', 119)

    async def test_stale_steam_total_does_not_consume_pending_sessions(self):
        self.client.remote['general']['progress'] = {'hours': 1, 'minutes': 0, 'seconds': 0}
        self.store.db.execute('UPDATE mappings SET record=? WHERE app=?', (json.dumps(self.client.remote, sort_keys=True, separators=(',', ':')), '999'))
        self.store.db.execute("UPDATE apps SET steam=1,mode='steam_total' WHERE app='999'")
        self.store.db.commit()
        self.observe(0)
        self.observe(10, [])
        with self.assertRaises(ValueError):
            await self.service.prepare('999', 60)
        self.assertEqual(self.store.sessions()[0]['state'], 'pending')
        self.assertEqual(self.client.writes, 0)

    async def test_only_nonzero_sessions_can_be_prepared(self):
        self.observe(0)
        with self.assertRaises(ValueError):
            await self.service.prepare('999')

    async def test_creation_checks_all_records_and_requires_approval(self):
        app = {**APP, 'id': '888'}
        with self.assertRaises(ValueError):
            await self.service.prepare_create(app, 2, 'Example', 'PlayStation 2')
        self.client.exists = False
        proposal = await self.service.prepare_create(app, 2, 'Example', 'PlayStation 2')
        self.assertEqual(proposal['after'], 0)
        self.assertEqual(self.client.writes, 0)
        self.assertTrue(await self.service.send(proposal['id'], True))
        self.assertEqual(self.store.mapping('888')['submissionId'], 123)
        self.assertTrue(self.client.remote['lists']['playing'])
        self.assertFalse(self.client.remote['lists']['completed'])

    async def test_creation_timeout_does_not_create_twice(self):
        self.client.exists = False
        proposal = await self.service.prepare_create({**APP, 'id': '888'}, 2, 'Example', 'PlayStation 2')
        self.client.fail = 'after'
        self.assertFalse(await self.service.send(proposal['id'], True))
        self.assertTrue(await self.service.reconcile(proposal['id']))
        self.assertEqual(self.client.writes, 1)

    async def test_cancel_does_not_discard_pending_time(self):
        proposal = await self.proposal()
        self.service.cancel_prepared(proposal['id'])
        again = await self.service.prepare('999')
        self.assertEqual(again['after'], proposal['after'])

    async def test_crash_keeps_operation_uncertain(self):
        proposal = await self.proposal()
        self.store.operation_state(proposal['id'], 'prepared', 'sending')
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.assertEqual(self.store.operation(proposal['id'])['state'], 'uncertain')
        self.assertEqual(self.store.sessions()[0]['state'], 'attention')

    async def test_creation_normalization_can_adopt_explicit_existing_record(self):
        self.client.exists = False
        proposal = await self.service.prepare_create({**APP, 'id': '888'}, 2, 'Example', 'PlayStation 2')
        self.client.fail = 'after'
        await self.service.send(proposal['id'], True)
        self.client.remote['general']['progressBefore']['hours'] = 0
        self.assertFalse(await self.service.reconcile(proposal['id']))
        await self.service.adopt_created_record(proposal['id'], 123)
        self.assertEqual(self.client.writes, 1)
        self.assertEqual(self.store.mapping('888')['submissionId'], 123)
        self.assertEqual(self.store.operation(proposal['id'])['state'], 'resolved')

    async def test_schema_one_migrates_legacy_pending_jobs(self):
        self.store.event('start', '999', 'start', 'old', 0)
        self.store.event('stop', '999', 'stop', 'old', 10)
        job = self.store.prepare(self.store.sessions()[0]['id'], self.client.remote)
        self.store.transition(job['id'], 'prepared', 'sending')
        self.store.db.execute('PRAGMA user_version=1')
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.assertEqual(self.store.operation(job['id'])['state'], 'uncertain')
        self.assertEqual(self.store.sessions()[0]['elapsed'], 10)

    async def test_review_does_not_expose_notes(self):
        review = await self.service.remote_review('999')
        self.assertNotIn('Private note', json.dumps(review))
        self.assertNotIn('Private note', json.dumps(self.service.status()))

    async def test_empty_library_is_not_mistaken_for_stale_cache(self):
        self.client.exists = False
        await self.service.refresh_library()
        self.assertFalse(self.service.status()['libraryCached'])


class FakeBrowser:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def request(self, path, payload=None, **kwargs):
        self.calls.append((path, payload, kwargs))
        response = self.responses[path]
        return response if isinstance(response, str) else json.dumps(response)


class ClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_identity_expired_and_account_switch(self):
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]}})
        client = HLTBClient(browser)
        self.assertEqual(await client.identity(), 1)
        browser.responses['/api/user'] = {'data': [{'user_id': 2}]}
        with self.assertRaisesRegex(IntegrationError, 'account_changed'):
            await client.identity()
        browser.responses['/api/user'] = {}
        with self.assertRaisesRegex(IntegrationError, 'login_required'):
            await client.identity()

    async def test_library_rejects_truncated_results(self):
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]},
            '/api/user/1/games/list': {'data': {'gamesList': [], 'total': 1}}})
        with self.assertRaisesRegex(IntegrationError, 'incomplete'):
            await HLTBClient(browser).library()

    async def test_library_statuses_and_contract(self):
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]},
            '/api/user/1/games/list': {'data': {'gamesList': [{'id': 3, 'game_id': 2,
                'custom_title': 'Example', 'platform': 'PlayStation 2', 'invested_pro': 200,
                'list_comp': 1}], 'total': 1}}})
        entries = await HLTBClient(browser).library()
        self.assertEqual(entries[0]['lists'], ['Completed'])
        self.assertEqual(browser.calls[-1][1]['limit'], 5000)

    async def test_record_identity_and_lossless_read(self):
        full = new_record(1, 2, 'Example', 'PlayStation 2')
        full.update(record())
        html = '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': {'editData': full}}}) + '</script>'
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]}, '/submit/edit/3': html, '/submit/edit/4': html})
        self.assertEqual(await HLTBClient(browser).read(3), full)
        with self.assertRaisesRegex(IntegrationError, 'identity'):
            await HLTBClient(browser).read(4)

    async def test_partial_edit_payload_cannot_become_a_replacement_update(self):
        html = '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': {'editData': record()}}}) + '</script>'
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]}, '/submit/edit/3': html})
        with self.assertRaisesRegex(IntegrationError, 'incomplete_edit_record'):
            await HLTBClient(browser).read(3)

    async def test_submit_rejects_html_success_and_checks_account(self):
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]}, '/api/submit': '<html>Login</html>'})
        client = HLTBClient(browser)
        with self.assertRaises(IntegrationError):
            await client.submit(record())
        self.assertEqual(browser.calls[-1][2]['referrer'], '/submit/edit/3')


class FakeCEF:
    def __init__(self):
        self.pages = [{'id': 'old', 'url': 'https://howlongtobeat.com/user/example'}]
        self.expression = ''

    def targets(self):
        return self.pages

    def evaluate(self, target, expression):
        self.expression = expression
        return {'status': 200, 'text': '{}'}


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_binds_new_target_only_and_keeps_cookies_in_browser(self):
        cef = FakeCEF()
        browser = BrowserSession(cef)
        url = await browser.begin()
        with self.assertRaises(IntegrationError):
            await browser.target()
        cef.pages.append({'id': 'new', 'url': url})
        await browser.request('/api/user')
        self.assertEqual(browser.target_id, 'new')
        self.assertIn('same-origin', cef.expression)
        self.assertIn('location.origin', cef.expression)
        self.assertNotIn('document.cookie', cef.expression)
        self.assertNotIn('Network.getCookies', cef.expression)
        cef.pages[1]['url'] = 'https://example.com/'
        with self.assertRaises(IntegrationError):
            await browser.request('/api/user')

    async def test_ambiguous_windows_are_not_claimed(self):
        cef = FakeCEF()
        browser = BrowserSession(cef)
        await browser.begin()
        cef.pages += [{'id': x, 'url': 'https://howlongtobeat.com/login'} for x in ['a', 'b']]
        with self.assertRaises(IntegrationError):
            await browser.target()

    async def test_origin_and_endpoint_validation(self):
        self.assertFalse(is_hltb('https://howlongtobeat.com.evil.test/'))
        self.assertFalse(is_hltb('http://howlongtobeat.com/'))
        with self.assertRaises(IntegrationError):
            CEF().evaluate({'webSocketDebuggerUrl': 'ws://example.com:8080/target'}, '1')
        browser = BrowserSession(FakeCEF())
        with self.assertRaises(IntegrationError):
            await browser.request('//example.com/')
