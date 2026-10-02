import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from test_core import record
from hltb_sync.browser import BrowserSession, CEF, IntegrationError, is_hltb
from hltb_sync.client import HLTBClient, new_record
from hltb_sync.records import seconds
from hltb_sync.service import Service
from hltb_sync.store import Store
from hltb_sync.matching import suggest

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
    async def steam_unmapped(self, existing=False, matching_id=True):
        with self.store.db:
            self.store.db.execute('DELETE FROM mappings')
        app = {'id': '888', 'name': 'Example Steam game', 'steam': True, 'minutes': 841}
        self.client.exists = existing
        if existing:
            self.client.remote['title'] = app['name']
            self.client.remote['platform'] = 'PC'
        self.client.search = AsyncMock(return_value=[{'gameId': 2, 'title': app['name']}])
        self.client.game_identity = AsyncMock(return_value={'gameId': 2, 'title': app['name'],
            'steamId': app['id'] if matching_id else '123', 'platforms': ['PC']})
        self.observe(0, [app])
        self.observe(10, [app])
        self.observe(20, [])
        return app

    async def test_auto_steam_creation_imports_lifetime_once_without_adding_session_twice(self):
        app = await self.steam_unmapped()
        self.assertEqual(await self.service.resolve_match(app), {'state': 'linked'})
        self.assertEqual(seconds(self.client.remote), 841 * 60)
        self.assertEqual(self.client.writes, 1)
        self.assertTrue(self.service.history_imported(app['id']))
        self.assertTrue(self.store.app(app['id'])['automatic'])
        self.assertTrue(self.client.remote['lists']['playing'])
        self.assertFalse(self.client.remote['lists']['completed'])
        self.assertEqual(self.store.sessions()[0]['state'], 'synced')
        await self.service.resolve_match(app)
        self.assertEqual(self.client.writes, 1)
        self.observe(30, [app])
        self.observe(40, [])
        await self.service.auto_sync()
        self.assertEqual(seconds(self.client.remote), 841 * 60 + 10)

    async def test_auto_steam_existing_record_adds_session_and_preserves_every_other_field(self):
        app = await self.steam_unmapped(existing=True)
        expected = copy.deepcopy(self.client.remote)
        from hltb_sync.records import proposed
        expected = proposed(expected, 20)
        self.assertEqual(await self.service.resolve_match(app), {'state': 'linked'})
        self.assertEqual(self.client.remote, expected)
        self.assertFalse(self.service.history_imported(app['id']))
        self.assertEqual(self.store.operations()[0]['kind'], 'sessions')
        self.assertTrue(self.store.app(app['id'])['automatic'])
        await self.service.resolve_match(app)
        self.assertEqual(self.client.writes, 1)
        self.client.search.assert_not_awaited()

    async def test_auto_steam_creation_timeout_never_retries_and_marks_import_after_reconcile(self):
        app = await self.steam_unmapped()
        self.client.fail = 'after'
        self.assertEqual(await self.service.resolve_match(app), {'state': 'attention'})
        self.assertFalse(self.service.history_imported(app['id']))
        await self.service.resolve_match(app)
        self.assertEqual(self.client.writes, 1)
        self.client.fail = None
        operation = self.store.operations()[0]
        self.assertTrue(await self.service.reconcile(operation['id']))
        self.assertTrue(self.service.history_imported(app['id']))
        self.assertEqual(seconds(self.client.remote), 841 * 60)

    async def test_created_record_omitted_empty_editor_defaults_reconcile_without_resend(self):
        app = await self.steam_unmapped()
        self.client.fail = 'after'
        await self.service.resolve_match(app)
        for key in ('adminId', 'customLabels', 'manualTimer'):
            self.client.remote.pop(key)
        self.client.remote['general'].pop('progressBefore')
        operation = self.store.operations()[0]
        self.client.remote['review']['notes'] = 'Must not be ignored'
        self.assertFalse(await self.service.reconcile(operation['id']))
        self.client.remote['review']['notes'] = ''
        self.assertTrue(await self.service.reconcile(operation['id']))
        self.assertEqual(self.client.writes, 1)
        self.assertEqual(seconds(self.client.remote), 841 * 60)
        self.assertTrue(self.service.history_imported(app['id']))

    async def test_auto_steam_wrong_identity_or_missing_total_never_writes(self):
        app = await self.steam_unmapped(matching_id=False)
        self.assertEqual((await self.service.resolve_match(app))['state'], 'ambiguous')
        self.assertEqual(self.client.writes, 0)
        self.client.game_identity.return_value['steamId'] = app['id']
        with self.assertRaises(ValueError):
            await self.service.resolve_match({**app, 'minutes': None})
        self.assertEqual(self.client.writes, 0)
        self.assertIsNone(self.store.mapping(app['id']))

    async def test_auto_steam_lower_total_does_not_block_adding_to_existing_record(self):
        app = await self.steam_unmapped(existing=True)
        self.client.remote['general']['progress'] = {'hours': 100, 'minutes': 0, 'seconds': 0}
        self.assertEqual(await self.service.resolve_match(app), {'state': 'linked'})
        self.assertEqual(seconds(self.client.remote), 100 * 3600 + 20)
        self.assertEqual(self.client.writes, 1)

    async def test_existing_record_does_not_require_steam_lifetime(self):
        app = await self.steam_unmapped(existing=True)
        before = seconds(self.client.remote)
        self.assertEqual(await self.service.resolve_match({**app, 'minutes': None}), {'state': 'linked'})
        self.assertEqual(seconds(self.client.remote), before + 20)

    async def test_existing_record_at_same_steam_total_still_receives_new_session(self):
        app = await self.steam_unmapped(existing=True)
        self.client.remote['general']['progress'] = {'hours': 14, 'minutes': 1, 'seconds': 0}
        self.assertEqual(await self.service.resolve_match(app), {'state': 'linked'})
        self.assertEqual(seconds(self.client.remote), 841 * 60 + 20)

    async def test_catalog_identity_reuses_renamed_record_with_session_delta(self):
        app = await self.steam_unmapped(existing=True)
        self.client.remote['title'] = 'Custom library title'
        before = seconds(self.client.remote)
        self.assertEqual(await self.service.resolve_match(app), {'state': 'linked'})
        self.assertEqual(seconds(self.client.remote), before + 20)
        self.assertEqual(self.client.remote['title'], 'Custom library title')
        self.assertEqual(self.store.operations()[0]['kind'], 'sessions')

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

    async def test_unmapped_session_survives_offline_suspend_restart_and_binding(self):
        with self.store.db:
            self.store.db.execute('DELETE FROM mappings')
        app = {**APP, 'platform': 'PlayStation 2', 'platformSource': 'ROM folder'}
        self.observe(0, [app])
        self.observe(10, [], 'suspend')
        self.observe(1000, [], 'resume')
        self.observe(1010, [])
        self.assertEqual(self.store.sessions()[0]['elapsed'], 20)
        self.client.fail = 'offline'
        with self.assertRaises(IntegrationError):
            await self.service.refresh_library()
        self.assertEqual(len(self.service.match_requests()), 1)
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.service = Service(self.store, self.client, lambda: self.tick)
        self.client.fail = None
        await self.service.refresh_library()
        request = self.service.match_requests()[0]
        self.assertEqual(request['recommended'], 3)
        self.assertEqual(request['app']['platform'], 'PlayStation 2')
        self.service.acknowledge_match(APP['id'])
        self.assertIsNone(self.service.match_requests()[0]['notice'])
        self.assertEqual(len(self.store.sessions()), 1)
        self.assertEqual(self.client.writes, 0)
        await self.service.bind(app, 3, 'sessions')
        self.assertEqual(self.service.match_requests(), [])
        proposal = await self.service.prepare(APP['id'])
        self.assertEqual(proposal['after'] - proposal['before'], 20)
        self.assertEqual(self.client.writes, 0)

    async def test_matching_does_not_preselect_ambiguous_or_wrong_platform_records(self):
        app = {**APP, 'platform': 'PlayStation 2'}
        entries = await self.client.library()
        self.assertEqual(suggest(app, entries)[1], 3)
        self.assertIsNone(suggest(app, entries + [{**entries[0], 'submissionId': 4}])[1])
        self.assertIsNone(suggest({**app, 'platform': 'PC'}, entries)[1])
        self.assertIsNone(suggest(APP, entries)[1])
        self.assertIsNone(suggest({**app, 'name': 'Example PS2'}, entries)[1])

    async def test_one_time_import_assigns_total_includes_sessions_and_keeps_future_deltas(self):
        self.observe(0); self.observe(10); self.observe(20, [])
        before = copy.deepcopy(self.client.remote)
        proposal = await self.service.prepare_history_import(APP['id'], 109, True)
        self.assertEqual(proposal['after'], 109 * 60)
        self.assertEqual(self.client.writes, 0)
        with self.assertRaises(PermissionError):
            await self.service.send(proposal['id'], False)
        self.assertTrue(await self.service.send(proposal['id'], True))
        self.assertEqual(self.store.sessions()[0]['state'], 'synced')
        self.assertEqual(self.store.app(APP['id'])['mode'], 'sessions')
        expected = copy.deepcopy(self.client.remote)
        expected['general']['progress'] = before['general']['progress']
        self.assertEqual(expected, before)
        self.store.close(); self.store = Store(self.path)
        self.service = Service(self.store, self.client, lambda: self.tick)
        with self.assertRaisesRegex(ValueError, 'already'):
            await self.service.prepare_history_import(APP['id'], 120, True)
        self.observe(30); self.observe(40, [])
        next_proposal = await self.service.prepare(APP['id'])
        self.assertEqual(next_proposal['before'], 6540)
        self.assertEqual(next_proposal['after'], 6550)

    async def test_import_requires_overlap_confirmation_and_blocks_decreases_or_open_proposals(self):
        with self.assertRaisesRegex(ValueError, 'Confirm'):
            await self.service.prepare_history_import(APP['id'], 109, False)
        with self.assertRaises(ValueError):
            await self.service.prepare_history_import(APP['id'], 1, True)
        with self.assertRaises(ValueError):
            await self.service.prepare_history_import(APP['id'], True, True)
        self.observe(0)
        with self.assertRaisesRegex(ValueError, 'Close'):
            await self.service.prepare_history_import(APP['id'], 109, True)
        self.observe(10, [])
        proposal = await self.service.prepare_history_import(APP['id'], 109, True)
        with self.assertRaisesRegex(ValueError, 'existing proposal'):
            await self.service.prepare_history_import(APP['id'], 109, True)
        self.service.cancel_prepared(proposal['id'])
        self.assertFalse(self.service.history_imported(APP['id']))
        await self.service.prepare_history_import(APP['id'], 109, True)
        self.assertEqual(self.client.writes, 0)

    async def test_uncertain_import_reconciles_without_duplicate_write(self):
        self.observe(0); self.observe(10, [])
        proposal = await self.service.prepare_history_import(APP['id'], 109, True)
        self.client.fail = 'after'
        self.assertFalse(await self.service.send(proposal['id'], True))
        with self.assertRaises(ValueError):
            await self.service.prepare_history_import(APP['id'], 109, True)
        self.client.fail = None
        self.assertTrue(await self.service.reconcile(proposal['id']))
        self.assertTrue(self.service.history_imported(APP['id']))
        self.assertEqual(self.client.writes, 1)

    async def test_dismissing_one_match_does_not_acknowledge_a_newer_session(self):
        app = {**APP, 'id': '888'}
        self.observe(0, [app]); self.observe(10, [])
        first = self.service.match_requests()[0]['notice']
        self.observe(20, [app]); self.observe(30, [])
        second = self.service.match_requests()[0]['notice']
        self.assertNotEqual(first, second)
        self.service.acknowledge_match(app['id'], first)
        self.assertEqual(self.service.match_requests()[0]['notice'], second)
        self.assertEqual(len(self.store.sessions()), 2)
        self.assertEqual(self.client.writes, 0)

    async def test_unmapped_interrupted_session_requires_attention_not_invented_time(self):
        app = {**APP, 'id': '888'}
        self.observe(0, [app])
        self.observe(10, [app])
        self.observe(500, [], 'unavailable')
        session = self.store.sessions()[0]
        self.assertEqual(session['elapsed'], 10)
        self.assertEqual(session['state'], 'attention')
        self.assertEqual(self.service.match_requests()[0]['seconds'], 10)

    async def test_emulator_ui_metadata_is_excluded_even_with_custom_shortcut_name(self):
        self.observe(0, [{**APP, 'id': '888', 'name': 'My launcher', 'excluded': True}])
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

    async def test_offline_autosync_status_waits_and_clears_after_reconnection(self):
        self.service.set_automatic(APP['id'], True)
        self.observe(0)
        self.observe(10, [])
        self.client.fail = 'offline'
        await self.service.auto_sync()
        self.assertEqual(self.service.error, 'sync_waiting_connection')
        self.assertEqual(self.store.sessions()[0]['state'], 'pending')
        self.assertEqual(self.store.operations(), [])
        self.client.fail = None
        await self.service.auto_sync()
        self.assertIsNone(self.service.error)
        self.assertEqual(self.store.sessions()[0]['state'], 'synced')
        self.assertEqual(self.client.writes, 1)

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

    async def test_reconcile_accepts_only_observed_server_metadata_normalization(self):
        self.client.remote['storefront'] = None
        self.client.remote['userIp'] = 'synthetic-before'
        with self.store.db:
            from hltb_sync.records import canonical
            self.store.db.execute('UPDATE mappings SET record=? WHERE app=?', (canonical(self.client.remote), APP['id']))
        proposal = await self.proposal()
        self.client.fail = 'after'
        await self.service.send(proposal['id'], True, enable_automatic=True)
        self.client.remote['storefront'] = ''
        self.client.remote['userIp'] = 'synthetic-after'
        self.client.remote['review']['notes'] = 'Unexpected user data change'
        self.assertFalse(await self.service.reconcile(proposal['id']))
        self.client.remote['review']['notes'] = record()['review']['notes']
        self.assertTrue(await self.service.reconcile(proposal['id']))
        self.assertEqual(self.client.writes, 1)
        self.assertTrue(self.store.app(APP['id'])['automatic'])
        self.assertEqual(self.store.mapping(APP['id'])['storefront'], '')

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

    async def test_confirm_and_sync_enables_later_sessions_without_extra_gates(self):
        proposal = await self.proposal()
        await self.service.send(proposal['id'], True, enable_automatic=True)
        self.assertTrue(self.store.app('999')['automatic'])
        self.observe(30)
        self.observe(40, [])
        await self.service.auto_sync()
        await self.service.auto_sync()
        self.assertEqual(self.client.writes, 2)

    async def test_import_confirmation_enables_autosync_but_uncertain_and_remote_changes_do_not_write_again(self):
        self.observe(0); self.observe(10, [])
        proposal = await self.service.prepare_history_import(APP['id'], 109, True)
        self.client.fail = 'after'
        self.assertFalse(await self.service.send(proposal['id'], True, enable_automatic=True))
        self.assertFalse(self.store.app(APP['id'])['automatic'])
        self.client.fail = None
        self.assertTrue(await self.service.reconcile(proposal['id']))
        self.assertTrue(self.store.app(APP['id'])['automatic'])
        self.observe(20); self.observe(30, [])
        self.client.remote['general']['progress']['minutes'] += 1
        await self.service.auto_sync()
        self.assertEqual(self.client.writes, 1)
        self.assertEqual(self.service.error, 'automatic_sync_needs_attention')

    async def test_disabling_auto_revokes_pending_enable_after_reconciliation(self):
        proposal = await self.proposal()
        self.client.fail = 'after'
        await self.service.send(proposal['id'], True, enable_automatic=True)
        self.service.set_automatic(APP['id'], False)
        self.client.fail = None
        await self.service.reconcile(proposal['id'])
        self.assertFalse(self.store.app(APP['id'])['automatic'])

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
    async def test_search_accepts_token_only_init_and_validates_game_steam_identity(self):
        browser = FakeBrowser({'/api/search/site/init?t=1000': {'token': 'synthetic'},
            '/api/search/site': {'data': [{'game_id': 2, 'game_name': 'Example'}]},
            '/game/2': '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': {
                'game': {'data': {'game': [{'game_id': 2, 'game_name': 'Example',
                    'profile_steam': 888, 'profile_platform': 'Mac, PC'}]}}}}}) + '</script>'})
        client = HLTBClient(browser)
        with patch('hltb_sync.client.time.time', return_value=1):
            self.assertEqual((await client.search('Example'))[0]['gameId'], 2)
        headers = browser.calls[-1][2]['headers']
        self.assertEqual(headers, {'x-auth-token': 'synthetic'})
        identity = await client.game_identity(2)
        self.assertEqual(identity['steamId'], '888')
        self.assertEqual(identity['platforms'], ['Mac', 'PC'])

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

    async def test_current_saved_record_omits_editor_only_fields_without_losing_data(self):
        full = new_record(1, 2, 'Example', 'PlayStation 2')
        full.update(record())
        for key in ('manualTimer', 'customLabels'):
            full.pop(key)
        full['general'].pop('progressBefore', None)
        html = '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': {'editData': full}}}) + '</script>'
        browser = FakeBrowser({'/api/user': {'data': [{'user_id': 1}]}, '/submit/edit/3': html})
        loaded = await HLTBClient(browser).read(3)
        self.assertEqual(loaded, full)
        from hltb_sync.records import proposed
        updated = proposed(loaded, 25)
        updated['general']['progress'] = full['general']['progress']
        self.assertEqual(updated, full)

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
    async def test_background_handoff_requires_marked_target_and_same_account(self):
        class AccountCEF(FakeCEF):
            other_account = False

            def evaluate(self, target, expression):
                if '/games/list' in expression:
                    data = {'data': {'gamesList': [], 'total': 0}}
                else:
                    user = 2 if self.other_account and target['id'] == 'retained' else 1
                    data = {'data': [{'user_id': user}]}
                return {'status': 200, 'text': json.dumps(data)}

        with tempfile.TemporaryDirectory(dir=Path('.local')) as directory:
            store = Store(Path(directory) / 'sessions.sqlite3')
            try:
                cef = AccountCEF()
                original = BrowserSession(cef)
                original.target_id = 'old'
                service = Service(store, HLTBClient(original))
                prepared = await service.prepare_background()
                cef.pages.append({'id': 'unrelated', 'url': 'https://howlongtobeat.com/'})
                with self.assertRaisesRegex(IntegrationError, 'login_window_not_found'):
                    await service.retain_background()
                self.assertIs(service.client.browser, original)
                cef.pages.append({'id': 'retained', 'url': prepared['url']})
                cef.other_account = True
                with self.assertRaisesRegex(IntegrationError, 'account_changed_disconnect_first'):
                    await service.retain_background()
                self.assertIs(service.client.browser, original)
                cef.other_account = False
                self.assertTrue(await service.retain_background())
                cef.pages = [page for page in cef.pages if page['id'] != 'old']
                self.assertEqual(await service.refresh_library(), [])
                self.assertEqual(store.preference('browser_target'), 'retained')
                # Restart with a dead target: do not read or rediscover other tabs.
                restarted_browser = BrowserSession(cef)
                restarted_browser.target_id = 'gone-after-reboot'
                restarted = Service(store, HLTBClient(restarted_browser))
                prepared = await restarted.prepare_restore()
                cef.pages.append({'id': 'restored', 'url': prepared['url']})
                self.assertTrue(await restarted.retain_background())
                self.assertEqual(store.preference('browser_target'), 'restored')
                self.assertEqual(restarted.auth, 'connected')
                restarted.error = 'login_required'
                self.assertFalse(restarted.restore_allowed())
                restarted.error = None
                store.set_preference('browser_target', None)
                with self.assertRaisesRegex(IntegrationError, 'connect_required'):
                    await restarted.prepare_restore()
            finally:
                store.close()

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
