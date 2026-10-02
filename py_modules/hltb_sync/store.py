"""Durable local ledger. Only acknowledged active intervals are counted."""
import math
import json
import os
import sqlite3
import uuid
from .records import canonical, proposed, validate


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name != 'nt':
            os.chmod(path.parent, 0o700)
        self.db = sqlite3.connect(path)
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise ValueError('Unsupported database version; data preserved')
        if os.name != 'nt':
            os.chmod(path, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS mappings (
                app TEXT PRIMARY KEY, record TEXT NOT NULL,
                submission INTEGER NOT NULL UNIQUE);
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, app TEXT NOT NULL, epoch TEXT NOT NULL,
                last REAL NOT NULL, elapsed REAL NOT NULL DEFAULT 0,
                phase TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'local',
                reason TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS active_app ON sessions(app)
                WHERE phase IN ('running','suspended');
            CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, session TEXT NOT NULL UNIQUE REFERENCES sessions(id),
                before_json TEXT NOT NULL, after_json TEXT NOT NULL,
                state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS apps (app TEXT PRIMARY KEY, name TEXT NOT NULL,
                steam INTEGER NOT NULL, minutes INTEGER, mode TEXT NOT NULL DEFAULT 'sessions',
                automatic INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS operations (
                id TEXT PRIMARY KEY, app TEXT NOT NULL, kind TEXT NOT NULL,
                before_json TEXT NOT NULL, after_json TEXT NOT NULL,
                sessions_json TEXT NOT NULL, state TEXT NOT NULL,
                resolution TEXT, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE UNIQUE INDEX IF NOT EXISTS one_open_operation ON operations(app)
                WHERE state IN ('prepared','sending','uncertain','conflict');
        ''')
        if version < 2:
            with self.db:
                for row in self.db.execute('SELECT app,record FROM mappings').fetchall():
                    record = json.loads(row['record'])
                    self.db.execute('INSERT OR IGNORE INTO apps(app,name,steam) VALUES (?,?,0)',
                                    (row['app'], record.get('title', row['app'])))
                for row in self.db.execute('SELECT j.*,s.app FROM jobs j JOIN sessions s ON s.id=j.session').fetchall():
                    self.db.execute('INSERT OR IGNORE INTO operations(id,app,kind,before_json,after_json,sessions_json,state) '
                                    "VALUES (?,?,'sessions',?,?,?,?)", (row['id'], row['app'], row['before_json'],
                                    row['after_json'], canonical([row['session']]), row['state']))
        with self.db:
            self.db.execute('PRAGMA user_version=2')

    def recover(self):
        with self.db:
            self.db.execute("UPDATE sessions SET phase='interrupted', state='attention', "
                            "reason='restart' WHERE phase IN ('running','suspended')")
            self.db.execute("UPDATE jobs SET state='uncertain' WHERE state='sending'")
            self.db.execute("UPDATE sessions SET state='attention', reason='uncertain' "
                            "WHERE id IN (SELECT session FROM jobs WHERE state='uncertain' "
                            "AND NOT EXISTS (SELECT 1 FROM operations WHERE operations.id=jobs.id))")
            self.db.execute("UPDATE operations SET state='uncertain' WHERE state='sending'")
            for row in self.db.execute("SELECT sessions_json FROM operations WHERE state='uncertain'"):
                for sid in json.loads(row[0]):
                    self.db.execute("UPDATE sessions SET state='attention',reason='uncertain' WHERE id=?", (sid,))

    def bind(self, app, record):
        validate(record)
        if not isinstance(app, str) or not app.isdecimal():
            raise ValueError('Invalid AppID')
        with self.db:
            # Remapping is deliberately unavailable in the pilot.
            self.db.execute('INSERT INTO mappings VALUES (?,?,?)',
                            (app, canonical(record), record['submissionId']))

    def event(self, event_id, app, kind, epoch, tick):
        if kind not in ('start', 'heartbeat', 'suspend', 'resume', 'stop'):
            raise ValueError('Unknown event')
        if not all(isinstance(v, str) and 0 < len(v) <= 128
                   for v in (event_id, app, epoch)):
            raise ValueError('Invalid identifier')
        if not isinstance(tick, (int, float)) or not math.isfinite(tick) or tick < 0:
            raise ValueError('Invalid clock')
        with self.db:
            if not self.db.execute('INSERT OR IGNORE INTO events VALUES (?)', (event_id,)).rowcount:
                return
            row = self.db.execute("SELECT * FROM sessions WHERE app=? AND phase IN "
                                  "('running','suspended')", (app,)).fetchone()
            if not row:
                if kind == 'start':
                    self.db.execute('INSERT INTO sessions(id,app,epoch,last,phase) VALUES (?,?,?,?,?)',
                                    (str(uuid.uuid4()), app, epoch, tick, 'running'))
                return
            if kind == 'start':
                return
            if row['epoch'] != epoch or tick < row['last']:
                raise ValueError('Event from another execution or out of order')
            # Linux CLOCK_MONOTONIC excludes sleep. Never accept a large unobserved gap.
            gap = tick - row['last']
            elapsed = row['elapsed']
            state, reason = row['state'], row['reason']
            if row['phase'] == 'running':
                if gap > 30:
                    state, reason = 'attention', 'observation_gap'
                else:
                    elapsed += gap
            phase = row['phase']
            if kind == 'suspend':
                phase = 'suspended'
            elif kind == 'resume':
                phase = 'running'
            elif kind == 'stop':
                phase = 'closed'
                if state != 'attention':
                    state = 'pending' if self.db.execute(
                        'SELECT 1 FROM mappings WHERE app=?', (app,)).fetchone() else 'local'
            self.db.execute('UPDATE sessions SET last=?,elapsed=?,phase=?,state=?,reason=? WHERE id=?',
                            (tick, elapsed, phase, state, reason, row['id']))

    def sessions(self):
        return [dict(r) for r in self.db.execute(
            'SELECT id,app,elapsed,phase,state,reason FROM sessions ORDER BY rowid DESC')]

    def prepare(self, session_id, remote):
        validate(remote)
        with self.db:
            session = self.db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
            if not session or session['phase'] != 'closed' or session['state'] not in ('local', 'pending'):
                raise ValueError('Session is not eligible')
            mapping = self.db.execute('SELECT * FROM mappings WHERE app=?', (session['app'],)).fetchone()
            if not mapping or mapping['record'] != canonical(remote):
                raise ValueError('Record changed: manual reconciliation required')
            if self.db.execute("SELECT 1 FROM jobs j JOIN sessions s ON s.id=j.session "
                               "WHERE s.app=? AND j.state!='verified'", (session['app'],)).fetchone():
                raise ValueError('This game has an unresolved operation')
            after = proposed(remote, int(session['elapsed']))
            job_id = str(uuid.uuid4())
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',
                            (job_id, session_id, canonical(remote), canonical(after), 'prepared'))
            self.db.execute("UPDATE sessions SET state='pending' WHERE id=?", (session_id,))
            return {'id': job_id, 'before': remote, 'after': after}

    def job(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Operation not found')
        return dict(row)

    def transition(self, job_id, expected, target):
        with self.db:
            changed = self.db.execute('UPDATE jobs SET state=? WHERE id=? AND state=?',
                                      (target, job_id, expected)).rowcount
            if changed != 1:
                raise ValueError('Operation already processed or blocked')
            if target in ('uncertain', 'conflict'):
                self.db.execute("UPDATE sessions SET state='attention',reason=? "
                                'WHERE id=(SELECT session FROM jobs WHERE id=?)', (target, job_id))

    def verify(self, job_id, remote):
        job = self.job(job_id)
        if job['state'] not in ('sending', 'uncertain'):
            raise ValueError('Operation has not been submitted')
        if canonical(remote) != job['after_json']:
            self.transition(job_id, job['state'], 'uncertain')
            return False
        with self.db:
            self.db.execute("UPDATE jobs SET state='verified' WHERE id=?", (job_id,))
            self.db.execute("UPDATE sessions SET state='synced',reason=NULL WHERE id=?", (job['session'],))
            self.db.execute('UPDATE mappings SET record=? WHERE app=(SELECT app FROM sessions WHERE id=?)',
                            (canonical(remote), job['session']))
        return True

    def close(self):
        self.db.close()

    def preference(self, key, default=None):
        row = self.db.execute('SELECT value FROM preferences WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_preference(self, key, value):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)', (key, canonical(value)))

    def mapping(self, app):
        row = self.db.execute('SELECT record FROM mappings WHERE app=?', (app,)).fetchone()
        return json.loads(row[0]) if row else None

    def operations(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM operations ORDER BY rowid DESC')]

    def operation(self, identifier):
        row = self.db.execute('SELECT * FROM operations WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise ValueError('Operation not found')
        return dict(row)

    def add_operation(self, app, kind, before, after, sessions):
        identifier = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO operations(id,app,kind,before_json,after_json,sessions_json,state) '
                            "VALUES (?,?,?,?,?,?,'prepared')", (identifier, app, kind,
                            canonical(before), canonical(after), canonical(sessions)))
        return identifier

    def operation_state(self, identifier, expected, target, resolution=None):
        with self.db:
            if self.db.execute('UPDATE operations SET state=?,resolution=? WHERE id=? AND state=?',
                               (target, resolution, identifier, expected)).rowcount != 1:
                raise ValueError('Operation already processed or blocked')
            if target in ('uncertain', 'conflict'):
                for sid in json.loads(self.operation(identifier)['sessions_json']):
                    self.db.execute("UPDATE sessions SET state='attention',reason=? WHERE id=?", (target, sid))

    def remember_app(self, app):
        with self.db:
            self.db.execute('INSERT INTO apps(app,name,steam,minutes) VALUES (?,?,?,?) '
                            'ON CONFLICT(app) DO UPDATE SET name=excluded.name,steam=excluded.steam,minutes=excluded.minutes',
                            (app['id'], app['name'], int(app['steam']), app.get('minutes')))

    def app(self, app_id):
        row = self.db.execute('SELECT * FROM apps WHERE app=?', (app_id,)).fetchone()
        if not row:
            raise ValueError('Select a Steam library entry first')
        return dict(row)

    def finish_operation(self, identifier, remote):
        operation = self.operation(identifier)
        if operation['state'] not in ('sending', 'uncertain'):
            raise ValueError('Operation has not been submitted')
        with self.db:
            self.db.execute("UPDATE operations SET state='verified' WHERE id=?", (identifier,))
            if self.preference('import_history:' + identifier, False):
                self.set_preference('history_imported:' + operation['app'], True)
            if operation['kind'] == 'history_import':
                self.db.execute("UPDATE apps SET mode='sessions',automatic=0 WHERE app=?", (operation['app'],))
            if self.preference('auto_after:' + identifier, False):
                self.db.execute("UPDATE apps SET mode='sessions',automatic=1 WHERE app=?", (operation['app'],))
            for sid in json.loads(operation['sessions_json']):
                self.db.execute("UPDATE sessions SET state='synced',reason=NULL WHERE id=?", (sid,))
            if self.mapping(operation['app']):
                self.db.execute('UPDATE mappings SET record=? WHERE app=?', (canonical(remote), operation['app']))
            else:
                self.db.execute('INSERT INTO mappings VALUES (?,?,?)',
                                (operation['app'], canonical(remote), remote['submissionId']))
