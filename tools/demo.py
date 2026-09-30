"""Synthetic end-to-end run. No credentials, network or real Steam AppID."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'py_modules'))
from hltb_sync.store import Store
from hltb_sync.sync import send_manual
from hltb_sync.records import seconds
import tempfile


class FakeHLTB:
    def __init__(self, record):
        self.record = copy.deepcopy(record)

    def read(self, submission_id):
        return copy.deepcopy(self.record)

    def submit(self, record):
        self.record = copy.deepcopy(record)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1] / '.local'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        store = Store(Path(directory) / 'demo.sqlite3')
        record = {'userId': 1, 'gameId': 2, 'submissionId': 3, 'title': 'Synthetic PS2 game',
                  'platform': 'PlayStation 2', 'general': {'progress': {'hours': 1, 'minutes': 0, 'seconds': 0}},
                  'lists': {'completed': False}, 'review': {'score': 80, 'notes': 'Keep me'}}
        store.bind('999', record)
        for event_id, kind, tick in [('1','start',0), ('2','suspend',20),
                                     ('3','resume',1000), ('4','stop',1010)]:
            store.event(event_id, '999', kind, 'demo', tick)
        job = store.prepare(store.sessions()[0]['id'], record)
        print(f"SIMULATION: before={seconds(job['before'])}s; proposed={seconds(job['after'])}s")
        print('Simulated verification:', send_manual(store, job['id'], FakeHLTB(record), authorized=True))
        print('State:', store.sessions()[0]['state'])
        store.close()
