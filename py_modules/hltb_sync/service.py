"""Serialized application use cases. SQLite stays on the asyncio event thread."""
import asyncio
import copy
import json
import time
from .browser import BrowserSession, IntegrationError
from .client import HLTBClient, new_record, summary, positive
from .records import canonical, proposed, seconds, submission_matches, creation_matches
from .matching import normalized, suggest, trackable


def app_info(value):
    if not isinstance(value, dict) or not isinstance(value.get('id'), str) or not value['id'].isdecimal():
        raise ValueError('Invalid app identifier')
    if not 0 < int(value['id']) <= 0xffffffff or type(value.get('steam')) is not bool:
        raise ValueError('Invalid Steam app')
    if not isinstance(value.get('name'), str) or not 0 < len(value['name']) <= 200:
        raise ValueError('Invalid app name')
    minutes = value.get('minutes')
    if minutes is not None and (type(minutes) is not int or not 0 <= minutes <= 100000000):
        raise ValueError('Invalid Steam playtime')
    for key in ('platform', 'platformSource'):
        if key in value and (not isinstance(value[key], str) or len(value[key]) > 100):
            raise ValueError('Invalid shortcut hint')
    if 'excluded' in value and type(value['excluded']) is not bool:
        raise ValueError('Invalid shortcut hint')
    return value


