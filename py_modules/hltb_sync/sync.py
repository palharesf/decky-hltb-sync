"""Transport-independent protocol; no production write transport is provided yet."""
import json
from .records import canonical


def send_manual(store, job_id, transport, *, authorized=False):
    if not authorized:
        raise PermissionError('Envio exige autorização para esta proposta')
    job = store.job(job_id)
    if job['state'] != 'prepared':
        raise ValueError('Reenvio bloqueado; releia para reconciliar')
    before = json.loads(job['before_json'])
    current = transport.read(before['submissionId'])
    if canonical(current) != job['before_json']:
        store.transition(job_id, 'prepared', 'conflict')
        return False
    # Commit intent BEFORE the request. A process crash must not cause a resend.
    store.transition(job_id, 'prepared', 'sending')
    try:
        transport.submit(json.loads(job['after_json']))
        return store.verify(job_id, transport.read(before['submissionId']))
    except Exception:
        # HTTP errors, timeout, malformed response and expired login are all uncertain
        # once a request may have left the process. Never log the exception/payload.
        store.transition(job_id, 'sending', 'uncertain')
        return False


def reconcile(store, job_id, transport):
    job = store.job(job_id)
    remote = transport.read(json.loads(job['before_json'])['submissionId'])
    return store.verify(job_id, remote)
