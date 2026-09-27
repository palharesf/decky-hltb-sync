"""Durable local ledger. Only acknowledged active intervals are counted."""
import math
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
        if self.db.execute('PRAGMA user_version').fetchone()[0] not in (0, 1):
            self.db.close()
            raise ValueError('Versão de banco não suportada; dados preservados')
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
            PRAGMA user_version=1;
        ''')

    def recover(self):
        with self.db:
            self.db.execute("UPDATE sessions SET phase='interrupted', state='attention', "
                            "reason='restart' WHERE phase IN ('running','suspended')")
            self.db.execute("UPDATE jobs SET state='uncertain' WHERE state='sending'")
            self.db.execute("UPDATE sessions SET state='attention', reason='uncertain' "
                            "WHERE id IN (SELECT session FROM jobs WHERE state='uncertain')")

    def bind(self, app, record):
        validate(record)
        if not isinstance(app, str) or not app.isdecimal():
            raise ValueError('AppID inválido')
        with self.db:
            # Remapping is deliberately unavailable in the pilot.
            self.db.execute('INSERT INTO mappings VALUES (?,?,?)',
                            (app, canonical(record), record['submissionId']))

    def event(self, event_id, app, kind, epoch, tick):
        if kind not in ('start', 'heartbeat', 'suspend', 'resume', 'stop'):
            raise ValueError('Evento desconhecido')
        if not all(isinstance(v, str) and 0 < len(v) <= 128
                   for v in (event_id, app, epoch)):
            raise ValueError('Identificador inválido')
        if not isinstance(tick, (int, float)) or not math.isfinite(tick) or tick < 0:
            raise ValueError('Relógio inválido')
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
                raise ValueError('Evento de outra execução ou fora de ordem')
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
                raise ValueError('Sessão não elegível')
            mapping = self.db.execute('SELECT * FROM mappings WHERE app=?', (session['app'],)).fetchone()
            if not mapping or mapping['record'] != canonical(remote):
                raise ValueError('Registro mudou: reconciliação manual necessária')
            if self.db.execute("SELECT 1 FROM jobs j JOIN sessions s ON s.id=j.session "
                               "WHERE s.app=? AND j.state!='verified'", (session['app'],)).fetchone():
                raise ValueError('Existe operação não resolvida para este jogo')
            after = proposed(remote, int(session['elapsed']))
            job_id = str(uuid.uuid4())
            self.db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)',
                            (job_id, session_id, canonical(remote), canonical(after), 'prepared'))
            self.db.execute("UPDATE sessions SET state='pending' WHERE id=?", (session_id,))
            return {'id': job_id, 'before': remote, 'after': after}

    def job(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Operação inexistente')
        return dict(row)

    def transition(self, job_id, expected, target):
        with self.db:
            changed = self.db.execute('UPDATE jobs SET state=? WHERE id=? AND state=?',
                                      (target, job_id, expected)).rowcount
            if changed != 1:
                raise ValueError('Operação já processada ou bloqueada')
            if target in ('uncertain', 'conflict'):
                self.db.execute("UPDATE sessions SET state='attention',reason=? "
                                'WHERE id=(SELECT session FROM jobs WHERE id=?)', (target, job_id))

    def verify(self, job_id, remote):
        job = self.job(job_id)
        if job['state'] not in ('sending', 'uncertain'):
            raise ValueError('Operação não enviada')
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