class Service:
    def __init__(self, store, client, clock=time.monotonic):
        self.store, self.client, self.clock = store, client, clock
        self.lock = asyncio.Lock()
        self.tracker_epoch = None
        self.sequence = -1
        self.suspended = False
        self.last_observation = 0
        self.auth = 'disconnected'
        self.library_cache = []
        self.library_loaded = False
        self.error = None
        self.retired_epochs = set()
        self.background_client = None

    async def connect(self):
        self.background_client = None
        self.auth = 'connecting'
        self.client.user_id = None
        return {'url': await self.client.browser.begin()}

    def restore_allowed(self):
        return bool(self.store.preference('browser_target')) and self.auth != 'connecting' and self.error not in (
            'login_required', 'account_changed_disconnect_first')

    async def prepare_restore(self):
        if not self.restore_allowed():
            raise IntegrationError('connect_required')
        user_id = self.store.preference('connected_user')
        if user_id is None:
            # Upgrade from versions that persisted only the bound target.
            users = {json.loads(r['record'])['userId'] for r in self.store.db.execute('SELECT record FROM mappings')}
            if len(users) != 1:
                raise IntegrationError('connect_required')
            user_id = users.pop()
        return await self.prepare_background(positive(user_id))

    async def prepare_background(self, expected_user=None):
        # A plugin-owned Steam view uses the existing browser session in place.
        # Never export cookies or close the login view before verifying the handoff.
        user_id = expected_user if expected_user is not None else await self.client.identity()
        browser = BrowserSession(self.client.browser.cef)
        url = await browser.begin()
        browser.marked_only = True
        self.background_client = HLTBClient(browser)
        self.background_client.user_id = user_id
        return {'url': url.replace('/login#', '/#')}

    async def retain_background(self):
        if self.background_client is None:
            raise IntegrationError('connect_required')
        client = self.background_client
        entries = await client.library()  # Also rejects a different account.
        self.client = client
        self.background_client = None
        self.library_cache = entries
        self.library_loaded = True
        self.auth = 'connected'
        self.store.set_preference('browser_target', client.browser.target_id)
        self.store.set_preference('connected_user', client.user_id)
        self.store.set_preference('library_cache', entries)
        return True

    async def refresh_library(self):
        entries = await self.client.library()
        self.library_cache = entries
        self.library_loaded = True
        self.auth = 'connected'
        self.store.set_preference('library_cache', entries)
        self.store.set_preference('connected_user', self.client.user_id)
        return entries

    def status(self):
        mappings = []
        for row in self.store.db.execute('SELECT app,record FROM mappings'):
            mappings.append({'app': row['app'], **summary(json.loads(row['record'])), **{
                'mode': self.store.app(row['app'])['mode'],
                'historyImported': self.history_imported(row['app']),
                'automatic': bool(self.store.app(row['app'])['automatic'])}})
        operations = [self.operation_view(row) for row in self.store.operations()[:100]]
        sessions = self.store.sessions()[:100]
        names = {r['app']: r['name'] for r in self.store.db.execute('SELECT app,name FROM apps')}
        for session in sessions:
            session['name'] = names.get(session['app'], session['app'])
        return {'auth': self.auth, 'canRestore': self.restore_allowed(), 'error': self.error, 'mappings': mappings, 'sessions': sessions,
                'operations': operations, 'library': self.library_cache if self.library_loaded else self.store.preference('library_cache', []),
                'libraryCached': not self.library_loaded, 'matches': self.match_requests(),
                'tracker': 'observing' if self.last_observation and self.clock() - self.last_observation < 30 else 'waiting'}

    def operation_view(self, operation):
        before, after = json.loads(operation['before_json']), json.loads(operation['after_json'])
        return {'id': operation['id'], 'app': operation['app'], 'kind': operation['kind'],
                'state': operation['state'], 'created': operation['created'], 'title': after.get('title', ''),
                'platform': after['platform'], 'before': seconds(before) if before else 0,
                'after': seconds(after), 'resolution': operation['resolution']}

    async def bind(self, app, submission, mode):
        app_info(app)
        if mode not in ('sessions', 'steam_total') or (mode == 'steam_total' and not app['steam']):
            raise ValueError('Steam totals are available only for Steam games')
        if not trackable(app):
            raise ValueError('Select a direct game shortcut, not a launcher or desktop')
        if any(o['app'] == app['id'] and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict') for o in self.store.operations()):
            raise ValueError('Resolve the existing proposal before linking this shortcut')
        record = await self.client.read(positive(submission))
        self.store.remember_app(app)
        self.store.bind(app['id'], record)
        with self.store.db:
            self.store.db.execute('UPDATE apps SET mode=? WHERE app=?', (mode, app['id']))
        return summary(record)

    def match_requests(self):
        entries = self.library_cache if self.library_loaded else self.store.preference('library_cache', [])
        grouped = {}
        for session in self.store.sessions():
            if session['phase'] not in ('closed', 'interrupted') or session['state'] == 'synced':
                continue
            if not self.store.mapping(session['app']):
                grouped.setdefault(session['app'], []).append(session)
        requests = []
        for app_id, sessions in grouped.items():
            saved = self.store.app(app_id)
            app = {'id': app_id, 'name': saved['name'], 'steam': bool(saved['steam']),
                   'minutes': saved['minutes'], **self.store.preference('hints:' + app_id, {})}
            candidates, recommended = suggest(app, entries)
            notices = [s['id'] for s in sessions if not self.store.preference('noticed:' + s['id'], False)]
            requests.append({'app': app, 'seconds': sum(int(s['elapsed']) for s in sessions),
                             'candidates': candidates, 'recommended': recommended,
                             'notice': notices[0] if notices else None})
        return requests

    async def resolve_match(self, app):
        """Resolve identity; only new records may import Steam lifetime automatically."""
        app_info(app)
        if not trackable(app):
            raise ValueError('Select a direct game')
        app_id = app['id']
        if self.store.mapping(app_id):
            return {'state': 'linked'}
        sessions = [s for s in self.store.sessions() if s['app'] == app_id and s['state'] != 'synced']
        if not sessions or any(s['phase'] != 'closed' or s['state'] == 'attention' for s in sessions):
            return {'state': 'attention'}
        if any(o['app'] == app_id and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict')
               for o in self.store.operations()):
            return {'state': 'attention'}
        self.store.remember_app(app)  # Fresh Steam AppDetails supplied after exit.
        entries = await self.refresh_library()
        candidates, recommended = suggest(app, entries)
        catalog = []
        platform = app.get('platform') or ('PC' if app['steam'] else None)
        if not recommended:
            catalog = await self.client.search(app['name'])
            identities = []
            for candidate in catalog[:5]:
                identity = await self.client.game_identity(candidate['gameId'])
                matches = identity['steamId'] == app_id and platform in identity['platforms'] if app['steam'] else (
                    normalized(identity['title']) == normalized(app['name']) and
                    platform in identity['platforms'])
                if matches:
                    identities.append(identity)
            if len(identities) != 1 or not platform:
                return {'state': 'ambiguous', 'catalog': catalog[:10]}
            identity = identities[0]
            records = [e for e in entries if e['gameId'] == identity['gameId']]
            compatible = [e for e in records if e['platform'] == platform]
            if len(compatible) == 1:
                recommended = compatible[0]['submissionId']
            elif records:
                return {'state': 'ambiguous', 'catalog': catalog[:10]}
            else:
                if app['steam'] and (not app['minutes'] or app['minutes'] * 60 < sum(int(s['elapsed']) for s in sessions)):
                    raise ValueError('Steam lifetime is not ready; saved hours were not sent')
                operation = await self.prepare_create(app, identity['gameId'], identity['title'], platform,
                                                      include_sessions=True, steam_minutes=app['minutes'] if app['steam'] else None)
                verified = await self.send(operation['id'], True, True)
                return {'state': 'linked' if verified else 'attention'}
        await self.bind(app, recommended, 'sessions')
        operation = await self.prepare(app_id)
        verified = await self.send(operation['id'], True, True)
        return {'state': 'linked' if verified else 'attention'}

    def acknowledge_match(self, app_id, notice=None):
        # Dismiss only the session shown. A newer close must get its own prompt.
        # Acknowledging a dialog never consumes sessions or confirms a mapping.
        for session in self.store.sessions():
            if (session['app'] == app_id and session['phase'] in ('closed', 'interrupted')
                    and (notice is None or session['id'] == notice)):
                self.store.set_preference('noticed:' + session['id'], True)

    def observe(self, epoch, sequence, apps, event):
        if not isinstance(epoch, str) or not 1 <= len(epoch) <= 128 or type(sequence) is not int or sequence < 0:
            raise ValueError('Invalid observation sequence')
        if event not in ('snapshot', 'suspend', 'resume', 'unavailable') or not isinstance(apps, list) or len(apps) > 100:
            raise ValueError('Invalid observation')
        apps = [app_info(a) for a in apps]
        if len({a['id'] for a in apps}) != len(apps):
            raise ValueError('Duplicate app in observation')
        if epoch != self.tracker_epoch:
            if epoch in self.retired_epochs:
                return
            if self.tracker_epoch:
                self.retired_epochs.add(self.tracker_epoch)
            self.store.recover()
            self.tracker_epoch, self.sequence = epoch, -1
            self.suspended = False
        if sequence <= self.sequence:
            return
        tick = self.clock()
        if event == 'unavailable':
            self.store.recover()
            self.last_observation = 0
            self.sequence = sequence
            return
        for app in apps:
            self.store.remember_app(app)
            hints = {k: app[k] for k in ('platform', 'platformSource', 'excluded') if k in app}
            if hints:
                self.store.set_preference('hints:' + app['id'], hints)
        self.last_observation = tick
        current = {a['id'] for a in apps if trackable(a)}
        active = {s['app']: s for s in self.store.sessions() if s['phase'] in ('running', 'suspended')}
        def emit(app, kind):
            self.store.event(f'{epoch}:{sequence}:{app}:{kind}', app, kind, epoch, tick)
        if event == 'suspend':
            for app in active:
                emit(app, 'suspend')
            self.suspended = True
        elif event == 'resume':
            # Do not infer closure from a transiently empty list during resume.
            for app in active:
                emit(app, 'resume')
            self.suspended = False
        elif not self.suspended:
            for app in current - active.keys():
                emit(app, 'start')
            for app in active:
                emit(app, 'heartbeat' if app in current else 'stop')
        self.sequence = sequence

    async def prepare(self, app_id, steam_minutes=None):
        mapping = self.store.mapping(app_id)
        if not mapping:
            raise ValueError('Link this game first')
        if any(s['app'] == app_id and s['phase'] in ('running', 'suspended') for s in self.store.sessions()):
            raise ValueError('Close the game before preparing an update')
        if any(s['app'] == app_id and s['state'] == 'attention' for s in self.store.sessions()):
            raise ValueError('Review interrupted or uncertain sessions first')
        remote = await self.client.read(mapping['submissionId'])
        if canonical(remote) != canonical(mapping):
            raise IntegrationError('remote_changed_review_required')
        app = self.store.app(app_id)
        pending = [s for s in self.store.sessions() if s['app'] == app_id and s['phase'] == 'closed'
                   and s['state'] in ('local', 'pending')]
        if app['mode'] == 'steam_total':
            if type(steam_minutes) is not int or not 0 <= steam_minutes <= 100000000:
                raise ValueError('A fresh Steam playtime reading is required')
            target = steam_minutes * 60
            if target < seconds(remote):
                raise ValueError('Steam total is lower than HLTB; automatic reduction is blocked')
            after = copy.deepcopy(remote)
            h, rem = divmod(target, 3600)
            m, s = divmod(rem, 60)
            after['general']['progress'].update(hours=h, minutes=m, seconds=s)
        else:
            after = proposed(remote, sum(int(s['elapsed']) for s in pending))
        if canonical(after) == canonical(remote):
            raise ValueError('No new playtime to synchronize; wait for Steam totals to refresh')
        identifier = self.store.add_operation(app_id, app['mode'], remote, after, [s['id'] for s in pending])
        return self.operation_view(self.store.operation(identifier))

    def history_imported(self, app_id):
        return self.store.preference('history_imported:' + app_id, False) or any(o['app'] == app_id and o['kind'] == 'history_import' and (
            o['state'] == 'verified' or (o['state'] == 'resolved' and o['resolution'] == 'included'))
            for o in self.store.operations())

    async def prepare_history_import(self, app_id, total_minutes, includes_saved):
        if type(total_minutes) is not int or not 0 < total_minutes <= 100000000:
            raise ValueError('Enter a positive whole-minute lifetime total')
        if includes_saved is not True:
            raise ValueError('Confirm that this total includes all saved sessions')
        if self.history_imported(app_id):
            raise ValueError('Past hours have already been imported for this game')
        if any(o['app'] == app_id and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict')
               for o in self.store.operations()):
            raise ValueError('Resolve or cancel the existing proposal first')
        mapping = self.store.mapping(app_id)
        if not mapping:
            raise ValueError('Confirm the HLTB match first')
        remote = await self.client.read(mapping['submissionId'])
        if canonical(remote) != canonical(mapping):
            raise IntegrationError('remote_changed_review_required')
        sessions = [s for s in self.store.sessions() if s['app'] == app_id]
        if any(s['phase'] in ('running', 'suspended') or s['state'] == 'attention' for s in sessions):
            raise ValueError('Close the game and review interrupted sessions first')
        pending = [s for s in sessions if s['phase'] == 'closed' and s['state'] in ('local', 'pending')]
        target = total_minutes * 60
        if target <= seconds(remote) or target < sum(int(s['elapsed']) for s in pending):
            raise ValueError('The imported total must increase HLTB and include the saved sessions')
        after = proposed(remote, target - seconds(remote))
        identifier = self.store.add_operation(app_id, 'history_import', remote, after,
                                              [s['id'] for s in pending])
        return self.operation_view(self.store.operation(identifier))

    async def prepare_create(self, app, game_id, title, platform, include_sessions=False, steam_minutes=None):
        app_info(app)
        if self.store.mapping(app['id']):
            raise ValueError('This shortcut is already linked')
        entries = await self.refresh_library()
        if any(e['gameId'] == game_id for e in entries):
            raise ValueError('Existing records found; choose one before creating another')
        record = new_record(self.client.user_id, positive(game_id), title, platform)
        self.store.remember_app(app)
        sessions = [s for s in self.store.sessions() if s['app'] == app['id'] and s['state'] != 'synced'] if include_sessions else []
        if any(s['phase'] != 'closed' or s['state'] == 'attention' for s in sessions):
            raise ValueError('Review interrupted sessions before syncing')
        elapsed = sum(int(s['elapsed']) for s in sessions)
        if steam_minutes is not None:
            if not app['steam'] or type(steam_minutes) is not int or steam_minutes <= 0 or steam_minutes * 60 < elapsed:
                raise ValueError('Steam lifetime must include the saved sessions')
            elapsed = steam_minutes * 60
        if elapsed:
            hours, remainder = divmod(elapsed, 3600)
            minutes, secs = divmod(remainder, 60)
            record['general']['progress'].update(hours=hours, minutes=minutes, seconds=secs)
        identifier = self.store.add_operation(app['id'], 'create', None, record, [s['id'] for s in sessions])
        if steam_minutes is not None:
            self.store.set_preference('import_history:' + identifier, True)
        return self.operation_view(self.store.operation(identifier))

    async def send(self, identifier, authorized, enable_automatic=False):
        if authorized is not True:
            raise PermissionError('Approve this exact proposal before submitting')
        operation = self.store.operation(identifier)
        if operation['state'] != 'prepared':
            raise ValueError('Submission blocked; reconcile this operation instead')
        before, after = json.loads(operation['before_json']), json.loads(operation['after_json'])
        if operation['kind'] == 'create':
            entries = await self.refresh_library()
            unchanged = self.client.user_id == after['userId'] and not any(e['gameId'] == after['gameId'] for e in entries)
        else:
            current = await self.client.read(before['submissionId'])
            unchanged = canonical(current) == canonical(before)
        if not unchanged:
            self.store.operation_state(identifier, 'prepared', 'conflict')
            return False
        if enable_automatic is True:
            self.store.set_preference('auto_after:' + identifier, True)
        self.store.operation_state(identifier, 'prepared', 'sending')
        try:
            await self.client.submit(after)
            return await self.reconcile(identifier)
        except Exception:
            if self.store.operation(identifier)['state'] == 'sending':
                self.store.operation_state(identifier, 'sending', 'uncertain')
            return False

    async def reconcile(self, identifier):
        operation = self.store.operation(identifier)
        if operation['state'] not in ('sending', 'uncertain'):
            raise ValueError('Only an uncertain or in-flight operation can be reconciled')
        after = json.loads(operation['after_json'])
        if operation['kind'] == 'create':
            entries = await self.refresh_library()
            candidates = [e for e in entries if e['gameId'] == after['gameId'] and e['platform'] == after['platform']]
            if len(candidates) != 1:
                self.store.operation_state(identifier, operation['state'], 'uncertain')
                return False
            remote = await self.client.read(candidates[0]['submissionId'])
            # Server assigns identity metadata on creation. All user-editable fields
            # must still match the approved empty record.
            expected = copy.deepcopy(after)
            for key in ('submissionId', 'userIp', 'userName', 'adminId'):
                if key in remote:
                    expected[key] = remote[key]
        else:
            remote = await self.client.read(after['submissionId'])
            expected = after
        matches = creation_matches(expected, remote) if operation['kind'] == 'create' else submission_matches(expected, remote)
        if not matches:
            self.store.operation_state(identifier, operation['state'], 'uncertain')
            return False
        self.store.finish_operation(identifier, remote)
        return True

    async def remote_review(self, app_id):
        mapping = self.store.mapping(app_id)
        if not mapping:
            raise ValueError('No linked record')
        remote = await self.client.read(mapping['submissionId'])
        # Full records stay in the backend. The UI receives only safe summaries.
        return {'previous': summary(mapping), 'current': summary(remote),
                'changed': canonical(mapping) != canonical(remote)}

    async def accept_remote(self, app_id, expected_seconds):
        if any(o['app'] == app_id and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict')
               for o in self.store.operations()):
            raise ValueError('Resolve the outstanding proposal first')
        mapping = self.store.mapping(app_id)
        remote = await self.client.read(mapping['submissionId'])
        if any(remote[k] != mapping[k] for k in ('userId', 'gameId', 'submissionId', 'platform')):
            raise ValueError('Record identity or platform changed; do not rebase this mapping')
        if seconds(remote) != expected_seconds:
            raise ValueError('Remote time changed again; review it first')
        with self.store.db:
            self.store.db.execute('UPDATE mappings SET record=? WHERE app=?', (canonical(remote), app_id))
        # This does not replay confirmed sessions and does not change pending time.

    def cancel_prepared(self, identifier):
        self.store.operation_state(identifier, 'prepared', 'cancelled', 'cancelled_before_send')

    async def resolve(self, identifier, decision):
        if decision not in ('included', 'not_included'):
            raise ValueError('Explicit reconciliation decision required')
        operation = self.store.operation(identifier)
        if operation['kind'] == 'create':
            raise ValueError('Creation requires a matching reread; do not blindly create again')
        if operation['state'] not in ('uncertain', 'conflict'):
            raise ValueError('Operation does not require reconciliation')
        after = json.loads(operation['after_json'])
        remote = await self.client.read(after['submissionId'])
        if any(remote[k] != after[k] for k in ('userId', 'gameId', 'submissionId', 'platform')):
            raise ValueError('Record identity or platform changed')
        with self.store.db:
            self.store.db.execute("UPDATE operations SET state='resolved',resolution=? WHERE id=?", (decision, identifier))
            self.store.db.execute('UPDATE mappings SET record=? WHERE app=?', (canonical(remote), operation['app']))
            for sid in json.loads(operation['sessions_json']):
                self.store.db.execute('UPDATE sessions SET state=?,reason=NULL WHERE id=?',
                                      ('synced' if decision == 'included' else 'pending', sid))
            self.store.db.execute('UPDATE apps SET automatic=0 WHERE app=?', (operation['app'],))
            if operation['kind'] == 'history_import' and decision == 'included':
                self.store.db.execute("UPDATE apps SET mode='sessions' WHERE app=?", (operation['app'],))

    async def adopt_created_record(self, identifier, submission):
        operation = self.store.operation(identifier)
        if operation['kind'] != 'create' or operation['state'] not in ('uncertain', 'conflict'):
            raise ValueError('Only an unresolved creation may adopt an existing record')
        expected = json.loads(operation['after_json'])
        remote = await self.client.read(positive(submission))
        if any(remote[k] != expected[k] for k in ('userId', 'gameId', 'platform')):
            raise ValueError('The selected account record does not match this game and platform')
        with self.store.db:
            if self.store.mapping(operation['app']):
                raise ValueError('This shortcut already has a mapping')
            self.store.db.execute('INSERT INTO mappings VALUES (?,?,?)',
                                (operation['app'], canonical(remote), remote['submissionId']))
            self.store.db.execute("UPDATE operations SET state='resolved',resolution='adopted_existing_record' WHERE id=?",
                                (identifier,))

    def accept_checkpoint(self, session_id):
        session = next((s for s in self.store.sessions() if s['id'] == session_id), None)
        if not session or session['state'] != 'attention' or session['reason'] not in ('restart', 'observation_gap'):
            raise ValueError('Only an interrupted checkpoint may be accepted')
        if session['phase'] in ('running', 'suspended'):
            raise ValueError('Close the game before reviewing its checkpoint')
        with self.store.db:
            self.store.db.execute("UPDATE sessions SET phase='closed',state='pending',reason=NULL WHERE id=?", (session_id,))

    def set_automatic(self, app_id, enabled, single_writer=None):
        if type(enabled) is not bool:
            raise ValueError('Invalid preference')
        if enabled:
            app = self.store.app(app_id)
            if app['mode'] != 'sessions':
                raise ValueError('Steam totals require a fresh manual preview in this release')
            if not self.store.mapping(app_id):
                raise ValueError('Confirm the HLTB match first')
        with self.store.db:
            self.store.db.execute('UPDATE apps SET automatic=? WHERE app=?', (int(enabled), app_id))
        if not enabled:
            for operation in self.store.operations():
                if operation['app'] == app_id:
                    self.store.set_preference('auto_after:' + operation['id'], False)

    async def auto_sync(self):
        for row in self.store.db.execute('SELECT app FROM apps WHERE automatic=1').fetchall():
            app_id = row['app']
            if any(o['app'] == app_id and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict') for o in self.store.operations()):
                continue
            if not any(s['app'] == app_id and s['phase'] == 'closed' and s['state'] == 'pending' for s in self.store.sessions()):
                continue
            try:
                proposal = await self.prepare(app_id)
                verified = await self.send(proposal['id'], True)
                self.error = None if verified else 'automatic_sync_needs_attention'
            except IntegrationError as exc:
                code = str(exc)
                if code == 'network_or_session_error':
                    blocked = any(o['app'] == app_id and o['state'] in ('prepared', 'sending', 'uncertain', 'conflict')
                                  for o in self.store.operations())
                    self.error = 'automatic_sync_needs_attention' if blocked else 'sync_waiting_connection'
                elif code in ('login_required', 'connect_required', 'browser_closed_or_navigated'):
                    self.auth = 'reconnect_required'
                    self.error = code
                else:
                    self.error = 'automatic_sync_needs_attention'
            except Exception:
                # Leave sessions intact. No automatic retry of persisted proposals.
                self.error = 'automatic_sync_needs_attention'
