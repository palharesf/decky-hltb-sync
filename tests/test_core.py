import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'py_modules'))
from hltb_sync.records import RecordError, parse_edit_html, proposed, seconds
from hltb_sync.store import Store
from hltb_sync.sync import reconcile, send_manual


def record():
    return {'userId': 1, 'gameId': 2, 'submissionId': 3, 'platform': 'PlayStation 2',
            'general': {'progress': {'hours': 1, 'minutes': 2, 'seconds': 3},
                        'progressBefore': {'hours': None}, 'completionDate': {'year': '0000'}},
            'lists': {'playing': True, 'completed': False, 'custom2': True},
            'review': {'score': 91, 'notes': 'Private note'},
            'additionals': {'notes': 'Preserve me'}, 'futureField': {'nested': [1, 2]}}


class Transport:
    def __init__(self):
        self.remote = record()
        self.writes = 0
        self.fail = None

    def read(self, submission):
        if self.fail == 'offline':
            raise ConnectionError()
        return copy.deepcopy(self.remote)

    def submit(self, payload):
        self.writes += 1
        if self.fail != 'before':
            self.remote = payload
        if self.fail in ('before', 'after'):
            raise TimeoutError('MUST NOT BE LOGGED')


class CoreTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / '.local'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.temp.name) / 'sessions.sqlite3'
        self.store = Store(self.path)
        self.n = 0

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def event(self, kind, tick, event_id=None):
        self.n += 1
        self.store.event(event_id or str(self.n), '999', kind, 'boot', tick)

    def session(self):
        return self.store.sessions()[0]

    def ready(self):
        self.store.bind('999', record())
        self.event('start', 0)
        self.event('stop', 20)
        return self.store.prepare(self.session()['id'], record())

    def test_suspend_is_not_stop_and_is_excluded(self):
        self.event('start', 10)
        self.event('suspend', 20)
        self.event('suspend', 100)
        self.assertEqual(self.session()['phase'], 'suspended')
        self.event('resume', 1000)
        self.event('resume', 1000)
        self.event('stop', 1010)
        self.assertEqual(self.session()['elapsed'], 20)

    def test_close_while_suspended(self):
        self.event('start', 0)
        self.event('suspend', 10)
        self.event('stop', 9000)
        self.assertEqual(self.session()['elapsed'], 10)

    def test_duplicate_start_stop_and_event_id(self):
        self.event('start', 0)
        self.event('start', 1)
        self.event('heartbeat', 10, 'same')
        self.event('heartbeat', 20, 'same')
        self.event('stop', 20)
        self.event('stop', 21)
        self.assertEqual(len(self.store.sessions()), 1)
        self.assertEqual(self.session()['elapsed'], 20)

    def test_recovery_preserves_checkpoint_without_guessing(self):
        self.event('start', 0)
        self.event('heartbeat', 10)
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.assertEqual(self.session()['elapsed'], 10)
        self.assertEqual(self.session()['state'], 'attention')
        self.event('start', 1000)
        self.assertEqual(self.session()['elapsed'], 0)

    def test_gap_requires_attention(self):
        self.event('start', 0)
        self.event('stop', 1000)
        self.assertEqual(self.session()['elapsed'], 0)
        self.assertEqual(self.session()['state'], 'attention')

    def test_wrong_clock_rolls_back_event(self):
        self.event('start', 10)
        with self.assertRaises(ValueError):
            self.store.event('retry', '999', 'stop', 'other', 20)
        self.store.event('retry', '999', 'stop', 'boot', 20)
        self.assertEqual(self.session()['elapsed'], 10)

    def test_no_retroactive_accounting(self):
        self.event('heartbeat', 100000)
        self.assertEqual(self.store.sessions(), [])
        self.event('start', 100000)
        self.event('stop', 100010)
        self.assertEqual(self.session()['elapsed'], 10)

    def test_payload_preserves_every_other_field(self):
        before = record()
        after = proposed(before, 3600)
        self.assertEqual(seconds(after), seconds(before) + 3600)
        after['general']['progress'] = before['general']['progress']
        self.assertEqual(after, before)
        self.assertEqual(before, record())

    def test_null_progress_and_unknown_fields(self):
        value = record()
        value['general']['progress'] = dict(hours=None, minutes=None, seconds=None, extra='keep')
        self.assertEqual(proposed(value, 60)['general']['progress'],
                         dict(hours=0, minutes=1, seconds=0, extra='keep'))

    def test_parser_rejects_login_and_preserves_full_record(self):
        html = '<script type="application/json" id="__NEXT_DATA__">' + json.dumps(
            {'props': {'pageProps': {'editData': record()}}}) + '</script>'
        self.assertEqual(parse_edit_html(html), record())
        with self.assertRaises(RecordError):
            parse_edit_html('<html>Login</html>')

    def test_unknown_time_format_fails_closed(self):
        value = record()
        value['general']['progress']['seconds'] = '03'
        with self.assertRaises(RecordError):
            proposed(value, 20)

    def test_explicit_unique_mapping_and_drift(self):
        self.store.bind('999', record())
        with self.assertRaises(Exception):
            self.store.bind('998', record())
        self.event('start', 0)
        self.event('stop', 20)
        changed = record()
        changed['review']['score'] = 90
        with self.assertRaises(ValueError):
            self.store.prepare(self.session()['id'], changed)

    def test_requires_authorization(self):
        job = self.ready()
        transport = Transport()
        with self.assertRaises(PermissionError):
            send_manual(self.store, job['id'], transport)
        self.assertEqual(transport.writes, 0)

    def test_success_rereads_and_deduplicates(self):
        job = self.ready()
        transport = Transport()
        self.assertTrue(send_manual(self.store, job['id'], transport, authorized=True))
        self.assertEqual(self.session()['state'], 'synced')
        with self.assertRaises(ValueError):
            send_manual(self.store, job['id'], transport, authorized=True)
        self.assertEqual(transport.writes, 1)
        with self.assertRaises(ValueError):
            self.store.prepare(self.session()['id'], transport.remote)

    def test_timeout_after_server_write_reconciles_without_resend(self):
        job = self.ready()
        transport = Transport()
        transport.fail = 'after'
        self.assertFalse(send_manual(self.store, job['id'], transport, authorized=True))
        self.assertEqual(self.session()['state'], 'attention')
        self.store.close()
        self.store = Store(self.path)
        self.store.recover()
        self.assertTrue(reconcile(self.store, job['id'], transport))
        self.assertEqual(transport.writes, 1)

    def test_timeout_without_write_does_not_allow_blind_retry(self):
        job = self.ready()
        transport = Transport()
        transport.fail = 'before'
        send_manual(self.store, job['id'], transport, authorized=True)
        self.assertFalse(reconcile(self.store, job['id'], transport))
        with self.assertRaises(ValueError):
            send_manual(self.store, job['id'], transport, authorized=True)

    def test_crash_after_intent_is_uncertain(self):
        job = self.ready()
        self.store.transition(job['id'], 'prepared', 'sending')
        self.store.recover()
        self.assertEqual(self.store.job(job['id'])['state'], 'uncertain')

    def test_playnite_overwrite_blocks_before_post(self):
        job = self.ready()
        transport = Transport()
        transport.remote['general']['progress']['hours'] = 0
        self.assertFalse(send_manual(self.store, job['id'], transport, authorized=True))
        self.assertEqual(transport.writes, 0)
        self.assertEqual(self.store.job(job['id'])['state'], 'conflict')

    def test_offline_read_keeps_prepared_session(self):
        job = self.ready()
        transport = Transport()
        transport.fail = 'offline'
        with self.assertRaises(ConnectionError):
            send_manual(self.store, job['id'], transport, authorized=True)
        self.assertEqual(self.store.job(job['id'])['state'], 'prepared')
        self.assertEqual(self.session()['elapsed'], 20)

    def test_second_job_for_same_game_blocked_until_verified(self):
        self.ready()
        self.event('start', 100)
        self.event('stop', 110)
        with self.assertRaises(ValueError):
            self.store.prepare(self.session()['id'], record())

    def test_next_session_uses_verified_baseline(self):
        job = self.ready()
        transport = Transport()
        send_manual(self.store, job['id'], transport, authorized=True)
        self.event('start', 100)
        self.event('stop', 110)
        next_job = self.store.prepare(self.session()['id'], transport.remote)
        self.assertEqual(seconds(next_job['after']), seconds(record()) + 30)
        self.assertTrue(send_manual(self.store, next_job['id'], transport, authorized=True))

    def test_post_write_preservation_mismatch_is_not_success(self):
        job = self.ready()
        self.store.transition(job['id'], 'prepared', 'sending')
        altered = copy.deepcopy(job['after'])
        altered['review']['notes'] = 'Concurrent edit'
        self.assertFalse(self.store.verify(job['id'], altered))
        self.assertEqual(self.session()['state'], 'attention')

    def test_future_schema_refuses_to_downgrade(self):
        self.store.db.execute('PRAGMA user_version=2')
        with self.assertRaises(ValueError):
            Store(self.path)
        self.assertEqual(self.store.db.execute('PRAGMA user_version').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
